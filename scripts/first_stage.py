"""Calibrate previous-game closeness and estimate first-stage attendance models.

No home-win outcome regression is run here. The percentile grid spans the
5th through 95th percentiles, plus the exact NFL-derived anchor, to check
whether any plausible margin threshold yields a relevant first stage.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import patsy
import scipy.stats as st
import statsmodels.api as sm
from statsmodels.stats.sandwich_covariance import cov_cluster

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "Data" / "processed"
RESULTS = ROOT / "results" / "first_stage"
NBA_MAX_ATTENDANCE = 100_000
GRID = [i / 100 for i in range(5, 100, 5)]
ANCHOR_START_YEAR = 2000
ANCHOR_END_YEAR = 2023
ANCHOR_MARGIN = 3
PRIMARY_SCOPE = "1960_plus"


def load_clean(league: str) -> pd.DataFrame:
    frame = pd.read_csv(DATA / f"{league.lower()}_games_clean.csv", parse_dates=["game_date"])
    for column in ["attendance", "abs_margin", "home_prev_game_abs_margin", "away_prev_game_abs_margin"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["season_id"] = pd.to_numeric(frame["season_id"], errors="coerce").astype("Int64")
    return frame


def empirical_cutoff(values: pd.Series, percentile: float) -> float:
    """Return the smallest observed margin whose empirical CDF reaches p."""
    ordered = np.sort(pd.to_numeric(values, errors="coerce").dropna().to_numpy(dtype=float))
    if not len(ordered):
        raise ValueError("Cannot set a closeness cutoff without valid game margins.")
    rank = max(0, min(len(ordered) - 1, int(np.ceil(percentile * len(ordered))) - 1))
    return float(ordered[rank])


def _reference_nfl() -> tuple[dict[str, object], float, pd.DataFrame]:
    nfl = load_clean("NFL")
    reference = nfl.loc[
        nfl["season_id"].between(ANCHOR_START_YEAR, ANCHOR_END_YEAR)
        & nfl["abs_margin"].notna()
    ].copy()
    season_counts = reference.groupby("season_id").size()
    # The source is a 16-game-era regular-season file: 256 games is a complete
    # 32-team season. Incomplete seasons are retained for the main anchor and
    # removed only for the reported sensitivity check.
    complete_seasons = season_counts.index[season_counts.eq(256)]
    complete = reference.loc[reference["season_id"].isin(complete_seasons)]
    share = float(reference["abs_margin"].le(ANCHOR_MARGIN).mean())
    complete_share = float(complete["abs_margin"].le(ANCHOR_MARGIN).mean())
    anchor = {
        "requested_season_start": ANCHOR_START_YEAR,
        "requested_season_end": ANCHOR_END_YEAR,
        "observed_season_start": int(reference["season_id"].min()),
        "observed_season_end": int(reference["season_id"].max()),
        "observed_date_start": reference["game_date"].min().date().isoformat(),
        "observed_date_end": reference["game_date"].max().date().isoformat(),
        "games_with_valid_margin": int(len(reference)),
        "games_with_abs_margin_le_3": int(reference["abs_margin"].le(ANCHOR_MARGIN).sum()),
        "nfl_anchor_percentile": share,
        "complete_256_game_seasons": ";".join(str(int(x)) for x in complete_seasons),
        "incomplete_season_game_counts": ";".join(
            f"{int(year)}:{int(count)}" for year, count in season_counts.items() if count < 256
        ),
        "complete_seasons_games": int(len(complete)),
        "complete_seasons_share_le_3": complete_share,
    }
    season_table = season_counts.rename("observed_games").reset_index()
    season_table["complete_256_game_season"] = season_table["observed_games"].eq(256)
    return anchor, share, season_table


def _prepare_sample(games: pd.DataFrame, start_year: int | None) -> tuple[pd.DataFrame, pd.Series]:
    if start_year is not None:
        games = games.loc[games["game_date"].dt.year.ge(start_year)].copy()
    margin_distribution = games["abs_margin"].dropna()
    sample = games.loc[
        games["attendance"].notna()
        & games["home_prev_game_abs_margin"].notna()
        & games["away_prev_game_abs_margin"].notna()
    ].copy()
    sample["game_weekday"] = sample["game_date"].dt.dayofweek.astype("string")
    sample["game_month"] = sample["game_date"].dt.month.astype("string")
    sample["season_id"] = sample["season_id"].astype("string")
    sample["game_type"] = sample["game_type"].fillna("Unknown").astype("string")
    for column in ["home_team_id", "away_team_id"]:
        sample[column] = sample[column].astype("string")
    return sample, margin_distribution


def _restriction_matrix(names: list[str], instruments: list[str]) -> np.ndarray:
    matrix = np.zeros((len(instruments), len(names)), dtype=float)
    for row, name in enumerate(instruments):
        matrix[row, names.index(name)] = 1.0
    return matrix


def fit_first_stage(sample: pd.DataFrame, cutoff: float, percentile: float, scope: str) -> dict[str, object]:
    if sample.empty:
        raise ValueError("The first-stage sample is empty after attendance and previous-game eligibility filters.")

    home_close = sample["home_prev_game_abs_margin"].le(cutoff).astype(int)
    away_close = sample["away_prev_game_abs_margin"].le(cutoff).astype(int)
    instrument_frame = pd.DataFrame({
        "home_prev_close": home_close.to_numpy(),
        "away_prev_close": away_close.to_numpy(),
    })
    active = [name for name in instrument_frame if instrument_frame[name].nunique() > 1]

    control_formula = (
        "1 + C(home_team_id) + C(away_team_id) + C(season_id) "
        "+ C(game_type) + C(game_weekday) + C(game_month)"
    )
    controls = patsy.dmatrix(control_formula, sample, return_type="dataframe")
    controls = controls.reset_index(drop=True)
    y = sample["attendance"].to_numpy(dtype=float)
    x = controls.copy()
    if active:
        for name in active:
            x[name] = instrument_frame[name].to_numpy(dtype=float)
    exog = x.to_numpy(dtype=float)
    result = sm.OLS(y, exog, hasconst=True).fit()
    names = list(x.columns)

    home_clusters, home_labels = pd.factorize(sample["home_team_id"], sort=True)
    cluster_df = max(1, len(home_labels) - 1)

    row: dict[str, object] = {
        "scope": scope,
        "league": str(sample["league"].iloc[0]),
        "percentile": float(percentile),
        "margin_cutoff": float(cutoff),
        "n_games_in_margin_distribution": int(sample.attrs.get("margin_count", 0)),
        "n_first_stage_observations": int(len(sample)),
        "n_home_team_clusters": int(len(home_labels)),
        "cluster_variable": "home_team_id",
        "n_control_columns": int(controls.shape[1]),
        "home_prev_close_share": float(home_close.mean()),
        "away_prev_close_share": float(away_close.mean()),
        "home_prev_close_coef": np.nan,
        "home_prev_close_cluster_se": np.nan,
        "away_prev_close_coef": np.nan,
        "away_prev_close_cluster_se": np.nan,
        "active_instruments": len(active),
        "joint_F_classical": np.nan,
        "joint_p_classical": np.nan,
        "joint_F_home_team_cluster": np.nan,
        "joint_p_home_team_cluster": np.nan,
        "home_partial_F_classical": np.nan,
        "away_partial_F_classical": np.nan,
        "home_prev_close_cluster_p": np.nan,
        "away_prev_close_cluster_p": np.nan,
    }
    if not active:
        return row

    restrictions = _restriction_matrix(names, active)
    classic_test = result.f_test(restrictions)
    row["joint_F_classical"] = float(np.asarray(classic_test.fvalue).squeeze())
    row["joint_p_classical"] = float(np.asarray(classic_test.pvalue).squeeze())

    covariance = cov_cluster(result, home_clusters, use_correction=True)
    robust_test = result.f_test(restrictions, cov_p=covariance)
    robust_f = float(np.asarray(robust_test.fvalue).squeeze())
    robust_stat_p = float(st.f.sf(robust_f, len(active), cluster_df)) if robust_f >= 0 else np.nan
    row["joint_F_home_team_cluster"] = robust_f
    row["joint_p_home_team_cluster"] = robust_stat_p

    params = np.asarray(result.params)
    for name in ("home_prev_close", "away_prev_close"):
        if name in names:
            position = names.index(name)
            estimate = float(params[position])
            variance = float(covariance[position, position])
            standard_error = float(np.sqrt(variance)) if variance > 0 else np.nan
            t_value = estimate / standard_error if standard_error and np.isfinite(standard_error) else np.nan
            t_p = float(2 * st.t.sf(abs(t_value), cluster_df)) if np.isfinite(t_value) else np.nan
            row[f"{name}_coef"] = estimate
            row[f"{name}_cluster_se"] = standard_error
            row[f"{name}_cluster_p"] = t_p

    for name, output in [("home_prev_close", "home_partial_F_classical"), ("away_prev_close", "away_partial_F_classical")]:
        if name in names:
            one_restriction = _restriction_matrix(names, [name])
            row[output] = float(np.asarray(result.f_test(one_restriction).fvalue).squeeze())
    return row


def threshold_grid(league: str, games: pd.DataFrame, scope: str, start_year: int | None, percentiles: list[float]) -> tuple[list[dict[str, object]], pd.DataFrame]:
    sample, margin_distribution = _prepare_sample(games, start_year)
    sample.attrs["margin_count"] = len(margin_distribution)
    if not len(margin_distribution):
        raise ValueError(f"{league} has no valid margins for {scope}.")
    rows = []
    for percentile in percentiles:
        cutoff = empirical_cutoff(margin_distribution, percentile)
        result = fit_first_stage(sample, cutoff, percentile, scope)
        result["league"] = league
        result["n_games_in_margin_distribution"] = int(len(margin_distribution))
        result["actual_game_share_at_or_below_cutoff"] = float(margin_distribution.le(cutoff).mean())
        rows.append(result)
        print(
            f"{scope} {league} p={percentile:.4f} cutoff={cutoff:g} "
            f"F={result['joint_F_classical']:.2f} home-team-cluster-p={result['joint_p_home_team_cluster']:.4g}",
            flush=True,
        )
    return rows, sample


def _choose_thresholds(grid: pd.DataFrame, anchor_percentile: float) -> tuple[dict[str, object], str]:
    primary = grid.loc[grid["scope"].eq(PRIMARY_SCOPE)].copy()
    primary["strong_and_significant"] = (
        primary["joint_F_classical"].gt(10)
        & primary["joint_p_home_team_cluster"].lt(0.05)
    )
    common = primary.pivot(index="percentile", columns="league", values="strong_and_significant")
    common_pass = common.index[common.all(axis=1)] if set(common.columns) >= {"MLB", "NBA"} else []
    if len(common_pass):
        selected_p = min(common_pass, key=lambda p: abs(float(p) - anchor_percentile))
        return {"MLB": float(selected_p), "NBA": float(selected_p)}, "common_percentile"

    selected: dict[str, object] = {}
    for league in ("MLB", "NBA"):
        candidates = primary.loc[
            primary["league"].eq(league) & primary["strong_and_significant"]
        ]
        if candidates.empty:
            selected[league] = None
        else:
            chosen = candidates.iloc[(candidates["percentile"] - anchor_percentile).abs().argmin()]
            selected[league] = float(chosen["percentile"])
    return selected, "league_specific" if any(v is not None for v in selected.values()) else "no_strong_threshold_found"


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    nba = load_clean("NBA")
    mlb = load_clean("MLB")
    nfl_anchor, anchor_percentile, nfl_seasons = _reference_nfl()
    pd.DataFrame([nfl_anchor]).to_csv(RESULTS / "nfl_reference.csv", index=False)
    nfl_seasons.to_csv(RESULTS / "nfl_season_coverage.csv", index=False)

    percentiles = sorted(set(GRID + [anchor_percentile]))
    all_rows: list[dict[str, object]] = []
    primary_samples: dict[str, pd.DataFrame] = {}
    for league, games in [("MLB", mlb), ("NBA", nba)]:
        rows, sample = threshold_grid(league, games, PRIMARY_SCOPE, 1960, percentiles)
        all_rows.extend(rows)
        primary_samples[league] = sample

    grid = pd.DataFrame(all_rows).sort_values(["scope", "percentile", "league"])
    grid.to_csv(RESULTS / "common_percentile_grid.csv", index=False)
    selected, selection_mode = _choose_thresholds(grid, anchor_percentile)

    sensitivity_rows: list[dict[str, object]] = []
    full_samples: dict[str, pd.DataFrame] = {}
    for league, games in [("MLB", mlb), ("NBA", nba)]:
        sample, distribution = _prepare_sample(games, None)
        sample.attrs["margin_count"] = len(distribution)
        full_samples[league] = sample
        chosen_p = selected[league]
        p_values = {anchor_percentile}
        if chosen_p is not None:
            p_values.add(float(chosen_p))
        for percentile in sorted(p_values):
            cutoff = empirical_cutoff(distribution, percentile)
            result = fit_first_stage(sample, cutoff, percentile, "full_history_sensitivity")
            result["league"] = league
            result["n_games_in_margin_distribution"] = int(len(distribution))
            result["actual_game_share_at_or_below_cutoff"] = float(distribution.le(cutoff).mean())
            sensitivity_rows.append(result)
    sensitivity = pd.DataFrame(sensitivity_rows)
    sensitivity.to_csv(RESULTS / "full_history_sensitivity.csv", index=False)

    selected_rows = []
    first_stage_rows = []
    for league, games in [("MLB", mlb), ("NBA", nba)]:
        percentile = selected[league]
        if percentile is None:
            percentile = anchor_percentile
            selected_status = "NFL_anchor_retained_no_threshold_met_F10_and_p05"
        else:
            selected_status = f"selected_{selection_mode}"
        sample, distribution = _prepare_sample(games, 1960)
        cutoff = empirical_cutoff(distribution, float(percentile))
        home_share = float(distribution.le(cutoff).mean())
        model_row = grid.loc[
            grid["scope"].eq(PRIMARY_SCOPE)
            & grid["league"].eq(league)
            & np.isclose(grid["percentile"], float(percentile))
        ]
        if model_row.empty:
            model = fit_first_stage(sample, cutoff, float(percentile), PRIMARY_SCOPE)
        else:
            model = model_row.iloc[0].to_dict()
        model["league"] = league
        model["selected_percentile"] = float(percentile)
        model["selected_margin_cutoff"] = float(cutoff)
        model["selected_threshold_status"] = selected_status
        model["actual_game_share_at_or_below_cutoff"] = home_share
        first_stage_rows.append(model)

        current = sample.copy()
        current["home_prev_close"] = current["home_prev_game_abs_margin"].le(cutoff).astype("int8")
        current["away_prev_close"] = current["away_prev_game_abs_margin"].le(cutoff).astype("int8")
        current["close_percentile"] = float(percentile)
        current["home_prev_game_margin_cutoff"] = float(cutoff)
        current["away_prev_game_margin_cutoff"] = float(cutoff)
        current.to_csv(DATA / f"{league.lower()}_first_stage_sample.csv", index=False, date_format="%Y-%m-%d %H:%M:%S")
        selected_rows.append({
            "league": league,
            "selection_mode": selection_mode,
            "selected_percentile": float(percentile),
            "margin_cutoff": float(cutoff),
            "share_of_game_margins_at_or_below_cutoff": home_share,
            "n_current_games_with_attendance_and_both_prior_margins": len(current),
            "n_home_previous_close": int(current["home_prev_close"].sum()),
            "n_away_previous_close": int(current["away_prev_close"].sum()),
            "threshold_status": selected_status,
        })

    selected_frame = pd.DataFrame(selected_rows)
    selected_frame.to_csv(RESULTS / "selected_thresholds.csv", index=False)
    first_stage = pd.DataFrame(first_stage_rows)
    first_stage.to_csv(RESULTS / "selected_first_stage.csv", index=False)

    common_at_anchor = grid.loc[
        grid["scope"].eq(PRIMARY_SCOPE) & np.isclose(grid["percentile"], anchor_percentile)
    ]
    both_anchor_pass = bool(
        len(common_at_anchor) == 2
        and common_at_anchor["joint_F_classical"].gt(10).all()
        and common_at_anchor["joint_p_home_team_cluster"].lt(0.05).all()
    )
    common_success = selection_mode == "common_percentile"
    nfl_incomplete = nfl_anchor["incomplete_season_game_counts"].replace(";", ", ") or "None"
    max_grid = (
        grid.loc[grid["scope"].eq(PRIMARY_SCOPE)]
        .sort_values("joint_F_classical", ascending=False)
        .drop_duplicates("league")
    )
    max_grid_text = "; ".join(
        f"{row.league}: F={row.joint_F_classical:.2f} at p={row.percentile:.0%} (cutoff {row.margin_cutoff:g})"
        for row in max_grid.itertuples()
    )
    anchor_shares = "; ".join(
        f"{row.league}: {row.share_of_game_margins_at_or_below_cutoff:.2%} (cutoff {row.margin_cutoff:g})"
        for row in selected_frame.itertuples()
    )
    full_anchor = sensitivity.loc[np.isclose(sensitivity["percentile"], anchor_percentile)]
    full_anchor_text = "; ".join(
        f"{row.league}: F={row.joint_F_classical:.2f}, clustered p={row.joint_p_home_team_cluster:.3f}"
        for row in full_anchor.itertuples()
    )

    lines = [
        "# Data cleaning and first-stage summary",
        "",
        "## Scope",
        "",
        "This run cleans the three supplied game files, then estimates first-stage attendance regressions for the MLB and NBA only. It does not estimate the home-win outcome equation or a second-stage IV effect.",
        "",
        "The main first-stage screen follows the existing notebook's proposed January 1960 cutoff for both MLB and NBA. Full-history results are reported separately as a sensitivity check because the notebook described that cutoff as provisional.",
        "",
        "## NFL reference coverage",
        "",
        f"The NFL file contains {nfl_anchor['games_with_valid_margin']:,} score-valid rows for seasons {nfl_anchor['observed_season_start']}–{nfl_anchor['observed_season_end']} ({nfl_anchor['observed_date_start']} through {nfl_anchor['observed_date_end']}). It has no season 2000 or seasons 2020–2023. The requested 2000–2023 window therefore contains only the file's observed 2001–2019 games.",
        f"Using |winner score − loser score| ≤ 3, {nfl_anchor['games_with_abs_margin_le_3']:,} of {nfl_anchor['games_with_valid_margin']:,} games are close: {anchor_percentile:.2%}. The cutoff percentile is the share in the lower tail of the absolute-margin distribution. Complete 256-game seasons yield {nfl_anchor['complete_seasons_share_le_3']:.2%}; seasons with fewer than 256 rows: {nfl_incomplete}.",
        "",
        "The same percentile means the MLB/NBA margin cutoff is the empirical inverse-CDF value at this lower-tail share. Discrete scoring means the achieved close-game share may be higher than the target percentile; the output tables report both.",
        "",
        "## First-stage findings",
        "",
        f"NFL-anchor percentile first-stage test passes F > 10 and home-team-cluster p < .05 in both leagues: {both_anchor_pass}.",
        f"Common percentile in the tested 5%–95% grid passes both criteria in both leagues: {common_success}.",
        f"Threshold selection mode: {selection_mode}.",
        f"Largest conventional joint F in the full tested grid: {max_grid_text}.",
        f"At the NFL anchor percentile, the discrete MLB/NBA score distributions yield achieved close-game shares of {anchor_shares}.",
        f"Full-history estimates at the NFL anchor: {full_anchor_text}.",
        "",
        "The selected first-stage model includes home-team, away-team, season, game-type, weekday, and month fixed effects. The excluded instruments are separate indicators for a close immediately previous game by the current home and away teams. Standard errors are clustered by current home team. The conventional joint partial F is reported alongside the home-team-cluster F and p-value.",
        "",
        "No tested threshold from the 5th through 95th percentile meets the F > 10 screen in either league; therefore no league-specific alternative is selected and the NFL anchor is retained for the prepared samples. F > 10 is a relevance screen, not evidence that the exclusion restriction holds. A previous close game can affect later team confidence or performance directly, so the exclusion restriction remains unresolved. No second-stage estimate is included.",
        "",
        "## Cleaning decisions",
        "",
        "- Raw data files are preserved under `Data/raw/`; cleaned files are written to `Data/processed/`.",
        "- Attendance is numeric. Missing, nonnumeric, zero, and negative values are unavailable for the first stage. For NBA only, values below 100 or above 100,000 are flagged as implausible and set missing; the raw files retain the source values.",
        "- Game histories are built before restricting current-game observations to positive attendance. A game with missing attendance can still be the previous game if it has a valid score, date, and team identifiers.",
        "- MLB game IDs' final digit orders validated same-day doubleheaders. Cases with ambiguous same-day order receive no lag instrument for the affected observation.",
        "- NBA preseason games and MLB exhibitions/All-Star games are excluded from the franchise-game history. Playoffs and in-season NBA cup games remain in the data.",
        "- NFL January/February dates are assigned to the calendar year after the season-start year; the season ID remains the source `year` field.",
        "",
        "See `nfl_reference.csv`, `common_percentile_grid.csv`, `selected_thresholds.csv`, `selected_first_stage.csv`, and `full_history_sensitivity.csv` for counts, cutoffs, coefficients, and F statistics.",
        "",
    ]
    (RESULTS / "report.md").write_text("\n".join(lines), encoding="utf-8")

    print("\nThreshold selection:")
    print(selected_frame.to_string(index=False))
    print("\nSelected first-stage F statistics:")
    show_columns = [
        "league", "selected_percentile", "selected_margin_cutoff", "n_first_stage_observations",
        "joint_F_classical", "joint_p_classical", "joint_F_home_team_cluster", "joint_p_home_team_cluster"
    ]
    print(first_stage[show_columns].to_string(index=False))
    print(f"\nWrote first-stage outputs to {RESULTS}")


if __name__ == "__main__":
    main()
