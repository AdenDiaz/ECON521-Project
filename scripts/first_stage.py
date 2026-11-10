"""Calibrate previous-game closeness and estimate first-stage attendance models.

No home-win outcome regression is run here. The search tests every integer
percentile from 1 through 99, every observed margin-cutoff transition in
either league, and the exact NFL-derived anchor.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import patsy
import scipy.stats as st
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "Data" / "processed"
RESULTS = ROOT / "results" / "first_stage"
GRID = [i / 100 for i in range(1, 100)]
ANCHOR_START_YEAR = 2000
ANCHOR_END_YEAR = 2023
ANCHOR_MARGIN = 3
ANALYSIS_START_YEAR = 2001
ANALYSIS_END_YEAR = 2019
PRIMARY_SCOPE = f"{ANALYSIS_START_YEAR}_{ANALYSIS_END_YEAR}"


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
    # 32-team season. Incomplete seasons remain in the anchor; their counts are
    # reported so the coverage limitation is visible.
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


def _prepare_sample(
    games: pd.DataFrame,
    start_year: int | None,
    end_year: int | None = None,
) -> tuple[pd.DataFrame, pd.Series]:
    if start_year is not None:
        in_window = games["game_date"].dt.year.ge(start_year)
        if end_year is not None:
            in_window &= games["game_date"].dt.year.le(end_year)
        games = games.loc[in_window].copy()
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


def _model_state(sample: pd.DataFrame) -> dict[str, object]:
    """Fit fixed-effect controls once; threshold models use Frisch-Waugh-Lovell residuals."""
    control_formula = (
        "1 + C(home_team_id) + C(away_team_id) + C(season_id) "
        "+ C(game_type) + C(game_weekday) + C(game_month)"
    )
    controls = patsy.dmatrix(control_formula, sample, return_type="dataframe").to_numpy(dtype=float)
    y = sample["attendance"].to_numpy(dtype=float)
    controls_fit = sm.OLS(y, controls, hasconst=True).fit()
    home_clusters, home_labels = pd.factorize(sample["home_team_id"], sort=True)
    return {
        "controls": controls,
        "controls_fit": controls_fit,
        "y_residual": np.asarray(controls_fit.resid, dtype=float),
        "home_clusters": home_clusters.astype(np.int64),
        "home_labels": home_labels,
    }


def fit_first_stage(
    sample: pd.DataFrame,
    cutoff: float,
    percentile: float,
    scope: str,
    model_state: dict[str, object] | None = None,
) -> dict[str, object]:
    if sample.empty:
        raise ValueError("The first-stage sample is empty after attendance and previous-game eligibility filters.")
    if model_state is None:
        model_state = _model_state(sample)

    home_close = sample["home_prev_game_abs_margin"].le(cutoff).to_numpy(dtype=float)
    away_close = sample["away_prev_game_abs_margin"].le(cutoff).to_numpy(dtype=float)
    raw_instruments = np.column_stack([home_close, away_close])
    instrument_names = ["home_prev_close", "away_prev_close"]
    active_positions = [
        position for position in range(raw_instruments.shape[1])
        if np.unique(raw_instruments[:, position]).size > 1
    ]

    controls = model_state["controls"]
    controls_fit = model_state["controls_fit"]
    y_residual = model_state["y_residual"]
    home_clusters = model_state["home_clusters"]
    home_labels = model_state["home_labels"]
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
        "active_instruments": 0,
        "joint_F_classical": np.nan,
        "joint_p_classical": np.nan,
        "joint_F_home_team_cluster": np.nan,
        "joint_p_home_team_cluster": np.nan,
        "home_partial_F_classical": np.nan,
        "away_partial_F_classical": np.nan,
        "home_prev_close_cluster_p": np.nan,
        "away_prev_close_cluster_p": np.nan,
    }
    if not active_positions:
        return row

    pinv_controls = controls_fit.model.pinv_wexog
    residualized = raw_instruments[:, active_positions] - controls @ (pinv_controls @ raw_instruments[:, active_positions])
    # Remove instruments absorbed by fixed effects or collinear with another instrument.
    independent_positions: list[int] = []
    for position in range(residualized.shape[1]):
        candidate = residualized[:, independent_positions + [position]]
        if np.linalg.matrix_rank(candidate) == len(independent_positions) + 1:
            independent_positions.append(position)
    residualized = residualized[:, independent_positions]
    active = [instrument_names[active_positions[position]] for position in independent_positions]
    q = len(active)
    row["active_instruments"] = q
    if q == 0:
        return row

    gram = residualized.T @ residualized
    bread = np.linalg.inv(gram)
    beta = bread @ (residualized.T @ y_residual)
    model_residual = y_residual - residualized @ beta
    rss_restricted = float(y_residual @ y_residual)
    rss_full = float(model_residual @ model_residual)
    rank_controls = int(controls_fit.model.rank)
    residual_df = max(1, len(sample) - rank_controls - q)
    classical_f = ((rss_restricted - rss_full) / q) / (rss_full / residual_df)
    row["joint_F_classical"] = float(classical_f)
    row["joint_p_classical"] = float(st.f.sf(classical_f, q, residual_df))

    scores = residualized * model_residual[:, None]
    n_clusters = len(home_labels)
    cluster_sums = np.column_stack([
        np.bincount(home_clusters, weights=scores[:, column], minlength=n_clusters)
        for column in range(q)
    ])
    meat = cluster_sums.T @ cluster_sums
    small_sample_correction = (n_clusters / (n_clusters - 1)) * ((len(sample) - 1) / (len(sample) - controls.shape[1] - q))
    covariance = bread @ meat @ bread * small_sample_correction
    robust_f = float((beta @ np.linalg.pinv(covariance) @ beta) / q)
    row["joint_F_home_team_cluster"] = robust_f
    row["joint_p_home_team_cluster"] = float(st.f.sf(robust_f, q, cluster_df)) if robust_f >= 0 else np.nan

    for index, name in enumerate(active):
        estimate = float(beta[index])
        variance = float(covariance[index, index])
        standard_error = float(np.sqrt(variance)) if variance > 0 else np.nan
        t_value = estimate / standard_error if standard_error and np.isfinite(standard_error) else np.nan
        t_p = float(2 * st.t.sf(abs(t_value), cluster_df)) if np.isfinite(t_value) else np.nan
        row[f"{name}_coef"] = estimate
        row[f"{name}_cluster_se"] = standard_error
        row[f"{name}_cluster_p"] = t_p
        partial_f = (estimate**2 / bread[index, index]) / (rss_full / residual_df)
        row["home_partial_F_classical" if name == "home_prev_close" else "away_partial_F_classical"] = float(partial_f)
    return row


def threshold_grid(
    league: str,
    games: pd.DataFrame,
    scope: str,
    start_year: int | None,
    end_year: int | None,
    percentiles: list[float],
) -> tuple[list[dict[str, object]], pd.DataFrame]:
    sample, margin_distribution = _prepare_sample(games, start_year, end_year)
    sample.attrs["margin_count"] = len(margin_distribution)
    if not len(margin_distribution):
        raise ValueError(f"{league} has no valid margins for {scope}.")
    model_state = _model_state(sample)
    rows = []
    fitted_by_cutoff: dict[float, dict[str, object]] = {}
    for percentile in percentiles:
        cutoff = empirical_cutoff(margin_distribution, percentile)
        is_new_cutoff = cutoff not in fitted_by_cutoff
        if is_new_cutoff:
            fitted_by_cutoff[cutoff] = fit_first_stage(sample, cutoff, percentile, scope, model_state)
        result = fitted_by_cutoff[cutoff].copy()
        result["percentile"] = float(percentile)
        result["league"] = league
        result["n_games_in_margin_distribution"] = int(len(margin_distribution))
        result["actual_game_share_at_or_below_cutoff"] = float(margin_distribution.le(cutoff).mean())
        rows.append(result)
        if is_new_cutoff:
            print(
                f"{scope} {league} cutoff={cutoff:g} F={result['joint_F_classical']:.2f} "
                f"home-team-cluster-p={result['joint_p_home_team_cluster']:.4g}",
                flush=True,
            )
    return rows, sample


def threshold_percentiles(distributions: list[pd.Series], anchor_percentile: float) -> list[float]:
    """Cover each observed margin cutoff transition plus a 1-point percentile grid."""
    candidates = set(GRID)
    candidates.add(float(anchor_percentile))
    for values in distributions:
        ordered = np.sort(pd.to_numeric(values, errors="coerce").dropna().to_numpy(dtype=float))
        if not len(ordered):
            continue
        transition_indices = np.r_[0, np.flatnonzero(ordered[1:] != ordered[:-1]) + 1]
        candidates.update((transition_indices + 1).astype(float) / len(ordered))
    return sorted(value for value in candidates if 0 < value < 1)


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

    mlb_distribution = _prepare_sample(mlb, ANALYSIS_START_YEAR, ANALYSIS_END_YEAR)[1]
    nba_distribution = _prepare_sample(nba, ANALYSIS_START_YEAR, ANALYSIS_END_YEAR)[1]
    percentiles = threshold_percentiles([mlb_distribution, nba_distribution], anchor_percentile)
    all_rows: list[dict[str, object]] = []
    for league, games in [("MLB", mlb), ("NBA", nba)]:
        rows, sample = threshold_grid(
            league,
            games,
            PRIMARY_SCOPE,
            ANALYSIS_START_YEAR,
            ANALYSIS_END_YEAR,
            percentiles,
        )
        all_rows.extend(rows)

    grid = pd.DataFrame(all_rows).sort_values(["scope", "percentile", "league"])
    grid.to_csv(RESULTS / "common_percentile_grid.csv", index=False)
    selected, selection_mode = _choose_thresholds(grid, anchor_percentile)

    selected_rows = []
    first_stage_rows = []
    for league, games in [("MLB", mlb), ("NBA", nba)]:
        percentile = selected[league]
        if percentile is None:
            percentile = anchor_percentile
            selected_status = "NFL_anchor_retained_no_threshold_met_F10_and_p05"
        else:
            selected_status = f"selected_{selection_mode}"
        sample, distribution = _prepare_sample(games, ANALYSIS_START_YEAR, ANALYSIS_END_YEAR)
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
    primary_grid = grid.loc[grid["scope"].eq(PRIMARY_SCOPE)]
    max_grid_rows = []
    for _, league_rows in primary_grid.groupby("league"):
        maximum = league_rows["joint_F_classical"].max()
        tied_rows = league_rows.loc[np.isclose(league_rows["joint_F_classical"], maximum)]
        max_grid_rows.append(tied_rows.iloc[(tied_rows["percentile"] - anchor_percentile).abs().argmin()])
    max_grid = pd.DataFrame(max_grid_rows)
    max_grid_text = "; ".join(
        f"{row.league}: F={row.joint_F_classical:.2f} at p={row.percentile:.6%} "
        f"(cutoff {row.margin_cutoff:g}; close share {row.actual_game_share_at_or_below_cutoff:.5%})"
        for row in max_grid.itertuples()
    )
    anchor_shares = "; ".join(
        f"{row.league}: {row.share_of_game_margins_at_or_below_cutoff:.2%} (cutoff {row.margin_cutoff:g})"
        for row in selected_frame.itertuples()
    )
    max_cluster_rows = []
    for _, league_rows in primary_grid.groupby("league"):
        maximum = league_rows["joint_F_home_team_cluster"].max()
        tied_rows = league_rows.loc[np.isclose(league_rows["joint_F_home_team_cluster"], maximum)]
        max_cluster_rows.append(tied_rows.iloc[(tied_rows["percentile"] - anchor_percentile).abs().argmin()])
    max_cluster = pd.DataFrame(max_cluster_rows)
    max_cluster_text = "; ".join(
        f"{row.league}: cluster-Wald F={row.joint_F_home_team_cluster:.2f} at p={row.percentile:.6%} "
        f"(cutoff {row.margin_cutoff:g}; close share {row.actual_game_share_at_or_below_cutoff:.5%}; "
        f"conventional F={row.joint_F_classical:.2f}; clustered p={row.joint_p_home_team_cluster:.3g}; "
        f"active IVs={row.active_instruments})"
        for row in max_cluster.itertuples()
    )

    lines = [
        "# Data cleaning and first-stage summary",
        "",
        "## Scope",
        "",
        "This run cleans the three supplied game files, then estimates first-stage attendance regressions for the MLB and NBA only. It does not estimate the home-win outcome equation or a second-stage IV effect.",
        "",
        f"The MLB and NBA current-game analysis is restricted to calendar years {ANALYSIS_START_YEAR}–{ANALYSIS_END_YEAR}, matching the years covered by the supplied NFL file. The cleaned source files retain their full history; prior-game links are built from the full schedules before the current-game date restriction.",
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
        f"Common percentile in the tested 1%–99% grid and observed margin cutoffs passes both criteria in both leagues: {common_success}.",
        f"Threshold selection mode: {selection_mode}.",
        f"Largest conventional joint partial F in the full tested grid: {max_grid_text}.",
        f"Largest home-team-clustered Wald F by league: {max_cluster_text}.",
        f"At the NFL anchor percentile, the discrete MLB/NBA score distributions yield achieved close-game shares of {anchor_shares}.",
        "",
        "The selected first-stage model includes home-team, away-team, season, game-type, weekday, and month fixed effects. The excluded instruments are separate indicators for a close immediately previous game by the current home and away teams. Standard errors are clustered by current home team. The conventional joint partial F is reported alongside the home-team-cluster F and p-value.",
        "",
        "No tested threshold from the 1st through 99th percentile or any observed margin-cutoff transition has a conventional joint partial F above 10 in either league; therefore no league-specific alternative is selected and the NFL anchor is retained for the prepared samples. Clustered Wald p-values fall below .05 at some cutoffs, but the corresponding conventional partial Fs remain below 10. The largest clustered Wald tests occur at degenerate endpoints that classify almost no NBA games or almost every MLB game as close; those sparse or nearly constant indicators are not treated as useful first stages. F > 10 is a relevance screen, not evidence that the exclusion restriction holds. A previous close game can affect later team confidence or performance directly, so the exclusion restriction remains unresolved. No second-stage estimate is included.",
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
        "See `nfl_reference.csv`, `common_percentile_grid.csv`, `selected_thresholds.csv`, and `selected_first_stage.csv` for counts, cutoffs, coefficients, and F statistics.",
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
