"""Screen same-market cross-league schedule conflicts as attendance instruments.

For each MLB or NBA game, the excluded-variable candidates indicate whether a
game in the other league is scheduled in the same metro on the same date, or
within two hours of the current game's scheduled start. The script estimates
first stages only. It does not estimate home-win outcomes.
"""
from __future__ import annotations

from pathlib import Path
import re

import numpy as np
import pandas as pd
import patsy
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "Data" / "raw"
SAMPLES = ROOT / "Data" / "processed"
OUT = ROOT / "results" / "instrument_candidates" / "schedule_conflict_first_stage.csv"
START_YEAR, END_YEAR = 2001, 2019

MLB_MARKET = {
    "ANA": "los_angeles", "LAA": "los_angeles", "CAL": "los_angeles", "LAD": "los_angeles",
    "OAK": "bay_area", "ATH": "bay_area", "SF": "bay_area", "SFG": "bay_area",
    "NYA": "new_york", "NYY": "new_york", "NYN": "new_york", "NYM": "new_york",
    "CHN": "chicago", "CHC": "chicago", "CHA": "chicago", "CHW": "chicago",
    "FLO": "miami", "FLA": "miami", "MIA": "miami", "TBD": "tampa_bay", "TB": "tampa_bay",
    "MON": "montreal", "WAS": "washington", "WSN": "washington", "WSH": "washington",
    "BOS": "boston", "PHI": "philadelphia", "CLE": "cleveland", "DET": "detroit",
    "HOU": "houston", "MIL": "milwaukee", "MIN": "minneapolis", "TOR": "toronto",
    "SEA": "seattle", "SD": "san_diego", "SDP": "san_diego", "ARI": "phoenix", "AZ": "phoenix",
    "COL": "denver", "TEX": "dallas", "KC": "kansas_city", "KCA": "kansas_city",
    "STL": "st_louis", "CIN": "cincinnati", "PIT": "pittsburgh", "BAL": "baltimore",
    "ATL": "atlanta", "CWS": "chicago", "KCR": "kansas_city", "KAN": "kansas_city", "LAN": "los_angeles", "SFN": "bay_area",
    "TBA": "tampa_bay", "SLN": "st_louis", "SDN": "san_diego",
}
NBA_CITY_MARKET = {
    "Atlanta": "atlanta", "Boston": "boston", "Brooklyn": "new_york", "New Jersey": "new_york",
    "Charlotte": "charlotte", "Chicago": "chicago", "Cleveland": "cleveland", "Dallas": "dallas",
    "Denver": "denver", "Detroit": "detroit", "Golden State": "bay_area", "Houston": "houston",
    "Indiana": "indianapolis", "Los Angeles": "los_angeles", "Memphis": "memphis", "Miami": "miami",
    "Milwaukee": "milwaukee", "Minnesota": "minneapolis", "New Orleans": "new_orleans",
    "New York": "new_york", "Oklahoma City": "oklahoma_city", "Orlando": "orlando",
    "Philadelphia": "philadelphia", "Phoenix": "phoenix", "Portland": "portland",
    "Sacramento": "sacramento", "San Antonio": "san_antonio", "Seattle": "seattle",
    "Toronto": "toronto", "Utah": "salt_lake_city", "Vancouver": "vancouver", "Washington": "washington",
}


def mlb_minutes(value: object) -> float:
    text = str(value).strip().upper()
    # Retrosheet uses 0:00PM for an unknown start time; do not treat it as noon.
    if not text or text in {"NAN", "0:00PM", "0:00AM"}:
        return np.nan
    match = re.fullmatch(r"(\d{1,2}):(\d{2})(AM|PM)", text)
    if not match:
        return np.nan
    hour, minute = int(match.group(1)), int(match.group(2))
    if not 1 <= hour <= 12 or minute > 59:
        return np.nan
    hour = hour % 12 + (12 if match.group(3) == "PM" else 0)
    return float(hour * 60 + minute)


