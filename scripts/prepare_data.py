"""Prepare consistent, game-level data for the ECON521 attendance project.

Raw files are never modified. Cleaned game files retain schedule rows with a
missing attendance value so they can still serve as a team's previous game.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "Data" / "raw"
PROCESSED = ROOT / "Data" / "processed"
CLEANING_RESULTS = ROOT / "results" / "cleaning"
NBA_MAX_ATTENDANCE = 100_000  # Conservative upper bound; source has 144k and 200k errors.
NBA_MIN_ATTENDANCE = 100      # The lone value below this is 9 for a 1982 NBA game.

OUTPUT_COLUMNS = [
    "league", "game_id", "source_row_number", "game_date", "season_id",
    "home_team_id", "away_team_id", "home_team", "away_team",
    "attendance", "attendance_quality", "game_type", "game_order",
    "home_score", "away_score", "score_margin", "abs_margin", "home_win",
    "home_prev_game_id", "home_prev_game_date", "home_prev_game_abs_margin",
    "home_prev_game_status", "away_prev_game_id", "away_prev_game_date",
    "away_prev_game_abs_margin", "away_prev_game_status",
]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required raw data file not found: {path}")
    frame = pd.read_csv(path, low_memory=False)
    frame["source_row_number"] = np.arange(1, len(frame) + 1, dtype=np.int64)
    return frame


def _numeric(series: pd.Series) -> pd.Series:
    text = series.astype("string").str.strip().str.replace(",", "", regex=False)
    return pd.to_numeric(text, errors="coerce")


def _clean_attendance(
    raw: pd.Series,
    *,
    league: str,
) -> tuple[pd.Series, pd.Series]:
    value = _numeric(raw)
    source_missing = raw.isna() | raw.astype("string").str.strip().eq("")
    quality = pd.Series("valid", index=raw.index, dtype="string")
    quality.loc[source_missing] = "missing_source_value"
    quality.loc[~source_missing & value.isna()] = "non_numeric_source_value"
    quality.loc[value.notna() & value.le(0)] = "non_positive_value"

    if league == "NBA":
        quality.loc[value.notna() & value.gt(NBA_MAX_ATTENDANCE)] = "implausible_high_value"
        quality.loc[value.notna() & value.gt(0) & value.lt(NBA_MIN_ATTENDANCE)] = "implausible_low_value"

    invalid = quality.ne("valid")
    value.loc[invalid] = np.nan
    return value.astype("float64"), quality


def _parse_nfl_date(date_series: pd.Series, season_year: pd.Series) -> pd.Series:
    text = (
        date_series.astype("string")
        .str.replace(r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)(day)?\s+", "", regex=True, case=False)
        .str.strip()
    )
    month = text.str.extract(r"^([A-Za-z]+)", expand=False).str.lower()
    # NFL year labels identify the season start. January/February games fall
    # in the next calendar year but remain in the same NFL season.
    calendar_year = season_year + month.isin({"january", "february"}).astype("Int64")
    return pd.to_datetime(
        text + " " + calendar_year.astype("string"),
        format="%B %d %Y",
        errors="coerce",
    )


def _canonicalize_nba() -> tuple[pd.DataFrame, pd.Series]:
    source = _read_csv(RAW / "NBA Data.csv")
    attendance, attendance_quality = _clean_attendance(source["attendance"], league="NBA")
    home_score = _numeric(source["homeScore"])
    away_score = _numeric(source["awayScore"])
    score_margin = home_score - away_score
    equal_score = home_score.notna() & away_score.notna() & home_score.eq(away_score)
    home_win = pd.Series(np.nan, index=source.index, dtype="float64")
    home_win.loc[home_score.gt(away_score)] = 1.0
    home_win.loc[home_score.lt(away_score)] = 0.0
    home_win.loc[equal_score] = 0.5
    game_date = pd.to_datetime(source["gameDate"], errors="coerce")
    season_id = game_date.dt.year.where(game_date.dt.month.ge(7), game_date.dt.year - 1)
    game_type = source["gameType"].astype("string").str.strip().replace("", pd.NA).fillna("Unknown")
    include = ~game_type.str.casefold().eq("preseason")

    clean = pd.DataFrame({
        "league": "NBA",
        "game_id": source["gameId"].astype("string").str.strip(),
        "source_row_number": source["source_row_number"],
        "game_date": game_date,
        "season_id": pd.to_numeric(season_id, errors="coerce").astype("Int64"),
        "home_team_id": source["hometeamId"].astype("string").str.strip(),
        "away_team_id": source["awayteamId"].astype("string").str.strip(),
        "home_team": (source["hometeamCity"].astype("string").str.strip() + " " + source["hometeamName"].astype("string").str.strip()).str.strip(),
        "away_team": (source["awayteamCity"].astype("string").str.strip() + " " + source["awayteamName"].astype("string").str.strip()).str.strip(),
        "attendance": attendance,
        "attendance_quality": attendance_quality,
        "game_type": game_type,
        "game_order": 0,
        "home_score": home_score,
        "away_score": away_score,
        "score_margin": score_margin,
        "abs_margin": score_margin.abs(),
        "home_win": home_win,
    })
    return clean.loc[include].copy(), attendance_quality


def _canonicalize_mlb() -> tuple[pd.DataFrame, pd.Series]:
    source = _read_csv(RAW / "MLB Data.csv")
    attendance, attendance_quality = _clean_attendance(source["attendance"], league="MLB")
    home_score = _numeric(source["hruns"])
    away_score = _numeric(source["vruns"])
    score_margin = home_score - away_score
    equal_score = home_score.notna() & away_score.notna() & home_score.eq(away_score)
    home_win = pd.Series(np.nan, index=source.index, dtype="float64")
    home_win.loc[home_score.gt(away_score)] = 1.0
    home_win.loc[home_score.lt(away_score)] = 0.0
    home_win.loc[equal_score] = 0.5
    game_date = pd.to_datetime(
        source["date"].astype("Int64").astype("string"),
        format="%Y%m%d",
        errors="coerce",
    )
    game_type = source["gametype"].astype("string").str.strip().str.casefold().replace("", pd.NA).fillna("Unknown")
    # Spring exhibitions and All-Star games do not represent a franchise's
    # regular opponent game, so they cannot be team-history links.
    include = ~game_type.isin({"exhibition", "allstar"})
    game_id = source["gid"].astype("string").str.strip()
    suffix = pd.to_numeric(game_id.str[-1], errors="coerce")

    clean = pd.DataFrame({
        "league": "MLB",
        "game_id": game_id,
        "source_row_number": source["source_row_number"],
        "game_date": game_date,
        "season_id": _numeric(source["season"]).astype("Int64"),
        "home_team_id": source["hometeam"].astype("string").str.strip().str.upper(),
        "away_team_id": source["visteam"].astype("string").str.strip().str.upper(),
        "home_team": source["hometeam"].astype("string").str.strip().str.upper(),
        "away_team": source["visteam"].astype("string").str.strip().str.upper(),
        "attendance": attendance,
        "attendance_quality": attendance_quality,
        "game_type": game_type,
        "game_order": suffix,
        "home_score": home_score,
        "away_score": away_score,
        "score_margin": score_margin,
        "abs_margin": score_margin.abs(),
        "home_win": home_win,
    })
    return clean.loc[include].copy(), attendance_quality


def _canonicalize_nfl() -> tuple[pd.DataFrame, pd.Series]:
    source = _read_csv(RAW / "NFL Data.csv")
    season_year = _numeric(source["year"]).astype("Int64")
    game_date = _parse_nfl_date(source["date_home"], season_year)
    away_date = _parse_nfl_date(source["date_away"], season_year)
    date_disagreement = game_date.notna() & away_date.notna() & game_date.ne(away_date)
    if date_disagreement.any():
        raise ValueError(f"NFL home/away date fields disagree on {int(date_disagreement.sum())} rows.")

    attendance, attendance_quality = _clean_attendance(source["weekly_attendance_home"], league="NFL")
    winning_score = _numeric(source["pts_win_home"])
    losing_score = _numeric(source["pts_loss_home"])
    winner = source["winner_home"].astype("string").str.strip().str.casefold()
    home_id = source["team_name_home"].astype("string").str.strip()
    away_id = source["team_name_away"].astype("string").str.strip()
    home_winner = winner.eq(home_id.str.casefold())
    away_winner = winner.eq(away_id.str.casefold())
    tie_source = (
        source["tie_home"].astype("string").str.strip().str.casefold().isin({"1", "true", "yes", "y"})
        | source["tie_away"].astype("string").str.strip().str.casefold().isin({"1", "true", "yes", "y"})
    )
    tie_score = winning_score.notna() & losing_score.notna() & winning_score.eq(losing_score)
    tie = tie_source | tie_score
    home_score = pd.Series(np.nan, index=source.index, dtype="float64")
    away_score = pd.Series(np.nan, index=source.index, dtype="float64")
    home_score.loc[home_winner] = winning_score.loc[home_winner]
    away_score.loc[home_winner] = losing_score.loc[home_winner]
    home_score.loc[away_winner] = losing_score.loc[away_winner]
    away_score.loc[away_winner] = winning_score.loc[away_winner]
    home_score.loc[tie] = winning_score.loc[tie]
    away_score.loc[tie] = losing_score.loc[tie]
    home_win = pd.Series(np.nan, index=source.index, dtype="float64")
    home_win.loc[home_winner & ~tie] = 1.0
    home_win.loc[away_winner & ~tie] = 0.0
    home_win.loc[tie] = 0.5
    # The source has one row per regular-season game, with schedule week 1-17.
    game_type = pd.Series("Regular Season", index=source.index, dtype="string")
    slug = home_id.str.casefold().str.replace(r"[^a-z0-9]+", "-", regex=True).str.strip("-")
    week = _numeric(source["week"]).astype("Int64")
    game_id = (
        "nfl-" + game_date.dt.strftime("%Y%m%d").astype("string")
        + "-w" + week.astype("string").str.zfill(2)
        + "-" + slug
    )

    clean = pd.DataFrame({
        "league": "NFL",
        "game_id": game_id,
        "source_row_number": source["source_row_number"],
        "game_date": game_date,
        "season_id": season_year,
        "home_team_id": home_id,
        "away_team_id": away_id,
        "home_team": home_id,
        "away_team": away_id,
        "attendance": attendance,
        "attendance_quality": attendance_quality,
        "game_type": game_type,
        "game_order": 0,
        "home_score": home_score,
        "away_score": away_score,
        "score_margin": home_score - away_score,
        "abs_margin": (winning_score - losing_score).abs(),
        "home_win": home_win,
    })
    return clean, attendance_quality


def _add_previous_game_history(games: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Add each side's immediately previous same-season game, before attendance filtering."""
    base = games.copy()
    if base["game_id"].duplicated().any():
        raise ValueError(f"{base['league'].iloc[0]} has duplicate game IDs.")

    home = base[["game_id", "game_date", "season_id", "home_team_id", "abs_margin", "game_order"]].copy()
    home = home.rename(columns={"home_team_id": "team_id", "abs_margin": "game_abs_margin"})
    home["side"] = "home"
    away = base[["game_id", "game_date", "season_id", "away_team_id", "abs_margin", "game_order"]].copy()
    away = away.rename(columns={"away_team_id": "team_id", "abs_margin": "game_abs_margin"})
    away["side"] = "away"
    appearances = pd.concat([home, away], ignore_index=True)

    date_key = ["team_id", "season_id", "game_date"]
    counts = appearances.groupby(date_key, dropna=False)["game_id"].transform("size")
    order_counts = appearances.groupby(date_key, dropna=False)["game_order"].transform("nunique")
    appearances["ambiguous_order"] = counts.gt(1) & order_counts.lt(counts)
    ambiguous_groups = int(appearances.loc[appearances["ambiguous_order"], date_key].drop_duplicates().shape[0])

    appearances = appearances.sort_values(
        ["team_id", "season_id", "game_date", "game_order", "game_id", "side"],
        kind="mergesort",
    ).reset_index(drop=True)
    group = appearances.groupby(["team_id", "season_id"], sort=False, dropna=False)
    appearances["prev_game_id"] = group["game_id"].shift(1)
    appearances["prev_game_date"] = group["game_date"].shift(1)
    appearances["prev_game_abs_margin"] = group["game_abs_margin"].shift(1)
    prior_row_ambiguous = group["ambiguous_order"].shift(1).fillna(False).astype(bool)
    bad_link = appearances["ambiguous_order"] | prior_row_ambiguous
    appearances.loc[bad_link, ["prev_game_id", "prev_game_date", "prev_game_abs_margin"]] = np.nan

    def status(row: pd.Series) -> str:
        if bool(row["ambiguous_order"]) or bool(row["prior_row_ambiguous"]):
            return "ambiguous_same_day_order"
        if pd.isna(row["prev_game_id"]):
            return "no_prior_game_same_season"
        if pd.isna(row["prev_game_abs_margin"]):
            return "previous_game_margin_missing"
        return "linked"

    appearances["prior_row_ambiguous"] = prior_row_ambiguous
    appearances["prev_status"] = appearances.apply(status, axis=1)

    outputs = []
    for side in ("home", "away"):
        lookup = appearances.loc[appearances["side"].eq(side), [
            "game_id", "prev_game_id", "prev_game_date", "prev_game_abs_margin", "prev_status"
        ]].rename(columns={
            "prev_game_id": f"{side}_prev_game_id",
            "prev_game_date": f"{side}_prev_game_date",
            "prev_game_abs_margin": f"{side}_prev_game_abs_margin",
            "prev_status": f"{side}_prev_game_status",
        })
        outputs.append(lookup)
    result = base.merge(outputs[0], on="game_id", how="left", validate="one_to_one")
    result = result.merge(outputs[1], on="game_id", how="left", validate="one_to_one")

    return result, ambiguous_groups


