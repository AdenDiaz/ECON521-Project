"""Recheck baseline-strong alternatives with team-season and exact-date FEs.

Date-level calendar instruments are recorded as absorbed, because exact-date
effects remove all variation in weekend, holiday, and month indicators.
"""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
import patsy
import pyhdfe
import statsmodels.api as sm
from scipy.stats import t as student_t
from statsmodels.stats.sandwich_covariance import cov_cluster_2groups

import expanded_iv_screen as expanded

ROOT = Path(__file__).resolve().parents[1]
GRID = ROOT / "results" / "instrument_candidates" / "expanded_first_stage_grid.csv"
OUT = ROOT / "results" / "instrument_candidates" / "team_season_date_fe_robustness.csv"
DATE_LEVEL = {
    "weekend", "saturday", "sunday", "friday", "opening_month", "late_season_month",
    "us_federal_holiday", "christmas", "july_fourth",
}
FORM = (
    "0 + C(game_type) + C(game_hour) + home_rest_days + away_rest_days + "
    "home_prev_win + away_prev_win + home_prev_margin_signed + away_prev_margin_signed"
)


def _codes(values: pd.Series) -> tuple[np.ndarray, int]:
    codes, levels = pd.factorize(values, sort=True)
    return codes.astype(np.int64), len(levels)


def _fit(frame: pd.DataFrame, candidate: str) -> dict[str, object] | None:
    if candidate in DATE_LEVEL:
        return {
            "candidate": candidate, "n": len(frame), "status": "absorbed by exact-date fixed effects",
            "team_date_two_way_Wald_F": np.nan,
        }
    z = pd.to_numeric(frame[candidate], errors="coerce")
    y = pd.to_numeric(frame.attendance, errors="coerce")
    formula = FORM
    if candidate in {"day_game", "afternoon_start", "late_start"}:
        formula = FORM.replace(" + C(game_hour)", "")
    controls = patsy.dmatrix(formula, frame, return_type="dataframe")
    valid = z.notna() & y.notna() & controls.notna().all(axis=1)
    if valid.sum() < 100 or z.loc[valid].nunique() < 2:
        return {"candidate": candidate, "n": int(valid.sum()), "status": "insufficient variation", "team_date_two_way_Wald_F": np.nan}
    data = frame.loc[valid]
    matrix = np.column_stack([y.loc[valid].to_numpy(float), z.loc[valid].to_numpy(float), controls.loc[valid].to_numpy(float)])
    home_season, n_hs = _codes(data.home_team_id.astype(str) + "|" + data.season_id.astype(str))
    away_season, n_as = _codes(data.away_team_id.astype(str) + "|" + data.season_id.astype(str))
    date, n_date = _codes(data.date_key)
    absorber = pyhdfe.create(
        np.column_stack([home_season, away_season, date]), drop_singletons=False,
        compute_degrees=False, residualize_method="map",
        options={"transform": "symmetric", "acceleration": "cg", "tol": 1e-10, "iteration_limit": 100000},
    )
    matrix = absorber.residualize(matrix)
    design = np.column_stack([matrix[:, 2:], matrix[:, 1]])
    model = sm.OLS(matrix[:, 0], design).fit()
    team, n_team = _codes(data.home_team_id)
    covariance, _, _ = cov_cluster_2groups(model, team, date, use_correction=True)
    pos = design.shape[1] - 1
    coef = float(model.params[pos])
    se = float(np.sqrt(max(covariance[pos, pos], 0.0)))
    t_stat = coef / se if se > 0 else np.nan
    return {
        "candidate": candidate, "n": int(valid.sum()), "status": "estimated",
        "home_teams": n_team, "date_clusters": n_date,
        "coefficient_attendance": coef,
        "partial_F_classical": float((coef / model.bse[pos]) ** 2),
        "team_date_two_way_Wald_F": float(t_stat**2),
        "p_team_date_two_way": float(2 * student_t.sf(abs(t_stat), min(n_team, n_date) - 1)),
        "home_team_season_groups": n_hs, "away_team_season_groups": n_as,
        "fixed_effects": "home-team x season; away-team x season; exact date",
        "controls": formula,
    }


def main() -> None:
    baseline = pd.read_csv(GRID)
    selected = baseline.loc[baseline.two_way_cluster_Wald_F_team_date.gt(10)].drop_duplicates(["league", "candidate"])
    rows = []
    for league in ("MLB", "NBA"):
        frame = expanded.load_league(league)
        for candidate in selected.loc[selected.league.eq(league), "candidate"].astype(str):
            row = _fit(frame, candidate)
            if row:
                row["league"] = league
                rows.append(row)
    result = pd.DataFrame(rows).sort_values(["league", "team_date_two_way_Wald_F"], ascending=[True, False], na_position="last")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT, index=False)
    print(result[["league", "candidate", "n", "status", "coefficient_attendance", "partial_F_classical", "team_date_two_way_Wald_F"]].to_string(index=False))
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
