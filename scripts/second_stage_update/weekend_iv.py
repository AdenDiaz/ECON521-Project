"""New, exploratory weekend-IV extension; no historical files are overwritten.

From repository root: python scripts/second_stage_update/weekend_iv.py
Dependencies and exact versions are in requirements.lock.txt beside this file.
Specification was fixed in analysis_plan.md before outcome regressions ran.
"""
from __future__ import annotations

import hashlib
import json
import platform
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import patsy
import pyhdfe
from scipy import linalg, sparse, stats
from scipy.sparse.csgraph import connected_components

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "second_stage_update"
SOURCE_COMMIT = "51c94a98731180e5be3415892c6846a0590f0250"
BASE_CONTROLS = ("home_rest_days + away_rest_days + home_prev_win + "
                 "away_prev_win + home_prev_margin_signed + away_prev_margin_signed")


def canon_id(values):
    return values.astype("string").str.replace(r"\.0$", "", regex=True)


def parse_clock(value):
    match = re.fullmatch(r"(\d{1,2}):(\d{2})(AM|PM)", str(value).strip().upper())
    if not match:
        return np.nan
    h, m, ap = int(match[1]), int(match[2]), match[3]
    if not 1 <= h <= 12 or m > 59:
        return np.nan
    return (h % 12 + (12 if ap == "PM" else 0)) * 60 + m