def _drop_unidentifiable_games(games: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    required = ["game_id", "game_date", "season_id", "home_team_id", "away_team_id"]
    valid = games[required].notna().all(axis=1)
    dropped = int((~valid).sum())
    games = games.loc[valid].copy()
    if games["game_id"].duplicated().any():
        duplicated = games.loc[games["game_id"].duplicated(keep=False), "game_id"].head(10).tolist()
        raise ValueError(f"Duplicate game IDs require review: {duplicated}")
    same_team = games["home_team_id"].eq(games["away_team_id"])
    if same_team.any():
        raise ValueError(f"{int(same_team.sum())} games have the same home and away team ID.")
    return games, dropped


def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    CLEANING_RESULTS.mkdir(parents=True, exist_ok=True)
    builders = {
        "NBA": _canonicalize_nba,
        "MLB": _canonicalize_mlb,
        "NFL": _canonicalize_nfl,
    }
    coverage_rows: list[dict[str, object]] = []
    attendance_rows: list[dict[str, object]] = []
    history_rows: list[dict[str, object]] = []

    for league, builder in builders.items():
        source_path = RAW / f"{league} Data.csv"
        source_count = len(pd.read_csv(source_path, usecols=[0]))
        canonical, attendance_quality = builder()
        game_type_excluded = source_count - len(canonical)
        canonical, unidentifiable = _drop_unidentifiable_games(canonical)
        canonical, ambiguous_groups = _add_previous_game_history(canonical)

        for category, count in attendance_quality.value_counts(dropna=False).items():
            attendance_rows.append({"league": league, "quality": str(category), "rows": int(count)})

        output_path = PROCESSED / f"{league.lower()}_games_clean.csv"
        canonical[OUTPUT_COLUMNS].to_csv(output_path, index=False, date_format="%Y-%m-%d %H:%M:%S")

        coverage_rows.append({
            "league": league,
            "raw_rows": source_count,
            "cleaned_game_rows": len(canonical),
            "game_type_excluded_rows": game_type_excluded,
            "rows_dropped_missing_game_key": unidentifiable,
            "duplicate_game_ids": int(canonical["game_id"].duplicated().sum()),
            "ambiguous_same_day_team_groups": ambiguous_groups,
            "date_min": canonical["game_date"].min(),
            "date_max": canonical["game_date"].max(),
            "season_min": int(canonical["season_id"].min()),
            "season_max": int(canonical["season_id"].max()),
            "rows_with_valid_attendance": int(canonical["attendance"].notna().sum()),
            "rows_with_valid_scores": int(canonical["abs_margin"].notna().sum()),
            "tied_games": int(canonical["home_win"].eq(0.5).sum()),
            "rows_with_home_prior_margin": int(canonical["home_prev_game_abs_margin"].notna().sum()),
            "rows_with_away_prior_margin": int(canonical["away_prev_game_abs_margin"].notna().sum()),
        })
        history_rows.append({
            "league": league,
            "rows_with_unavailable_home_history": int(canonical["home_prev_game_abs_margin"].isna().sum()),
            "rows_with_unavailable_away_history": int(canonical["away_prev_game_abs_margin"].isna().sum()),
            "home_ambiguous_order_rows": int(canonical["home_prev_game_status"].eq("ambiguous_same_day_order").sum()),
            "away_ambiguous_order_rows": int(canonical["away_prev_game_status"].eq("ambiguous_same_day_order").sum()),
        })
        print(
            f"{league}: {source_count:,} raw rows -> {len(canonical):,} cleaned games; "
            f"{int(canonical['attendance'].notna().sum()):,} with usable attendance; "
            f"{ambiguous_groups:,} ambiguous same-day team groups."
        )

    pd.DataFrame(coverage_rows).to_csv(CLEANING_RESULTS / "data_coverage.csv", index=False)
    pd.DataFrame(attendance_rows).to_csv(CLEANING_RESULTS / "attendance_quality.csv", index=False)
    pd.DataFrame(history_rows).to_csv(CLEANING_RESULTS / "history_quality.csv", index=False)
    print(f"Wrote cleaned data to {PROCESSED}")


if __name__ == "__main__":
    main()
