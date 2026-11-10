"""Combine all preserved first-stage candidate screens into one sortable CSV."""
from __future__ import annotations

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "instrument_candidates" / "all_candidate_inventory.csv"
BASE = ROOT / "results" / "instrument_candidates"
FIRST = ROOT / "results" / "first_stage"
RECORDS: list[dict[str, object]] = []


def _value(row: pd.Series, *names: str, default: object = None) -> object:
    for name in names:
        if name in row.index and pd.notna(row[name]):
            return row[name]
    return default


def _add(source: str, row: pd.Series, *, league: object = None, candidate: object = None,
         family: object = None, definition: object = None, n: object = None,
         coefficient: object = None, classical_f: object = None, team_f: object = None,
         two_way_f: object = None, p_two_way: object = None, specification: str = "",
         risk: object = None, status: str = "estimated", extra: str = "") -> None:
    RECORDS.append({
        "league": league if league is not None else _value(row, "league", "scope"),
        "candidate": candidate if candidate is not None else _value(row, "candidate", "instrument_candidate"),
        "family": family if family is not None else _value(row, "family"),
        "definition": definition if definition is not None else _value(row, "definition"),
        "n": n if n is not None else _value(row, "n", "n_first_stage_observations"),
        "attendance_coefficient": coefficient if coefficient is not None else _value(row, "coefficient_attendance"),
        "classical_partial_F": classical_f if classical_f is not None else _value(row, "partial_F_classical", "joint_F_classical"),
        "home_team_cluster_Wald_F": team_f if team_f is not None else _value(row, "cluster_Wald_F", "home_team_cluster_Wald_F", "joint_F_home_team_cluster"),
        "team_date_cluster_Wald_F": two_way_f if two_way_f is not None else _value(row, "two_way_cluster_Wald_F_team_date", "team_date_two_way_Wald_F"),
        "p_team_date_cluster": p_two_way if p_two_way is not None else _value(row, "p_two_way_team_date", "p_team_date_two_way", "p_team_date_two_way_df9"),
        "specification": specification,
        "exclusion_risk": risk if risk is not None else _value(row, "exclusion_risk"),
        "status": status,
        "source_file": source,
        "extra": extra,
    })


def main() -> None:
    # Main alternative IV search and stronger team-season specification.
    path = BASE / "expanded_first_stage_grid.csv"
    if path.exists():
        for _, r in pd.read_csv(path).iterrows():
            _add(path.name, r, specification="home/away team, season, game-type, and calendar controls; clustered by team and date")
    path = BASE / "team_season_fe_robustness.csv"
    if path.exists():
        for _, r in pd.read_csv(path).iterrows():
            _add(path.name, r, specification="home-team x season and away-team x season fixed effects; clustered by team and date")
    path = BASE / "team_season_date_fe_robustness.csv"
    if path.exists():
        for _, r in pd.read_csv(path).iterrows():
            _add(path.name, r, specification="home/away team-season plus exact-date fixed effects", status=str(_value(r, "status", default="estimated")))

    # Weather search and robust threshold grids.
    for filename, spec, default_league in [
        ("nba_weather_window_first_stage.csv", "home/away team, season, game-type, weekday, month, and timing controls; two-way clustered", "NBA"),
        ("nba_weather_threshold_robustness.csv", "home/away team-season plus exact-date fixed effects; two-way clustered", "NBA"),
        ("mlb_dome_weather_first_stage.csv", "dome-marked games; home/away team, season, game type, calendar, rest, and form controls", "MLB"),
        ("mlb_dome_weather_robustness.csv", "dome-marked games; home/away team-season plus exact-date fixed effects", "MLB"),
        ("mlb_recorded_weather_first_stage.csv", "outdoor-marked games; home/away team-season plus exact-date fixed effects", "MLB"),
    ]:
        path = BASE / filename
        if not path.exists():
            continue
        for _, r in pd.read_csv(path).iterrows():
            _add(path.name, r, league=_value(r, "league", default=default_league), specification=spec,
                 status="not estimable after controls" if pd.isna(_value(r, "team_date_two_way_Wald_F", "two_way_cluster_Wald_F_team_date")) else "estimated")

    # Previously completed alternatives.
    path = BASE / "schedule_conflict_first_stage.csv"
    if path.exists():
        for _, r in pd.read_csv(path).iterrows():
            _add(path.name, r, candidate=_value(r, "instrument_candidate"),
                 specification=str(_value(r, "specification", default="same-market schedule conflict")) + "; " + str(_value(r, "fixed_effects", default="")),
                 team_f=_value(r, "cluster_Wald_F"), classical_f=_value(r, "partial_F_classical"),
                 risk="Local event competition may affect attendance; traffic and team travel can directly affect game conditions.")
    path = BASE / "nba_weather_first_stage.csv"
    if path.exists():
        for _, r in pd.read_csv(path).iterrows():
            _add(path.name, r, candidate=_value(r, "instrument_candidate"),
                 definition=_value(r, "definition"), classical_f=_value(r, "partial_F_classical"),
                 team_f=_value(r, "cluster_Wald_F"),
                 risk="Indoor play reduces direct weather exposure, but weather can disrupt fan and team travel.")

    # The original closer-prior-game percentile/cutoff search.
    path = FIRST / "common_percentile_grid.csv"
    if path.exists():
        for _, r in pd.read_csv(path).iterrows():
            pct, cutoff = _value(r, "percentile"), _value(r, "margin_cutoff")
            league = _value(r, "league")
            _add(path.name, r, league=league,
                 candidate="home and away previous-game closeness",
                 family="prior_game_margin",
                 definition=f"Both teams' prior game absolute margin <= {cutoff} at {pct}th-percentile cutoff",
                 n=_value(r, "n_first_stage_observations"),
                 classical_f=_value(r, "joint_F_classical"),
                 team_f=_value(r, "joint_F_home_team_cluster"),
                 specification="original close-prior-game instrument; percentile/cutoff grid",
                 risk="Prior-game closeness may affect current team form, confidence, fatigue, and fan engagement.",
                 extra=f"percentile={pct}; margin_cutoff={cutoff}; active_instruments={_value(r, 'active_instruments')}; home_coef={_value(r, 'home_prev_close_coef')}; away_coef={_value(r, 'away_prev_close_coef')}")

    result = pd.DataFrame(RECORDS)
    result["n"] = pd.to_numeric(result["n"], errors="coerce")
    for col in ["attendance_coefficient", "classical_partial_F", "home_team_cluster_Wald_F", "team_date_cluster_Wald_F", "p_team_date_cluster"]:
        result[col] = pd.to_numeric(result[col], errors="coerce")
    result.to_csv(OUT, index=False)
    print(f"Compiled {len(result):,} candidate/specification rows to {OUT}")
    print("Rows with two-way team/date F > 10:", int(result.team_date_cluster_Wald_F.gt(10).sum()))
    print("Rows with home-team cluster F > 10:", int(result.home_team_cluster_Wald_F.gt(10).sum()))


if __name__ == "__main__":
    main()