def load_events() -> dict[str, pd.DataFrame]:
    mlb = pd.read_csv(SAMPLES / "mlb_first_stage_sample.csv", parse_dates=["game_date"])
    nba = pd.read_csv(SAMPLES / "nba_first_stage_sample.csv", parse_dates=["game_date"])
    mlb = mlb.loc[mlb.game_date.dt.year.between(START_YEAR, END_YEAR)].copy()
    nba = nba.loc[nba.game_date.dt.year.between(START_YEAR, END_YEAR)].copy()

    mlb_raw = pd.read_csv(RAW / "MLB Data.csv", low_memory=False, usecols=["starttime"])
    mlb_raw["source_row_number"] = np.arange(1, len(mlb_raw) + 1)
    mlb = mlb.merge(mlb_raw, on="source_row_number", how="left", validate="one_to_one")
    mlb["market"] = mlb["home_team_id"].map(MLB_MARKET)
    mlb["start_minute"] = mlb.starttime.map(mlb_minutes)

    nba_raw = pd.read_csv(RAW / "NBA Data.csv", low_memory=False, usecols=["gameDate", "hometeamCity"])
    nba_raw["source_row_number"] = np.arange(1, len(nba_raw) + 1)
    nba = nba.merge(nba_raw, on="source_row_number", how="left", validate="one_to_one")
    nba["market"] = nba.hometeamCity.map(NBA_CITY_MARKET)
    nba["gameDate"] = pd.to_datetime(nba.gameDate, errors="coerce")
    nba["start_minute"] = nba.gameDate.dt.hour * 60 + nba.gameDate.dt.minute
    for league, frame in [("MLB", mlb), ("NBA", nba)]:
        missing = frame.market.isna()
        if missing.any():
            values = frame.loc[missing, "home_team_id" if league == "MLB" else "hometeamCity"].dropna().unique()
            raise ValueError(f"Unmapped {league} home markets: {values[:10]}")
    return {"MLB": mlb, "NBA": nba}


def conflict_flags(current: pd.DataFrame, other: pd.DataFrame) -> pd.DataFrame:
    """Match a current game to any other-league game in its market/date."""
    other_events = other[["market", "game_date", "start_minute"]].copy()
    other_events["date_key"] = other_events.game_date.dt.date
    current = current.copy()
    current["date_key"] = current.game_date.dt.date
    schedules = {
        key: grp.start_minute.to_numpy(dtype=float)
        for key, grp in other_events.groupby(["market", "date_key"], sort=False)
    }
    same_day, within_two = [], []
    for row in current[["market", "date_key", "start_minute"]].itertuples(index=False, name=None):
        times = schedules.get((row[0], row[1]), np.array([], dtype=float))
        same_day.append(bool(len(times)))
        known_times = times[np.isfinite(times)]
        within_two.append(bool(len(known_times) and np.isfinite(row[2]) and (np.abs(known_times - row[2]) <= 120).any()))
    return pd.DataFrame({"conflict_same_market_date": same_day, "conflict_within_two_hours": within_two}, index=current.index)