def load_league(league):
    """Validate one-to-one joins and construct pregame controls without new fetches."""
    clean = pd.read_csv(ROOT / "Data/processed" / f"{league.lower()}_games_clean.csv", low_memory=False)
    clean.game_date = pd.to_datetime(clean.game_date)
    clean.game_id = canon_id(clean.game_id)
    assert not clean.game_id.duplicated().any()
    assert not clean.source_row_number.duplicated().any()
    window = clean.loc[clean.game_date.dt.year.between(2001, 2019)]
    raw = pd.read_csv(ROOT / "Data/raw" / f"{league} Data.csv", low_memory=False)
    raw["source_row_number"] = np.arange(1, len(raw) + 1)
    raw_id = "gid" if league == "MLB" else "gameId"
    raw["raw_game_id"] = canon_id(raw[raw_id])
    base = pd.read_csv(ROOT / "Data/processed" / f"{league.lower()}_first_stage_sample.csv", low_memory=False)
    base.game_id = canon_id(base.game_id)
    assert not base.game_id.duplicated().any()
    assert not base.source_row_number.duplicated().any()
    for c in ["game_date", "home_prev_game_date", "away_prev_game_date"]:
        base[c] = pd.to_datetime(base[c])
    assert base.game_date.dt.year.between(2001, 2019).all()
    raw_cols = ["source_row_number", "raw_game_id"] + (["starttime", "number", "daynight"] if league == "MLB" else ["gameDate"])
    base = base.merge(raw[raw_cols], on="source_row_number", how="left", validate="one_to_one", indicator=True)
    assert base._merge.eq("both").all()
    assert base.game_id.eq(base.raw_game_id).all()
    base = base.drop(columns="_merge")
    assert base.attendance.gt(0).all() and base.attendance_quality.eq("valid").all()
    outcome = np.where(base.home_score.gt(base.away_score), 1., np.where(base.home_score.lt(base.away_score), 0., .5))
    assert np.allclose(outcome, base.home_win)
    hist = clean.set_index("game_id")
    assert base.home_team_id.ne(base.away_team_id).all()
    bad_prior = {}
    for side in ["home", "away"]:
        pid = canon_id(base[f"{side}_prev_game_id"])
        assert pid.isin(hist.index).all()
        team = base[f"{side}_team_id"].astype("string")
        phome = pid.map(hist.home_team_id.astype("string"))
        paway = pid.map(hist.away_team_id.astype("string"))
        assert (team.eq(phome) | team.eq(paway)).all()
        assert pid.map(hist.season_id).eq(base.season_id).all()
        assert pid.map(hist.game_date).eq(base[f"{side}_prev_game_date"]).all()
        assert base[f"{side}_prev_game_date"].le(base.game_date).all()
        same_day = base[f"{side}_prev_game_date"].eq(base.game_date)
        if same_day.any():
            assert pid.map(hist.game_order).loc[same_day].lt(base.loc[same_day, "game_order"]).all()
        prior_result = pid.map(hist.home_win).astype(float)
        prior_margin = pid.map(hist.score_margin).astype(float)
        invalid_prior = prior_result.eq(.5) if league == "NBA" else pd.Series(False, index=base.index)
        bad_prior[side] = int(invalid_prior.sum())
        prior_result.loc[invalid_prior] = np.nan
        prior_margin.loc[invalid_prior] = np.nan
        base[f"{side}_prev_win"] = np.where(team.eq(phome), prior_result, 1-prior_result)
        base[f"{side}_prev_margin_signed"] = np.where(team.eq(phome), prior_margin, -prior_margin)
        gap = (base.game_date.dt.normalize() - base[f"{side}_prev_game_date"].dt.normalize()).dt.days
        base[f"{side}_rest_days"] = (gap-1).clip(lower=0)
    if league == "MLB":
        minute = base.starttime.map(parse_clock)
        base["doubleheader"] = pd.to_numeric(base.number, errors="coerce").gt(0)
    else:
        time = pd.to_datetime(base.gameDate)
        assert time.eq(base.game_date).all()
        minute = time.dt.hour*60 + time.dt.minute
        base["doubleheader"] = False
    base["game_hour"] = minute.floordiv(60).astype("Int64").astype("string").fillna("Unknown").astype(str)
    base["date_key"] = base.game_date.dt.strftime("%Y-%m-%d")
    base["year_month"] = base.game_date.dt.strftime("%Y-%m")
    base["month"] = base.game_date.dt.month.astype(str)
    iso = base.game_date.dt.isocalendar()
    base["year_week"] = iso.year.astype(str) + "-" + iso.week.astype(str).str.zfill(2)
    base["weekend"] = base.game_date.dt.day_of_week.ge(5).astype(int)
    base["attendance_1000"] = base.attendance / 1000
    base["home_season"] = base.home_team_id.astype(str) + "|" + base.season_id.astype(str)
    base["away_season"] = base.away_team_id.astype(str) + "|" + base.season_id.astype(str)
    regular = base.game_type.astype(str).str.casefold().isin(["regular", "regular season"])
    decisive = base.home_win.isin([0, 1])
    controls_ok = base[["home_rest_days", "away_rest_days", "home_prev_win", "away_prev_win", "home_prev_margin_signed", "away_prev_margin_signed"]].notna().all(axis=1)
    main = base.loc[regular & decisive & controls_ok].copy().reset_index(drop=True)
    audit = {
        "league": league, "clean_rows_full_source": len(clean), "clean_rows_2001_2019": len(window),
        "clean_unique_game_ids": bool(not clean.game_id.duplicated().any()),
        "clean_unique_source_rows": bool(not clean.source_row_number.duplicated().any()),
        "window_missing_attendance": int(window.attendance.isna().sum()),
        "window_positive_attendance": int(window.attendance.gt(0).sum()),
        "window_missing_outcome": int(window.home_win.isna().sum()),
        "window_tied_scores": int(window.home_win.eq(.5).sum()),
        "first_stage_rows": len(base), "regular_first_stage_rows": int(regular.sum()),
        "regular_tied_scores_excluded": int((regular & ~decisive).sum()),
        "regular_decisive_rows_missing_lag_controls_excluded": int((regular & decisive & ~controls_ok).sum()),
        "bad_nba_prior_tied_scores_by_side": bad_prior,
        "main_n": len(main), "main_date_min": str(main.game_date.min()), "main_date_max": str(main.game_date.max()),
        "main_season_ids": sorted(main.season_id.unique().tolist()),
        "raw_join_match_rate": 1., "raw_id_match_rate": 1., "prior_join_match_rate": 1.,
        "all_prior_games_same_season_and_chronological": True,
        "main_missing_start_hour": int(main.game_hour.eq("Unknown").sum()),
        "main_doubleheader_rows": int(main.doubleheader.sum()),
        "main_weekend_n": int(main.weekend.sum()), "main_weekday_n": int(main.weekend.eq(0).sum()),
        "main_attendance_mean": float(main.attendance.mean()), "main_attendance_sd": float(main.attendance.std()),
        "main_home_win_mean": float(main.home_win.mean()),
        "main_weekend_raw_mean_attendance": float(main.loc[main.weekend.eq(1), "attendance"].mean()),
        "main_weekday_raw_mean_attendance": float(main.loc[main.weekend.eq(0), "attendance"].mean()),
        "ties": base.loc[~decisive, ["game_id", "date_key", "home_score", "away_score", "attendance"]].to_dict("records"),
        "attendance_units": "recorded persons; no stadium-capacity normalization or paid-versus-present validation",
        "weekend_definition": "stored calendar game date Saturday/Sunday; no timezone correction",
        "game_hour_caveat": "recorded start hour, source does not establish scheduled versus realized time or timezone",
    }
    return main, audit


