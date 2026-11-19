"""Reproduce trusted-library checks without rerunning/changing saved analyses.

From repository root: python scripts/second_stage_update/validate_main.py
Writes only mlb_trusted_library_check.json and nba_trusted_library_check.json.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import patsy
import pyhdfe
from scipy import linalg
from linearmodels.iv import IV2SLS

from weekend_iv import OUT, BASE_CONTROLS, load_league, codes, fe_rank, cluster_cov


def validate(league, saved):
    data, _ = load_league(league)
    home, _ = codes(data.home_season)
    away, _ = codes(data.away_season)
    controls = patsy.dmatrix("0 + C(year_month) + " + BASE_CONTROLS, data, return_type="dataframe")
    raw = np.column_stack([data.home_win, data.attendance_1000, data.weekend, controls]).astype(float)
    absorber = pyhdfe.create(np.column_stack([home,away]), drop_singletons=False, compute_degrees=False,
                            residualize_method="map", options={"tol":1e-10,"iteration_limit":100000})
    residualized = absorber.residualize(raw)
    y,d,z = residualized[:,0],residualized[:,1],residualized[:,2]
    rawx = residualized[:,3:]
    _,r,pivot = linalg.qr(rawx,mode="economic",pivoting=True)
    rank_x = int((np.abs(np.diag(r))>1e-8).sum())
    x = rawx[:,pivot[:rank_x]]
    design = np.column_stack([x,d])
    instruments = np.column_stack([x,z])
    projected = instruments @ np.linalg.solve(instruments.T@instruments,instruments.T@design)
    bread = np.linalg.inv(design.T@projected)
    coefficient = bread@projected.T@y
    structural_residual = y-design@coefficient
    team, nteam = codes(data.home_team_id)
    date, ndate = codes(data.date_key)
    n = len(data)
    k = fe_rank(home,away)+rank_x+1
    covariance = cluster_cov(projected*structural_residual[:,None],bread,team,date,k)
    trusted = IV2SLS(y,x,d,z).fit(cov_type="clustered",clusters=np.column_stack([team,date]),debiased=True)
    # Library sees the absorbed data, so match its residual-df correction to
    # the exact rank of the original model including both sets of absorbed FE.
    trusted_covariance = trusted.cov.to_numpy()*(n-design.shape[1])/(n-k)
    assert np.allclose(coefficient,trusted.params.to_numpy(),rtol=1e-7,atol=1e-9)
    assert np.allclose(covariance,trusted_covariance,rtol=1e-7,atol=1e-9)
    row = saved.loc[saved.league.eq(league)&saved.specification.eq("main")&saved.model.eq("2SLS")].iloc[0]
    assert int(row.n)==n
    assert np.isclose(row.coefficient,coefficient[-1],rtol=1e-10,atol=1e-12)
    assert np.isclose(row.standard_error,np.sqrt(covariance[-1,-1]),rtol=1e-10,atol=1e-12)
    result = dict(library="linearmodels IV2SLS",coefficient_match=True,
                  all_covariance_elements_match_after_full_FE_df_correction=True,
                  coefficient_max_absolute_error=float(np.max(np.abs(trusted.params.to_numpy()-coefficient))),
                  covariance_max_absolute_error=float(np.max(np.abs(trusted_covariance-covariance))),
                  saved_model_results_coefficient_match=True,saved_model_results_standard_error_match=True,
                  n=n,home_team_clusters=nteam,date_clusters=ndate,full_model_rank=k,
                  reproduction_command="python scripts/second_stage_update/validate_main.py",
                  validator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (OUT/f"{league.lower()}_trusted_library_check.json").write_text(json.dumps(result,indent=2),encoding="utf-8")


def main():
    protected = list(OUT.glob("*.csv"))+[OUT/"anderson_rubin.json",OUT/"data_audit.json",OUT/"provenance.json"]
    before = {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    saved = pd.read_csv(OUT/"model_results.csv")
    for league in ["MLB","NBA"]:
        validate(league,saved)
        print(league,"main coefficient/covariance validation passed",flush=True)
    assert before=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    print("All saved estimation outputs remain unchanged",flush=True)


if __name__=="__main__":
    main()
