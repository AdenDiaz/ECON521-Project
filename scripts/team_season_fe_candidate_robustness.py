"""Re-estimate strong exploratory IV candidates with team-season fixed effects.

The selected candidate list is mechanical: every candidate with a baseline
home-team/date two-way clustered Wald F above 10 is tested. Models absorb
home-team-by-season and away-team-by-season effects using alternating
projections, then cluster inference by current home team and game date.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import patsy
import statsmodels.api as sm
from scipy.stats import t as student_t
from statsmodels.stats.sandwich_covariance import cov_cluster_2groups

import expanded_iv_screen as expanded

ROOT = Path(__file__).resolve().parents[1]
GRID = ROOT / "results" / "instrument_candidates" / "expanded_first_stage_grid.csv"
OUT = ROOT / "results" / "instrument_candidates" / "team_season_fe_robustness.csv"

FORMULAS = {
    "weekend": "0 + C(game_type) + C(game_month) + C(game_hour) + home_rest_days + away_rest_days + home_prev_win + away_prev_win + home_prev_margin_signed + away_prev_margin_signed",
    "weekday": "0 + C(game_type) + C(game_month) + C(game_hour) + home_rest_days + away_rest_days + home_prev_win + away_prev_win + home_prev_margin_signed + away_prev_margin_signed",
    "day_time": "0 + C(game_type) + C(game_weekday) + C(game_month) + home_rest_days + away_rest_days + home_prev_win + away_prev_win + home_prev_margin_signed + away_prev_margin_signed",
    "month": "0 + C(game_type) + C(game_weekday) + C(game_hour) + home_rest_days + away_rest_days + home_prev_win + away_prev_win + home_prev_margin_signed + away_prev_margin_signed",
    "general": "0 + C(game_type) + C(game_weekday) + C(game_month) + C(game_hour) + home_rest_days + away_rest_days + home_prev_win + away_prev_win + home_prev_margin_signed + away_prev_margin_signed",
    "demand": "0 + C(game_type) + C(game_weekday) + C(game_month) + C(game_hour) + home_rest_days + away_rest_days + home_prev_win + away_prev_win + home_prev_margin_signed + away_prev_margin_signed",
}


def _codes(series: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    code, uniques = pd.factorize(series, sort=True)
    return code.astype(np.int64), uniques


def absorb_two_way(matrix: np.ndarray, group_one: np.ndarray, group_two: np.ndarray, *, tolerance: float = 1e-8, max_iter: int = 1000) -> tuple[np.ndarray, int]:
    groups = []
    for codes in (group_one, group_two):
        counts = np.bincount(codes).astype(float)
        groups.append((codes, counts))
    for iteration in range(1, max_iter + 1):
        previous = matrix.copy()
        for codes, counts in groups:
            for column in range(matrix.shape[1]):
                means = np.bincount(codes, weights=matrix[:, column]) / counts
                matrix[:, column] -= means[codes]
        if np.max(np.abs(matrix - previous)) < tolerance:
            return matrix, iteration
    return matrix, max_iter


def formula_for(candidate: str) -> str:
    if candidate in {"weekend", "saturday", "sunday", "friday"}:
        return FORMULAS["weekend"]
    if candidate in {"day_game", "afternoon_start", "late_start"}:
        return FORMULAS["day_time"]
    if candidate in {"opening_month", "late_season_month"}:
        return FORMULAS["month"]
    if candidate in {"last_home_game_attendance", "mean_prior_5_home_gates", "mean_prior_season_home_gates", "home_prev_game_attendance", "away_last_home_game_attendance"}:
        return FORMULAS["demand"]
    if candidate.endswith("back_to_back") or candidate.endswith("short_rest"):
        return FORMULAS["general"]
    return FORMULAS["general"]


def fit_candidate(frame: pd.DataFrame, league: str, candidate_row: pd.Series) -> dict[str, object] | None:
    candidate = str(candidate_row.candidate)
    variable = pd.to_numeric(frame[candidate], errors="coerce").astype(float)
    outcome = pd.to_numeric(frame.attendance, errors="coerce")
    formula = formula_for(candidate)
    controls = patsy.dmatrix(formula, frame, return_type="dataframe")
    valid = outcome.notna() & variable.notna() & controls.notna().all(axis=1)
    if valid.sum() < 100 or variable.loc[valid].nunique() < 2:
        return None
    data = frame.loc[valid]
    control = controls.loc[valid].to_numpy(dtype=float)
    matrix = np.column_stack([
        outcome.loc[valid].to_numpy(dtype=float),
        variable.loc[valid].to_numpy(dtype=float),
        control,
    ])
    home_season = data.home_team_id.astype(str) + "|" + data.season_id.astype(str)
    away_season = data.away_team_id.astype(str) + "|" + data.season_id.astype(str)
    group_home, home_levels = _codes(home_season)
    group_away, away_levels = _codes(away_season)
    matrix, iterations = absorb_two_way(matrix, group_home, group_away)
    design = np.column_stack([matrix[:, 2:], matrix[:, 1]])
    model = sm.OLS(matrix[:, 0], design).fit()
    team_code, team_levels = _codes(data.home_team_id)
    date_code, date_levels = _codes(data.date_key)
    robust_team = model.get_robustcov_results(
        cov_type="cluster", groups=team_code, use_correction=True, df_correction=True
    )
    cov_both, _, _ = cov_cluster_2groups(model, team_code, date_code, use_correction=True)
    position = design.shape[1] - 1
    coef = float(model.params[position])
    se_classical = float(model.bse[position])
    se_team_date = float(np.sqrt(max(cov_both[position, position], 0.0)))
    df_team_date = min(len(team_levels), len(date_levels)) - 1
    t_team_date = coef / se_team_date if se_team_date > 0 else np.nan
    return {
        "league": league,
        "candidate": candidate,
        "family": candidate_row.family,
        "definition": candidate_row.definition,
        "n": int(valid.sum()),
        "coefficient_attendance": coef,
        "partial_F_classical": float((coef / se_classical) ** 2),
        "home_team_cluster_Wald_F": float(robust_team.tvalues[position] ** 2),
        "p_home_team_cluster": float(robust_team.pvalues[position]),
        "team_date_two_way_Wald_F": float(t_team_date ** 2),
        "p_team_date_two_way": float(2 * student_t.sf(abs(t_team_date), df_team_date)),
        "n_home_team_clusters": int(len(team_levels)),
        "n_date_clusters": int(len(date_levels)),
        "home_team_season_groups": int(len(home_levels)),
        "away_team_season_groups": int(len(away_levels)),
        "alternating_projection_iterations": iterations,
        "controls": formula,
        "exclusion_risk": candidate_row.exclusion_risk,
    }


def main() -> None:
    baseline = pd.read_csv(GRID)
    selected = baseline.loc[baseline.two_way_cluster_Wald_F_team_date.gt(10)].drop_duplicates(["league", "candidate"])
    rows = []
    for league in ("MLB", "NBA"):
        frame = expanded.load_league(league)
        for _, candidate_row in selected.loc[selected.league.eq(league)].iterrows():
            row = fit_candidate(frame, league, candidate_row)
            if row:
                rows.append(row)
    result = pd.DataFrame(rows).sort_values(["league", "team_date_two_way_Wald_F"], ascending=[True, False])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT, index=False)
    print(result[["league", "candidate", "n", "coefficient_attendance", "partial_F_classical", "home_team_cluster_Wald_F", "team_date_two_way_Wald_F", "p_team_date_two_way", "alternating_projection_iterations"]].to_string(index=False))
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
