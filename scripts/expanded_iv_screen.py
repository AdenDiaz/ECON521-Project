"""Exploratory first-stage search over schedule and lagged-demand IV candidates.

This script preserves earlier screens and writes a new candidate grid. It tests
attendance prediction only; it does not estimate home-win effects. Results from
a broad search are exploratory and should be reported as such.
"""
from __future__ import annotations

from pathlib import Path
import re

import numpy as np
import pandas as pd
import patsy
import statsmodels.api as sm
from scipy.stats import t as student_t
from statsmodels.stats.sandwich_covariance import cov_cluster_2groups
from pandas.tseries.holiday import USFederalHolidayCalendar

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "Data" / "raw"
DATA = ROOT / "Data" / "processed"
OUT = ROOT / "results" / "instrument_candidates" / "expanded_first_stage_grid.csv"
START_YEAR, END_YEAR = 2001, 2019


def parse_clock(value: object) -> float:
    text = str(value).strip().upper()
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


def _team_season_openers(league: str) -> set[str]:
    clean = pd.read_csv(DATA / f"{league.lower()}_games_clean.csv", parse_dates=["game_date"])
    clean["game_id"] = clean.game_id.astype("string").str.replace(r"\.0$", "", regex=True)
    clean["season_id"] = clean.season_id.astype("string")
    regular = clean.loc[clean.game_type.astype("string").str.casefold().isin({"regular", "regular season"})].copy()
    first = regular.groupby(["home_team_id", "season_id"]).game_date.transform("min")
    return set(regular.loc[regular.game_date.eq(first), "game_id"].dropna().astype(str))


def _lagged_home_gates(league: str) -> pd.DataFrame:
    clean = pd.read_csv(DATA / f"{league.lower()}_games_clean.csv", parse_dates=["game_date"])
    clean["game_id"] = clean.game_id.astype("string").str.replace(r"\.0$", "", regex=True)
    clean["season_id"] = clean.season_id.astype("string")
    clean = clean.sort_values(["home_team_id", "game_date", "game_order", "source_row_number"])
    groups = clean.groupby("home_team_id", sort=False)
    clean["last_home_game_attendance"] = groups.attendance.transform(lambda x: x.shift(1).ffill())
    clean["mean_prior_5_home_gates"] = groups.attendance.transform(
        lambda x: x.shift(1).rolling(5, min_periods=2).mean()
    )
    clean["mean_prior_season_home_gates"] = clean.groupby(
        ["home_team_id", "season_id"], sort=False
    ).attendance.transform(lambda x: x.shift(1).expanding(min_periods=2).mean())
    clean["previous_home_date"] = groups.game_date.shift(1)
    clean["last_home_gate_date"] = clean.game_date.where(pd.to_numeric(clean.attendance, errors="coerce").notna())
    clean["last_home_gate_date"] = clean.groupby("home_team_id", sort=False).last_home_gate_date.transform(
        lambda x: x.shift(1).ffill()
    )
    clean["days_since_last_observed_home_gate"] = (
        clean.game_date.dt.normalize() - clean.last_home_gate_date.dt.normalize()
    ).dt.days
    lookup = clean.set_index("source_row_number")[[
        "last_home_game_attendance", "mean_prior_5_home_gates", "mean_prior_season_home_gates",
        "days_since_last_observed_home_gate",
    ]]
    return lookup


def _prior_home_gate_for_visitor(league: str, frame: pd.DataFrame) -> pd.Series:
    """Find each visiting team's latest observed home gate before game day."""
    clean = pd.read_csv(DATA / f"{league.lower()}_games_clean.csv", parse_dates=["game_date"])
    clean = clean.loc[pd.to_numeric(clean.attendance, errors="coerce").notna()].copy()
    clean["game_day"] = clean.game_date.dt.normalize()
    history = {}
    for team, group in clean.groupby("home_team_id", sort=False):
        group = group.sort_values(["game_day", "game_order", "source_row_number"])
        group = group.drop_duplicates("game_day", keep="last")
        history[str(team)] = (
            group.game_day.to_numpy(dtype="datetime64[ns]").astype("int64"),
            pd.to_numeric(group.attendance, errors="coerce").to_numpy(dtype=float),
        )
    values = np.full(len(frame), np.nan)
    days = frame.game_date.dt.normalize().to_numpy(dtype="datetime64[ns]").astype("int64")
    teams = frame.away_team_id.astype(str).to_numpy()
    for team in np.unique(teams):
        if team not in history:
            continue
        idx = np.flatnonzero(teams == team)
        hist_days, hist_gates = history[team]
        prior = np.searchsorted(hist_days, days[idx], side="left") - 1
        has_prior = prior >= 0
        values[idx[has_prior]] = hist_gates[prior[has_prior]]
    return pd.Series(values, index=frame.index, name="away_last_home_game_attendance")