def fit(league: str, frame: pd.DataFrame) -> list[dict[str, object]]:
    frame = frame.copy()
    frame["season_id"] = frame.season_id.astype("string")
    frame["game_type"] = frame.game_type.fillna("Unknown").astype("string")
    frame["home_team_id"] = frame.home_team_id.astype("string")
    frame["away_team_id"] = frame.away_team_id.astype("string")
    frame["game_weekday"] = frame.game_date.dt.dayofweek.astype("string")
    frame["game_month"] = frame.game_date.dt.month.astype("string")
    frame["game_hour"] = frame.start_minute.floordiv(60).astype("Int64").astype("string").fillna("Unknown")
    controls = patsy.dmatrix(
        "1 + C(home_team_id) + C(away_team_id) + C(season_id) + C(game_type) + C(game_weekday) + C(game_month) + C(game_hour)",
        frame, return_type="dataframe",
    )
    outcome = pd.to_numeric(frame.attendance, errors="coerce")
    rows = []
    for variable in ["conflict_same_market_date", "conflict_within_two_hours"]:
        instrument = frame[variable].astype(float)
        valid = outcome.notna() & instrument.notna()
        design = pd.concat([controls.loc[valid], instrument.loc[valid].rename(variable)], axis=1)
        model = sm.OLS(outcome.loc[valid], design).fit()
        robust = model.get_robustcov_results(
            cov_type="cluster", groups=frame.loc[valid, "home_team_id"],
            use_correction=True, df_correction=True,
        )
        coef, classical_se = float(model.params[variable]), float(model.bse[variable])
        rows.append({
            "league": league,
            "specification": "baseline",
            "instrument_candidate": variable,
            "definition": "Same metro/date other-league game" if variable.endswith("date") else "Same metro/date other-league game starts within 2 hours",
            "n": int(valid.sum()),
            "conflict_share": float(instrument.loc[valid].mean()),
            "coefficient_attendance": coef,
            "se_classical": classical_se,
            "partial_F_classical": float((coef / classical_se) ** 2),
            "p_classical": float(model.pvalues[variable]),
            "se_home_team_cluster": float(robust.bse[-1]),
            "cluster_Wald_F": float(robust.tvalues[-1] ** 2),
            "p_home_team_cluster": float(robust.pvalues[-1]),
            "n_home_team_clusters": int(frame.loc[valid, "home_team_id"].nunique()),
            "fixed_effects": "home team, away team, season, game type, weekday, month, current start hour",
            "cluster": "current home team",
        })
    # Robustness specification with exact calendar-date fixed effects. Remove
    # date means from the outcome, candidate instruments, and remaining low-
    # dimensional controls, then fit the partialled-out first stage.
    date_frame = frame.copy()
    date_frame["game_hour"] = date_frame.start_minute.floordiv(60).astype("Int64").astype("string").fillna("Unknown")
    controls_date = patsy.dmatrix(
        "0 + C(home_team_id) + C(away_team_id) + C(game_type) + C(game_hour)",
        date_frame, return_type="dataframe",
    )
    valid = outcome.notna()
    base = pd.concat([
        outcome.loc[valid].rename("attendance"),
        date_frame.loc[valid, ["conflict_same_market_date", "conflict_within_two_hours"]].astype(float),
        controls_date.loc[valid],
    ], axis=1)
    date_keys = date_frame.loc[valid, "game_date"].dt.strftime("%Y-%m-%d")
    residualized = base - base.groupby(date_keys.to_numpy(), sort=False).transform("mean")
    date_rows = []
    for variable in ["conflict_same_market_date", "conflict_within_two_hours"]:
        design = pd.concat([residualized[controls_date.columns], residualized[variable]], axis=1)
        model = sm.OLS(residualized["attendance"], design).fit()
        robust = model.get_robustcov_results(
            cov_type="cluster", groups=frame.loc[valid, "home_team_id"],
            use_correction=True, df_correction=True,
        )
        coef, classical_se = float(model.params[variable]), float(model.bse[variable])
        date_rows.append({
            "league": league,
            "specification": "calendar_date_fixed_effects",
            "instrument_candidate": variable,
            "definition": "Same metro/date other-league game" if variable.endswith("date") else "Same metro/date other-league game starts within 2 hours",
            "n": int(valid.sum()),
            "conflict_share": float(date_frame.loc[valid, variable].mean()),
            "coefficient_attendance": coef,
            "se_classical": classical_se,
            "partial_F_classical": float((coef / classical_se) ** 2),
            "p_classical": float(model.pvalues[variable]),
            "se_home_team_cluster": float(robust.bse[design.columns.get_loc(variable)]),
            "cluster_Wald_F": float(robust.tvalues[design.columns.get_loc(variable)] ** 2),
            "p_home_team_cluster": float(robust.pvalues[design.columns.get_loc(variable)]),
            "n_home_team_clusters": int(frame.loc[valid, "home_team_id"].nunique()),
            "fixed_effects": "home team, away team, game type, game date, current start hour",
            "cluster": "current home team",
        })
    return rows + date_rows


def main() -> None:
    events = load_events()
    rows = []
    for current_league, other_league in [("MLB", "NBA"), ("NBA", "MLB")]:
        current = events[current_league]
        flags = conflict_flags(current, events[other_league])
        current = current.join(flags)
        rows.extend(fit(current_league, current))
    result = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT, index=False)
    print(result[["league", "specification", "instrument_candidate", "n", "conflict_share", "coefficient_attendance", "partial_F_classical", "cluster_Wald_F", "p_home_team_cluster"]].to_string(index=False))
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