def codes(x):
    a, levels = pd.factorize(x, sort=True)
    return a.astype(np.int64), len(levels)


def fe_rank(h, a):
    """Exact rank of two sets of categorical effects via bipartite components."""
    nh, na = h.max()+1, a.max()+1
    graph = sparse.coo_matrix((np.ones(len(h)), (h, a+nh)), shape=(nh+na, nh+na))
    ncomp = connected_components(graph+graph.T, directed=False, return_labels=False)
    return int(nh+na-ncomp)


def grouped_meat(score, g):
    g, n = codes(g)
    sums = np.zeros((n, score.shape[1]))
    np.add.at(sums, g, score)
    return sums.T @ sums, n


def cluster_cov(score, bread, team, date, k_full):
    """CGM inclusion-exclusion, CR1 per dimension, exact full model rank."""
    n = len(team)
    meat = np.zeros((score.shape[1], score.shape[1]))
    groups = [team, date, pd.MultiIndex.from_arrays([team, date])]
    for sign, g in zip([1, 1, -1], groups):
        component, ng = grouped_meat(score, g)
        meat += sign * (ng/(ng-1)) * ((n-1)/(n-k_full)) * component
    return bread @ meat @ bread.T


def estimate(data, league, spec):
    calendar = {"main": "year_month", "pooled_month": "month", "calendar_week": "year_week", "no_doubleheaders": "year_month", "recorded_hour": "year_month"}[spec]
    if spec == "no_doubleheaders":
        data = data.loc[~data.doubleheader].copy().reset_index(drop=True)
    h, nh = codes(data.home_season)
    a, na = codes(data.away_season)
    rf = fe_rank(h, a)
    form = "0 + C(" + calendar + ") + " + BASE_CONTROLS
    if spec == "recorded_hour":
        form += " + C(game_hour)"
    controls = patsy.dmatrix(form, data, return_type="dataframe")
    matrix = np.column_stack([data.home_win, data.attendance_1000, data.weekend, controls])
    absorber = pyhdfe.create(np.column_stack([h, a]), drop_singletons=False, compute_degrees=False,
                            residualize_method="map", options={"tol": 1e-10, "iteration_limit": 100000})
    residualized = absorber.residualize(matrix.astype(float))
    y, d, z = residualized[:, 0], residualized[:, 1], residualized[:, 2]
    rawx = residualized[:, 3:]
    _, r, pivot = linalg.qr(rawx, mode="economic", pivoting=True)
    rankx = int((np.abs(np.diag(r)) > 1e-8).sum())
    x = rawx[:, pivot[:rankx]]
    assert np.linalg.matrix_rank(np.column_stack([x, z])) == rankx+1, "weekend absorbed"
    n = len(y)
    k = rf + rankx + 1
    team, nteam = codes(data.home_team_id)
    date, ndate = codes(data.date_key)
    df = min(nteam, ndate)-1
    crit = stats.t.ppf(.975, df)
    rows = []
    results = {}
    for model, dep, reg in [("OLS", y, d), ("first_stage", d, z), ("reduced_form", y, z)]:
        design = np.column_stack([x, reg])
        bread = np.linalg.inv(design.T @ design)
        b = bread @ design.T @ dep
        u = dep - design @ b
        cov = cluster_cov(design*u[:, None], bread, team, date, k)
        se = np.sqrt(cov[-1, -1])
        classical_se = np.sqrt((u@u)/(n-k) * bread[-1, -1])
        results[model] = {"coef": b[-1], "u": u, "cov": cov, "design": design, "bread": bread}
        rows.append(dict(league=league, specification=spec, model=model, n=n, coefficient=float(b[-1]),
                         standard_error=float(se), ci_low=float(b[-1]-crit*se), ci_high=float(b[-1]+crit*se),
                         p_value=float(2*stats.t.sf(abs(b[-1]/se), df)),
                         unit="home-win probability per 1,000 attendees" if model=="OLS" else ("1,000 attendees for weekend" if model=="first_stage" else "home-win probability for weekend"),
                         home_team_clusters=nteam, date_clusters=ndate, t_df=df, fe_rank=rf, residual_control_rank=rankx,
                         full_model_rank=k, classical_partial_F=float((b[-1]/classical_se)**2) if model=="first_stage" else np.nan,
                         two_way_clustered_Wald_F=float((b[-1]/se)**2) if model=="first_stage" else np.nan))
    # Exactly identified 2SLS after absorbing the same exogenous effects.
    xx = np.column_stack([x, d])
    zz = np.column_stack([x, z])
    projection = zz @ np.linalg.solve(zz.T@zz, zz.T@xx)
    bread = np.linalg.inv(xx.T@projection)
    b = bread @ projection.T @ y
    structural_u = y-xx@b
    cov = cluster_cov(projection*structural_u[:, None], bread, team, date, k)
    se = np.sqrt(cov[-1, -1])
    assert np.isclose(b[-1], results["reduced_form"]["coef"] / results["first_stage"]["coef"], rtol=1e-8)
    if spec == "main":
        # Independent trusted-library check. Its debiasing omits absorbed FE;
        # rescale only the residual df factor to include our exact full rank.
        from linearmodels.iv import IV2SLS
        trusted = IV2SLS(y, x, d, z).fit(cov_type="clustered", clusters=np.column_stack([team, date]), debiased=True)
        trusted_cov = trusted.cov.to_numpy() * (n-xx.shape[1])/(n-k)
        assert np.allclose(trusted.params.to_numpy(), b, rtol=1e-7, atol=1e-9)
        assert np.allclose(trusted_cov, cov, rtol=1e-7, atol=1e-9)
        (OUT/f"{league.lower()}_trusted_library_check.json").write_text(json.dumps({
            "library": "linearmodels IV2SLS", "coefficient_match": True,
            "all_covariance_elements_match_after_full_FE_df_correction": True,
            "coefficient_max_absolute_error": float(np.max(np.abs(trusted.params.to_numpy()-b))),
            "covariance_max_absolute_error": float(np.max(np.abs(trusted_cov-cov)))}, indent=2), encoding="utf-8")
    rows.append(dict(league=league, specification=spec, model="2SLS", n=n, coefficient=float(b[-1]), standard_error=float(se),
                     ci_low=float(b[-1]-crit*se), ci_high=float(b[-1]+crit*se), p_value=float(2*stats.t.sf(abs(b[-1]/se), df)),
                     unit="home-win probability per 1,000 attendees", home_team_clusters=nteam, date_clusters=ndate,
                     t_df=df, fe_rank=rf, residual_control_rank=rankx, full_model_rank=k,
                     classical_partial_F=np.nan, two_way_clustered_Wald_F=np.nan))
    # Joint covariance of RF and FS coefficients from common cluster moments.
    zr = z - x @ np.linalg.lstsq(x, z, rcond=None)[0]
    ar_score = np.column_stack([zr*results["reduced_form"]["u"], zr*results["first_stage"]["u"]])
    ar_cov = cluster_cov(ar_score, np.eye(2)/(zr@zr), team, date, k)
    rho, pi = results["reduced_form"]["coef"], results["first_stage"]["coef"]
    # AR acceptance inequality (rho-b*pi)^2 <= critical_t^2 Var(rho-b*pi).
    A = pi*pi-crit*crit*ar_cov[1, 1]
    B = -2*rho*pi+2*crit*crit*ar_cov[0, 1]
    C = rho*rho-crit*crit*ar_cov[0, 0]
    disc = B*B-4*A*C
    if disc >= 0:
        roots = sorted([(-B-np.sqrt(disc))/(2*A), (-B+np.sqrt(disc))/(2*A)])
        ar_set = {"type": "bounded_interval" if A>0 else "disjoint_unbounded", "endpoints": [float(v) for v in roots]}
    else:
        ar_set = {"type": "all_real" if A<0 else "empty", "endpoints": []}
    ar = dict(league=league, specification=spec, confidence_level=.95, test="single-instrument two-way clustered Anderson-Rubin t/F inversion",
              coefficient_units="probability per 1,000 attendees", t_df=df, confidence_set=ar_set,
              zero_null_p=float(2*stats.t.sf(abs(rho/np.sqrt(ar_cov[0, 0])), df)),
              covariance_rf_fs=ar_cov.tolist(), quadratic=[float(A), float(B), float(C)],
              caveat="weak-IV robust conditional on valid instrument; cluster asymptotics with few home-team clusters")
    fs = next(row for row in rows if row["model"]=="first_stage")
    fs["partial_R_squared"] = float((zr@d)**2/((zr@zr)*((d-x@np.linalg.lstsq(x,d,rcond=None)[0])@(d-x@np.linalg.lstsq(x,d,rcond=None)[0]))))
    fs["residualized_weekend_variance"] = float(np.mean(zr*zr))
    # Sample manifest supports reproducible common-sample checks without raw duplication.
    manifest = data[["game_id", "source_row_number", "date_key", "season_id", "home_team_id", "away_team_id", "attendance", "home_win", "weekend"]].copy()
    manifest.to_csv(OUT/f"{league.lower()}_{spec}_sample_manifest.csv", index=False)
    return rows, ar


