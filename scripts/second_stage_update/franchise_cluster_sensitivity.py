"""Inference-only MLB audit: consolidate relocated/renamed franchise clusters.

From repository root:
python scripts/second_stage_update/franchise_cluster_sensitivity.py

Primary point estimates, samples, controls, FE, and saved files are unchanged.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import patsy
import pyhdfe
from scipy import linalg, stats
from linearmodels.iv import IV2SLS

from weekend_iv import ROOT, OUT, BASE_CONTROLS, load_league, codes, fe_rank, cluster_cov


def main():
    protected = [OUT/"model_results.csv", OUT/"anderson_rubin.json", OUT/"data_audit.json", OUT/"provenance.json"]
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    data, _ = load_league("MLB")
    h, _ = codes(data.home_season)
    a, _ = codes(data.away_season)
    rank_fe = fe_rank(h, a)
    controls = patsy.dmatrix("0 + C(year_month) + " + BASE_CONTROLS, data, return_type="dataframe")
    matrix = np.column_stack([data.home_win, data.attendance_1000, data.weekend, controls])
    absorber = pyhdfe.create(np.column_stack([h,a]), drop_singletons=False, compute_degrees=False,
                            residualize_method="map", options={"tol":1e-10,"iteration_limit":100000})
    residualized = absorber.residualize(matrix.astype(float))
    y,d,z = residualized[:,0],residualized[:,1],residualized[:,2]
    rawx = residualized[:,3:]
    _,r,pivot = linalg.qr(rawx,mode="economic",pivoting=True)
    rank_x = int((np.abs(np.diag(r))>1e-8).sum())
    x = rawx[:,pivot[:rank_x]]
    # Source IDs FLO/MIA and MON/WAS identify the two split franchise histories.
    # All other source IDs remain separate; team-season FE are unchanged.
    cluster_labels = data.home_team_id.replace({"FLO":"FLO_MIA", "MIA":"FLO_MIA", "MON":"MON_WAS", "WAS":"MON_WAS"})
    team, nteam = codes(cluster_labels)
    date, ndate = codes(data.date_key)
    n, k = len(data), rank_fe+rank_x+1
    df = min(nteam,ndate)-1
    crit = stats.t.ppf(.975,df)
    rows = []
    primary = pd.read_csv(OUT/"model_results.csv")
    primary = primary.loc[primary.league.eq("MLB") & primary.specification.eq("main")].set_index("model")
    for model,dep,reg in [("OLS",y,d),("first_stage",d,z),("reduced_form",y,z),("2SLS",y,d)]:
        design = np.column_stack([x,reg])
        if model=="2SLS":
            instruments = np.column_stack([x,z])
            projected = instruments @ np.linalg.solve(instruments.T@instruments,instruments.T@design)
            bread = np.linalg.inv(design.T@projected)
            b = bread @ projected.T @ dep
            residual = dep-design@b
            score = projected*residual[:,None]
        else:
            bread = np.linalg.inv(design.T@design)
            b = bread@design.T@dep
            residual = dep-design@b
            score = design*residual[:,None]
        cov = cluster_cov(score,bread,team,date,k)
        se = float(np.sqrt(cov[-1,-1]))
        assert np.isclose(b[-1],primary.loc[model,"coefficient"],rtol=1e-10,atol=1e-12)
        assert n==primary.loc[model,"n"]
        if model=="2SLS":
            trusted = IV2SLS(y,x,d,z).fit(cov_type="clustered",clusters=np.column_stack([team,date]),debiased=True)
            trusted_cov = trusted.cov.to_numpy()*(n-design.shape[1])/(n-k)
            assert np.allclose(cov,trusted_cov,rtol=1e-7,atol=1e-9)
        rows.append(dict(league="MLB", specification="main_inference_sensitivity",model=model,n=n,
                         coefficient=float(b[-1]),standard_error=se,ci_low=float(b[-1]-crit*se),ci_high=float(b[-1]+crit*se),
                         p_value=float(2*stats.t.sf(abs(b[-1]/se),df)),unit=primary.loc[model,"unit"],
                         home_franchise_clusters=nteam,date_clusters=ndate,t_df=df,full_model_rank=k,
                         two_way_clustered_Wald_F=float((b[-1]/se)**2) if model=="first_stage" else np.nan,
                         original_home_team_clusters=int(primary.loc[model,"home_team_clusters"]),
                         original_standard_error=float(primary.loc[model,"standard_error"]),
                         cluster_mapping="FLO+MIA; MON+WAS; all other raw home IDs unchanged"))
    result = pd.DataFrame(rows)
    result.to_csv(OUT/"franchise_cluster_sensitivity.csv",index=False)
    after = {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    assert before==after, "Primary output changed"
    note = ["# MLB franchise-cluster inference sensitivity", "",
            "This is an inference audit prompted by the source-ID review, after primary estimation; it is not selected by outcome significance. Primary model_results.csv and its other saved outputs are unchanged (hashes verified).", "",
            "Merge FLO and MIA into one home-franchise cluster and MON and WAS into another. All other home IDs remain distinct. These mappings consolidate renamed/relocated franchise histories. Keep date clusters, sample, point estimates, team-season effects, and exogenous controls exactly as in the main specification. Cluster count falls from 32 raw codes to 30 home franchises; dates remain 3,392. The t reference df becomes 29. CGM/CR1 formula and full absorbed-FE rank correction are unchanged.", "",
            "| Equation | Estimate | Alternate SE | Alternate 95% CI |", "|---|---:|---:|---:|"]
    for _,v in result.iterrows():
        scale = 1000 if v.model=="first_stage" else 100
        label = "FS (attendees/weekend)" if v.model=="first_stage" else ("RF (home-win pp/weekend)" if v.model=="reduced_form" else v.model+" (home-win pp/1,000)")
        note.append(f"| {label} | {v.coefficient*scale:.4f} | {v.standard_error*scale:.4f} | [{v.ci_low*scale:.4f}, {v.ci_high*scale:.4f}] |")
    wald = result.loc[result.model.eq("first_stage"),"two_way_clustered_Wald_F"].iloc[0]
    note += ["",f"Alternate first-stage two-way clustered Wald F = {wald:.3f}; classical partial F remains unchanged because clustering does not alter the homoskedastic calculation.","",
             "All primary point estimates match to numerical precision. The 2SLS covariance also matches linearmodels IV2SLS after matching absorbed-FE degrees of freedom. Few home-franchise clusters, away-team dependence, and unresolved weekend exclusion remain limitations.","",
             "Reproduce: python scripts/second_stage_update/franchise_cluster_sensitivity.py"]
    (OUT/"franchise_cluster_sensitivity.md").write_text("\n".join(note)+"\n",encoding="utf-8")
    (OUT/"franchise_cluster_sensitivity_provenance.json").write_text(json.dumps({
        "source_commit":"51c94a98731180e5be3415892c6846a0590f0250",
        "mapping":{"FLO":"FLO_MIA","MIA":"FLO_MIA","MON":"MON_WAS","WAS":"MON_WAS"},
        "primary_files_unchanged_sha256":before,"script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "trusted_iv_covariance_match":True},indent=2),encoding="utf-8")
    print(result.to_string(index=False))


if __name__=="__main__":
    main()