def _add_nfl_conflicts(frame: pd.DataFrame) -> pd.DataFrame:
    nfl = pd.read_csv(DATA / "nfl_games_clean.csv", parse_dates=["game_date"])
    raw = pd.read_csv(RAW / "NFL Data.csv", low_memory=False, usecols=["city", "time_home"])
    raw["source_row_number"] = np.arange(1, len(raw) + 1)
    nfl = nfl.merge(raw, on="source_row_number", how="left", validate="one_to_one")
    nfl = nfl.loc[nfl.game_date.dt.year.between(START_YEAR, END_YEAR)].copy()
    market = {
        "Atlanta": "atlanta", "Baltimore": "baltimore", "Buffalo": "buffalo",
        "Carolina": "charlotte", "Chicago": "chicago", "Cincinnati": "cincinnati",
        "Cleveland": "cleveland", "Dallas": "dallas", "Denver": "denver", "Detroit": "detroit",
        "Green Bay": "green_bay", "Houston": "houston", "Indianapolis": "indianapolis",
        "Jacksonville": "jacksonville", "Kansas City": "kansas_city", "Miami": "miami",
        "Minnesota": "minneapolis", "New England": "boston", "New Orleans": "new_orleans",
        "New York": "new_york", "Oakland": "bay_area", "Arizona": "phoenix",
        "Philadelphia": "philadelphia", "Pittsburgh": "pittsburgh", "San Diego": "san_diego",
        "San Francisco": "bay_area", "Seattle": "seattle", "St. Louis": "st_louis",
        "Tampa Bay": "tampa_bay", "Tennessee": "nashville", "Washington": "washington",
        "Los Angeles": "los_angeles",
    }
    nfl["market"] = nfl.city.map(market)
    nfl["start_minute"] = nfl.time_home.map(parse_clock)
    nba_market = {
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
    if "hometeamCity" in frame:
        frame["market"] = frame.hometeamCity.map(nba_market)
    else:
        from schedule_conflict_iv_first_stage import MLB_MARKET
        frame["market"] = frame.home_team_id.map(MLB_MARKET)
    nfl["date_key"] = nfl.game_date.dt.date
    frame["date_key"] = frame.game_date.dt.date
    schedules = {
        key: grp.start_minute.to_numpy(dtype=float)
        for key, grp in nfl.dropna(subset=["market"]).groupby(["market", "date_key"], sort=False)
    }
    flags = {"nfl_same_market_same_date": [], "nfl_within_3h": [], "nfl_within_6h": [], "nfl_within_9h": []}
    for row in frame[["market", "date_key", "start_minute"]].itertuples(index=False, name=None):
        times = schedules.get((row[0], row[1]), np.array([], dtype=float))
        known = times[np.isfinite(times)]
        flags["nfl_same_market_same_date"].append(bool(len(times)))
        for hours in (3, 6, 9):
            flags[f"nfl_within_{hours}h"].append(
                bool(len(known) and np.isfinite(row[2]) and (np.abs(known - row[2]) <= hours * 60).any())
            )
    for name, values in flags.items():
        frame[name] = values
    return frame


def load_league(league: str) -> pd.DataFrame:
    sample = pd.read_csv(DATA / f"{league.lower()}_first_stage_sample.csv", parse_dates=["game_date", "home_prev_game_date", "away_prev_game_date"])
    sample = sample.loc[sample.game_date.dt.year.between(START_YEAR, END_YEAR)].copy()
    if league == "MLB":
        raw = pd.read_csv(RAW / "MLB Data.csv", low_memory=False, usecols=["starttime", "daynight", "number", "usedh"])
        raw["source_row_number"] = np.arange(1, len(raw) + 1)
        sample = sample.merge(raw, on="source_row_number", how="left", validate="one_to_one")
        sample["start_minute"] = sample.starttime.map(parse_clock)
        sample["day_game"] = sample.daynight.astype("string").str.strip().str.upper().eq("D").astype(int)
        sample["doubleheader_second_game"] = pd.to_numeric(sample.number, errors="coerce").eq(2).astype(int)
        sample["market"] = sample.home_team_id.map({
            "ANA": "los_angeles", "LAA": "los_angeles", "LAN": "los_angeles", "LAD": "los_angeles",
            "OAK": "bay_area", "ATH": "bay_area", "SF": "bay_area", "SFG": "bay_area", "SFN": "bay_area",
            "NYA": "new_york", "NYY": "new_york", "NYN": "new_york", "NYM": "new_york",
            "CHN": "chicago", "CHC": "chicago", "CHA": "chicago", "CHW": "chicago", "CWS": "chicago",
            "FLO": "miami", "FLA": "miami", "MIA": "miami", "TBD": "tampa_bay", "TBA": "tampa_bay",
            "MON": "montreal", "WAS": "washington", "WSN": "washington", "WSH": "washington",
            "BOS": "boston", "PHI": "philadelphia", "CLE": "cleveland", "DET": "detroit",
            "HOU": "houston", "MIL": "milwaukee", "MIN": "minneapolis", "TOR": "toronto",
            "SEA": "seattle", "SD": "san_diego", "SDP": "san_diego", "SDN": "san_diego",
            "ARI": "phoenix", "AZ": "phoenix", "COL": "denver", "TEX": "dallas",
            "KC": "kansas_city", "KAN": "kansas_city", "KCA": "kansas_city", "KCR": "kansas_city",
            "STL": "st_louis", "SLN": "st_louis", "CIN": "cincinnati", "PIT": "pittsburgh",
            "BAL": "baltimore", "ATL": "atlanta",
        })
    else:
        raw = pd.read_csv(RAW / "NBA Data.csv", low_memory=False, usecols=["gameDate", "hometeamCity"])
        raw["source_row_number"] = np.arange(1, len(raw) + 1)
        sample = sample.merge(raw, on="source_row_number", how="left", validate="one_to_one")
        sample["gameDate"] = pd.to_datetime(sample.gameDate, errors="coerce")
        sample["start_minute"] = sample.gameDate.dt.hour * 60 + sample.gameDate.dt.minute
        sample["day_game"] = sample.start_minute.lt(17 * 60).astype(int)
        sample["doubleheader_second_game"] = 0
    sample["game_hour"] = sample.start_minute.floordiv(60).astype("Int64").astype("string").fillna("Unknown")
    sample["game_weekday"] = sample.game_date.dt.dayofweek.astype("string")
    sample["game_month"] = sample.game_date.dt.month.astype("string")
    sample["date_key"] = sample.game_date.dt.date
    sample["season_id"] = sample.season_id.astype("string")
    sample["game_type"] = sample.game_type.fillna("Unknown").astype("string")
    sample["home_team_id"] = sample.home_team_id.astype("string")
    sample["away_team_id"] = sample.away_team_id.astype("string")
    history = pd.read_csv(DATA / f"{league.lower()}_games_clean.csv")
    history["game_id"] = history.game_id.astype("string").str.replace(r"\.0$", "", regex=True)
    history = history.drop_duplicates("game_id").set_index("game_id")
    hist_home = history.home_team_id.astype("string")
    hist_away = history.away_team_id.astype("string")
    hist_win = pd.to_numeric(history.home_win, errors="coerce")
    hist_margin = pd.to_numeric(history.score_margin, errors="coerce")
    hist_attendance = pd.to_numeric(history.attendance, errors="coerce")
    for side in ("home", "away"):
        prev_id = sample[f"{side}_prev_game_id"].astype("string").str.replace(r"\.0$", "", regex=True)
        current_team = sample[f"{side}_team_id"].astype("string")
        prior_home_team = prev_id.map(hist_home)
        prior_away_team = prev_id.map(hist_away)
        prior_win = prev_id.map(hist_win)
        prior_margin = prev_id.map(hist_margin)
        sample[f"{side}_prev_win"] = np.where(
            current_team.eq(prior_home_team), prior_win,
            np.where(current_team.eq(prior_away_team), 1 - prior_win, np.nan),
        )
        sample[f"{side}_prev_margin_signed"] = np.where(
            current_team.eq(prior_home_team), prior_margin,
            np.where(current_team.eq(prior_away_team), -prior_margin, np.nan),
        )
        sample[f"{side}_prev_game_attendance"] = prev_id.map(hist_attendance)
    for side in ("home", "away"):
        prev = sample[f"{side}_prev_game_date"]
        gap = (sample.game_date.dt.normalize() - prev.dt.normalize()).dt.days
        sample[f"{side}_rest_days"] = (gap - 1).clip(lower=0)
        sample[f"{side}_back_to_back"] = sample[f"{side}_rest_days"].eq(0).astype(int)
        sample[f"{side}_short_rest"] = sample[f"{side}_rest_days"].le(1).astype(int)
        sample[f"{side}_rest_bin"] = pd.cut(sample[f"{side}_rest_days"], [-1, 0, 1, 3, 6, 100], labels=["0", "1", "2-3", "4-6", "7+"]).astype("string")
    sample["weekend"] = sample.game_date.dt.dayofweek.ge(5).astype(int)
    sample["saturday"] = sample.game_date.dt.dayofweek.eq(5).astype(int)
    sample["sunday"] = sample.game_date.dt.dayofweek.eq(6).astype(int)
    sample["friday"] = sample.game_date.dt.dayofweek.eq(4).astype(int)
    sample["afternoon_start"] = sample.start_minute.lt(17 * 60).astype(int)
    sample["late_start"] = sample.start_minute.ge(20 * 60).astype(int)
    calendar = USFederalHolidayCalendar()
    federal = set(calendar.holidays(start=f"{START_YEAR}-01-01", end=f"{END_YEAR}-12-31").date)
    sample["us_federal_holiday"] = sample.game_date.dt.date.isin(federal).astype(int)
    if league == "MLB":
        sample["opening_month"] = sample.game_date.dt.month.eq(4).astype(int)
        sample["late_season_month"] = sample.game_date.dt.month.ge(8).astype(int)
    else:
        sample["opening_month"] = sample.game_date.dt.month.eq(10).astype(int)
        sample["late_season_month"] = sample.game_date.dt.month.ge(3).astype(int)
    sample["christmas"] = (sample.game_date.dt.month.eq(12) & sample.game_date.dt.day.eq(25)).astype(int)
    sample["july_fourth"] = (sample.game_date.dt.month.eq(7) & sample.game_date.dt.day.eq(4)).astype(int)
    sample["home_opener"] = sample.game_id.astype("string").str.replace(r"\.0$", "", regex=True).isin(_team_season_openers(league)).astype(int)
    sample = sample.join(_lagged_home_gates(league), on="source_row_number")
    sample["away_last_home_game_attendance"] = _prior_home_gate_for_visitor(league, sample)
    sample["home_prev_game_abs_margin"] = pd.to_numeric(sample.home_prev_game_abs_margin, errors="coerce")
    sample["away_prev_game_abs_margin"] = pd.to_numeric(sample.away_prev_game_abs_margin, errors="coerce")
    sample["home_prev_close"] = pd.to_numeric(sample.home_prev_close, errors="coerce")
    sample["away_prev_close"] = pd.to_numeric(sample.away_prev_close, errors="coerce")
    sample = _add_nfl_conflicts(sample)
    return sample


def fit_candidate(frame: pd.DataFrame, league: str, name: str, definition: str, variable: str, formula: str, family: str, risk: str) -> dict[str, object] | None:
    instrument = pd.to_numeric(frame[variable], errors="coerce").astype(float)
    outcome = pd.to_numeric(frame.attendance, errors="coerce")
    valid = instrument.notna() & outcome.notna()
    if instrument.loc[valid].nunique() < 2 or valid.sum() < 100:
        return None
    data = frame.loc[valid].copy()
    controls = patsy.dmatrix(formula, data, return_type="dataframe")
    design = pd.concat([controls, instrument.loc[valid].rename("excluded_iv")], axis=1)
    model = sm.OLS(outcome.loc[valid], design).fit()
    robust = model.get_robustcov_results(cov_type="cluster", groups=data.home_team_id, use_correction=True, df_correction=True)
    coef = float(model.params["excluded_iv"])
    se = float(model.bse["excluded_iv"])
    robust_t = float(robust.tvalues[-1])
    team_cluster = pd.factorize(data.home_team_id, sort=True)[0]
    date_cluster = pd.factorize(data.date_key, sort=True)[0]
    cov_both, _, _ = cov_cluster_2groups(model, team_cluster, date_cluster, use_correction=True)
    iv_position = design.columns.get_loc("excluded_iv")
    se_team_date = float(np.sqrt(max(cov_both[iv_position, iv_position], 0.0)))
    df_team_date = min(data.home_team_id.nunique(), data.date_key.nunique()) - 1
    t_team_date = coef / se_team_date if se_team_date > 0 else np.nan
    f_team_date = t_team_date ** 2
    p_team_date = float(2 * student_t.sf(abs(t_team_date), df_team_date)) if np.isfinite(t_team_date) else np.nan
    return {
        "league": league,
        "candidate": name,
        "family": family,
        "definition": definition,
        "n": int(valid.sum()),
        "exposure_share_or_mean": float(instrument.loc[valid].mean()),
        "coefficient_attendance": coef,
        "se_classical": se,
        "partial_F_classical": float((coef / se) ** 2),
        "cluster_Wald_F": robust_t ** 2,
        "p_home_team_cluster": float(robust.pvalues[-1]),
        "two_way_cluster_Wald_F_team_date": float(f_team_date),
        "p_two_way_team_date": p_team_date,
        "clusters": int(data.home_team_id.nunique()),
        "fixed_effects_and_controls": formula.replace("C(", "").replace(")", ""),
        "exclusion_risk": risk,
    }


def main() -> None:
    formulas = {
        "full": "1 + C(home_team_id) + C(away_team_id) + C(season_id) + C(game_type) + C(game_weekday) + C(game_month) + C(game_hour)",
        "no_weekday": "1 + C(home_team_id) + C(away_team_id) + C(season_id) + C(game_type) + C(game_month) + C(game_hour) + home_rest_days + away_rest_days + home_prev_win + away_prev_win + home_prev_margin_signed + away_prev_margin_signed",
        "no_hour": "1 + C(home_team_id) + C(away_team_id) + C(season_id) + C(game_type) + C(game_weekday) + C(game_month) + home_rest_days + away_rest_days + home_prev_win + away_prev_win + home_prev_margin_signed + away_prev_margin_signed",
        "no_month": "1 + C(home_team_id) + C(away_team_id) + C(season_id) + C(game_type) + C(game_weekday) + C(game_hour) + home_rest_days + away_rest_days + home_prev_win + away_prev_win + home_prev_margin_signed + away_prev_margin_signed",
        "with_rest_form": "1 + C(home_team_id) + C(away_team_id) + C(season_id) + C(game_type) + C(game_weekday) + C(game_month) + C(game_hour) + home_rest_days + away_rest_days + home_prev_win + away_prev_win + home_prev_margin_signed + away_prev_margin_signed",
        "with_date_only": "1 + C(home_team_id) + C(away_team_id) + C(season_id) + C(game_type) + C(game_weekday) + C(game_month) + C(game_hour)",
    }
    rows: list[dict[str, object]] = []
    for league in ("MLB", "NBA"):
        frame = load_league(league)
        candidates = [
            ("weekend", "Saturday or Sunday vs weekday", "weekend", "no_weekday", "calendar", "Schedule timing can change player routines/rest; control for rest, but direct schedule effects remain."),
            ("saturday", "Saturday vs other days", "saturday", "no_weekday", "calendar", "Schedule timing may affect routines/rest and broadcast/game preparation."),
            ("sunday", "Sunday vs other days", "sunday", "no_weekday", "calendar", "Schedule timing may affect routines/rest and broadcast/game preparation."),
            ("friday", "Friday vs other days", "friday", "no_weekday", "calendar", "Schedule timing may affect routines/rest and travel."),
            ("day_game", "MLB day game (source daynight flag) or NBA start before 5 p.m.", "day_game", "no_hour", "game_time", "Circadian timing can directly affect player performance; for MLB, doubleheaders and travel also matter."),
            ("afternoon_start", "Scheduled start before 5 p.m.", "afternoon_start", "no_hour", "game_time", "Start time can affect player routines and travel; schedule assignments are not random."),
            ("late_start", "Scheduled start at or after 8 p.m.", "late_start", "no_hour", "game_time", "Start time can affect circadian performance and team travel."),
            ("home_opener", "Team's first regular-season home game in its season", "home_opener", "full", "calendar_event", "Opening-game ceremonies, motivation, and season expectations could affect performance directly."),
            ("opening_month", "April MLB / October NBA regular-season games", "opening_month", "no_month", "calendar_progression", "Season stage changes player conditioning, roster strategy, and team incentives."),
            ("late_season_month", "August-September MLB / March-April NBA games", "late_season_month", "no_month", "calendar_progression", "Season stage affects fatigue, playoff incentives, and roster decisions."),
            ("us_federal_holiday", "Game falls on a U.S. federal holiday", "us_federal_holiday", "full", "holiday", "Holiday scheduling may be selected and can change team routines/travel."),
            ("christmas", "Game falls on December 25", "christmas", "full", "holiday", "NBA Christmas games are selected marquee matchups; direct selection and preparation effects are likely."),
            ("july_fourth", "Game falls on July 4", "july_fourth", "full", "holiday", "Holiday schedules and special events may affect team routines and game atmosphere."),
            ("home_back_to_back", "Home team played the previous calendar day", "home_back_to_back", "full", "rest_schedule", "Direct fatigue/performance channel makes exclusion especially doubtful."),
            ("away_back_to_back", "Away team played the previous calendar day", "away_back_to_back", "full", "rest_schedule", "Direct away-team fatigue/performance channel makes exclusion especially doubtful."),
            ("home_short_rest", "Home team had zero or one rest day", "home_short_rest", "full", "rest_schedule", "Direct fatigue/performance channel makes exclusion especially doubtful."),
            ("away_short_rest", "Away team had zero or one rest day", "away_short_rest", "full", "rest_schedule", "Direct away-team fatigue/performance channel makes exclusion especially doubtful."),
            ("doubleheader_second_game", "Second MLB game in a same-day doubleheader", "doubleheader_second_game", "full", "game_time", "Doubleheader fatigue, lineups, and pitcher use directly affect performance."),
            ("last_home_game_attendance", "Attendance at home team's most recent prior home game", "last_home_game_attendance", "with_rest_form", "demand_persistence", "Prior crowd size may affect team morale and proxies for persistent popularity, quality, and local demand."),
            ("mean_prior_5_home_gates", "Mean attendance over up to five observed prior home games", "mean_prior_5_home_gates", "with_rest_form", "demand_persistence", "Prior crowd size and latent team form/popularity may directly predict current performance."),
            ("mean_prior_season_home_gates", "Season-to-date mean of prior home-game attendance", "mean_prior_season_home_gates", "with_rest_form", "demand_persistence", "Season attendance trend proxies for latent demand, team quality, and fan response to performance."),
            ("home_prev_game_attendance", "Attendance at the home team's immediately preceding game, home or away", "home_prev_game_attendance", "with_rest_form", "demand_persistence", "Prior game crowd reflects opponent demand and team form; the prior crowd could also have direct effects on team morale."),
            ("away_last_home_game_attendance", "Attendance at the visiting team's most recent prior home game", "away_last_home_game_attendance", "with_rest_form", "opponent_popularity", "Visiting-team popularity can predict its current performance and directly affect the home result."),
        ]
        for name, definition, variable, control_key, family, risk in candidates:
            formula = formulas[control_key]
            if name == "doubleheader_second_game" and league != "MLB":
                continue
            if name == "july_fourth" and league != "MLB":
                continue
            if name == "christmas" and league != "NBA":
                continue
            row = fit_candidate(frame, league, name, definition, variable, formula, family, risk)
            if row:
                rows.append(row)
        for variable, definition, window in [
            ("nfl_same_market_same_date", "NFL home game in same metro on same date", "same_date"),
            ("nfl_within_3h", "NFL home game starts within 3 hours in same metro/date", "within_3h"),
            ("nfl_within_6h", "NFL home game starts within 6 hours in same metro/date", "within_6h"),
            ("nfl_within_9h", "NFL home game starts within 9 hours in same metro/date", "within_9h"),
        ]:
            row = fit_candidate(frame, league, f"nfl_{window}", definition, variable, formulas["full"], "cross_league_conflict", "Crowd substitution is plausible; local traffic, team arrival, and schedule coordination can directly affect game conditions.")
            if row:
                rows.append(row)
    result = pd.DataFrame(rows).sort_values(["league", "cluster_Wald_F"], ascending=[True, False])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT, index=False)
    show = ["league", "candidate", "n", "exposure_share_or_mean", "coefficient_attendance", "partial_F_classical", "cluster_Wald_F", "p_home_team_cluster", "two_way_cluster_Wald_F_team_date", "p_two_way_team_date"]
    print(result[show].to_string(index=False))
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