def nfl_audit():
    f = pd.read_csv(ROOT/"Data/processed/nfl_games_clean.csv")
    date = pd.to_datetime(f.game_date)
    weekend = date.dt.day_of_week.ge(5)
    return dict(n=len(f), attendance_valid=int(f.attendance.gt(0).sum()), decisive=int(f.home_win.isin([0,1]).sum()),
                ties=int(f.home_win.eq(.5).sum()), missing_outcomes=int(f.home_win.isna().sum()),
                weekend_n=int(weekend.sum()), weekday_n=int((~weekend).sum()),
                season_min=int(f.season_id.min()), season_max=int(f.season_id.max()),
                role="calibration only; raw game outcomes are available, but no NFL causal model is estimated",
                reason="89% weekend schedule, mostly Sunday; league-specific scheduling/selection controls need separate justification")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows, ars, audits = [], [], []
    for league in ["MLB", "NBA"]:
        data, audit = load_league(league)
        audits.append(audit)
        for spec in ["main", "pooled_month", "calendar_week", "recorded_hour"] + (["no_doubleheaders"] if league=="MLB" else []):
            result, ar = estimate(data, league, spec)
            rows.extend(result)
            ars.append(ar)
            print(league, spec, result[0]["n"], "completed", flush=True)
    results = pd.DataFrame(rows)
    results.to_csv(OUT/"model_results.csv", index=False)
    (OUT/"anderson_rubin.json").write_text(json.dumps(ars, indent=2), encoding="utf-8")
    (OUT/"data_audit.json").write_text(json.dumps({"leagues": audits, "NFL": nfl_audit()}, indent=2, default=str), encoding="utf-8")
    provenance = dict(source_branch="main", source_commit=SOURCE_COMMIT, run_utc=datetime.now(timezone.utc).isoformat(),
                      python=platform.python_version(), analysis_scope="new preliminary second-stage extension",
                      covariance="two-way home-team/date CGM; per-component CR1 G/(G-1)*(N-1)/(N-Kfull); exact two-way FE rank plus residualized control rank and treatment/instrument",
                      inference="t df=min(home-team,date clusters)-1; no small-cluster bootstrap",
                      files={})
    for file in sorted((ROOT/"Data/processed").glob("*csv")):
        provenance["files"][str(file.relative_to(ROOT))] = hashlib.sha256(file.read_bytes()).hexdigest()
    for file in sorted((ROOT/"Data/raw").glob("*csv")):
        provenance["files"][str(file.relative_to(ROOT))] = hashlib.sha256(file.read_bytes()).hexdigest()
    for file in [Path(__file__), Path(__file__).with_name("analysis_plan.md"), Path(__file__).with_name("requirements.lock.txt")]:
        provenance["files"][str(file.relative_to(ROOT))] = hashlib.sha256(file.read_bytes()).hexdigest()
    (OUT/"provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    print(results[["league", "specification", "model", "n", "coefficient", "standard_error", "classical_partial_F", "two_way_clustered_Wald_F"]].to_string(index=False))


if __name__ == "__main__":
    main()
