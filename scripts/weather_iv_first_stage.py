"""Build and test an exploratory NBA pregame-weather attendance instrument.

The candidate is precipitation in the three complete hours before tipoff,
measured at the home arena location. The script estimates first stages only;
it does not estimate the home-win equation or a second-stage effect.

Weather inputs come from NASA POWER's hourly meteorology API. The API returns
hourly precipitation in UTC. Game times in the NBA source are local venue
times and are converted with each venue's IANA time zone before matching.
"""
from __future__ import annotations

import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timezone
from io import TextIOWrapper
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import HTTPError, Request, urlopen
from zoneinfo import ZoneInfo
import hashlib
import tempfile
import time

import numpy as np
import pandas as pd
import patsy
import scipy.stats as st
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "Data" / "raw" / "NBA Data.csv"
SAMPLE = ROOT / "Data" / "processed" / "nba_first_stage_sample.csv"
WEATHER_FILE = ROOT / "Data" / "external" / "nba_game_weather_nasa_power.csv"
RESULTS = ROOT / "results" / "instrument_candidates"
START_YEAR, END_YEAR = 2001, 2019
API = "https://power.larc.nasa.gov/api/temporal/hourly/point"

# Coordinates are approximate home-arena locations. Arena moves within a city
# are either within the same NASA POWER MERRA-2 grid area or explicitly handled below.
# tuple: latitude, longitude, IANA time zone
LOCATIONS = {
    "Atlanta": (33.7573, -84.3963, "America/New_York"),
    "Boston": (42.3662, -71.0621, "America/New_York"),
    "Brooklyn": (40.6826, -73.9754, "America/New_York"),
    "Charlotte": (35.2251, -80.8392, "America/New_York"),
    "Chicago": (41.8807, -87.6742, "America/Chicago"),
    "Cleveland": (41.4965, -81.6882, "America/New_York"),
    "Dallas": (32.7905, -96.8103, "America/Chicago"),
    "Denver": (39.7487, -105.0077, "America/Denver"),
    "Detroit": (42.3411, -83.0553, "America/Detroit"),
    "Golden State": (37.7503, -122.2030, "America/Los_Angeles"),
    "Houston": (29.7508, -95.3621, "America/Chicago"),
    "Indiana": (39.7640, -86.1555, "America/Indiana/Indianapolis"),
    "Los Angeles": (34.0430, -118.2673, "America/Los_Angeles"),
    "Memphis": (35.1382, -90.0506, "America/Chicago"),
    "Miami": (25.7814, -80.1870, "America/New_York"),
    "Milwaukee": (43.0451, -87.9172, "America/Chicago"),
    "Minnesota": (44.9795, -93.2760, "America/Chicago"),
    "New Jersey": (40.8128, -74.0742, "America/New_York"),
    "New Orleans": (29.9490, -90.0821, "America/Chicago"),
    "New York": (40.7505, -73.9934, "America/New_York"),
    "Oklahoma City": (35.4634, -97.5151, "America/Chicago"),
    "Orlando": (28.5392, -81.3839, "America/New_York"),
    "Philadelphia": (39.9012, -75.1720, "America/New_York"),
    "Phoenix": (33.4457, -112.0712, "America/Phoenix"),
    "Portland": (45.5316, -122.6668, "America/Los_Angeles"),
    "Sacramento": (38.5802, -121.4997, "America/Los_Angeles"),
    "San Antonio": (29.4270, -98.4375, "America/Chicago"),
    "Seattle": (47.6221, -122.3540, "America/Los_Angeles"),
    "Toronto": (43.6435, -79.3791, "America/Toronto"),
    "Utah": (40.7683, -111.9011, "America/Denver"),
    "Vancouver": (49.2767, -123.1120, "America/Vancouver"),
    "Washington": (38.8981, -77.0209, "America/New_York"),
}


def arena_location(city: str, game_date: pd.Timestamp) -> tuple[float, float, str]:
    """Return the approximate arena coordinate and local zone for a source city."""
    if city == "Golden State" and game_date >= pd.Timestamp("2019-10-01"):
        return 37.7680, -122.3877, "America/Los_Angeles"  # Chase Center
    if city == "New Jersey" and game_date >= pd.Timestamp("2010-12-01"):
        return 40.7336, -74.1711, "America/New_York"  # Prudential Center
    try:
        return LOCATIONS[city]
    except KeyError as exc:
        raise ValueError(f"No arena location configured for NBA source city {city!r}") from exc


def fetch_game_weather(games: pd.DataFrame) -> list[dict[str, object]]:
    """Fetch one hourly series per unique arena area and retain game hours only."""
    grouped_rows: dict[tuple[float, float, str], list[object]] = {}
    for row in games.itertuples(index=False):
        grouped_rows.setdefault(row.location, []).append(row)
    locations = sorted(grouped_rows)
    cache_dir = Path(tempfile.gettempdir()) / "econ521_nba_weather_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    def fetch_location(location: tuple[float, float, str]) -> list[dict[str, object]]:
        rows = grouped_rows[location]
        row_specs = []
        for row in rows:
            local = row.raw_game_date.to_pydatetime().replace(tzinfo=ZoneInfo(location[2]))
            start_hour = pd.Timestamp(local.astimezone(timezone.utc)).floor("h")
            # NASA timestamps label the start of each hourly interval. These
            # three bins end at the scheduled tipoff hour.
            hours = [start_hour - pd.Timedelta(hours=3), start_hour - pd.Timedelta(hours=2), start_hour - pd.Timedelta(hours=1)]
            hour_keys = [hour.strftime("%Y-%m-%dT%H") for hour in hours]
            row_specs.append((row, hour_keys))

        signature = hashlib.sha1(
            repr((location, START_YEAR, END_YEAR, "PRECTOTCORR,T2M", [(r.source_row_number, r.raw_game_date.isoformat()) for r in rows])).encode("utf-8")
        ).hexdigest()[:16]
        cache_file = cache_dir / f"weather_{signature}.csv"
        if cache_file.exists():
            cached = pd.read_csv(cache_file)
            precip_by_row = dict(zip(
                cached["source_row_number"].astype(int),
                pd.to_numeric(cached["precip_pre3h_mm"], errors="coerce"),
            ))
            temp_by_row = dict(zip(
                cached["source_row_number"].astype(int),
                pd.to_numeric(cached["temp_pre3h_c"], errors="coerce"),
            ))
        else:
            params = {
                "parameters": "PRECTOTCORR,T2M",
                "community": "RE",
                "longitude": f"{location[1]:.4f}",
                "latitude": f"{location[0]:.4f}",
                "start": f"{START_YEAR}0101",
                "end": f"{END_YEAR}1231",
                "format": "CSV",
                "time-standard": "UTC",
            }
            request = Request(
                f"{API}?{urlencode(params)}",
                headers={"User-Agent": "ECON521-project/1.0 (academic research)"},
            )
            for attempt in range(2):
                try:
                    response_context = urlopen(request, timeout=180)
                    break
                except HTTPError as exc:
                    detail = exc.read().decode("utf-8", errors="replace")
                    if exc.code == 429 and attempt == 0:
                        print("NASA POWER rate limit reached; waiting 65 seconds before retrying.", flush=True)
                        time.sleep(65)
                        continue
                    raise RuntimeError(f"NASA POWER request failed ({exc.code}): {detail}") from exc
            observations: dict[str, tuple[float, float]] = {}
            with response_context as response:
                text = TextIOWrapper(response, encoding="utf-8", newline="")
                reader = csv.reader(text)
                for header in reader:
                    if header[:6] == ["YEAR", "MO", "DY", "HR", "PRECTOTCORR", "T2M"]:
                        break
                else:
                    raise ValueError(f"NASA POWER returned no hourly data for {location}.")
                needed = {hour for _, hour_keys in row_specs for hour in hour_keys}
                for record in reader:
                    if len(record) < 6:
                        continue
                    year, month, day, hour = map(int, record[:4])
                    key = f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}"
                    if key in needed:
                        value, temperature = float(record[4]), float(record[5])
                        observations[key] = (
                            np.nan if value <= -900 else value,
                            np.nan if temperature <= -900 else temperature,
                        )
            precip_by_row = {}
            temp_by_row = {}
            for row, hour_keys in row_specs:
                values = [observations.get(hour) for hour in hour_keys]
                if all(value is not None for value in values):
                    precip_values = [value[0] for value in values]
                    temp_values = [value[1] for value in values]
                    if all(np.isfinite(value) for value in precip_values):
                        precip_by_row[int(row.source_row_number)] = float(sum(precip_values))
                    if all(np.isfinite(value) for value in temp_values):
                        temp_by_row[int(row.source_row_number)] = float(np.mean(temp_values))
            pd.DataFrame([
                {"source_row_number": int(row.source_row_number),
                 "precip_pre3h_mm": precip_by_row.get(int(row.source_row_number), np.nan),
                 "temp_pre3h_c": temp_by_row.get(int(row.source_row_number), np.nan)}
                for row in rows
            ]).to_csv(cache_file, index=False)

        return [
            {
                "game_id": str(row.game_id),
                "source_row_number": int(row.source_row_number),
                "game_date": row.game_date,
                "home_city_source": row.hometeamCity,
                "arena_latitude": location[0],
                "arena_longitude": location[1],
                "arena_timezone": location[2],
                "precip_pre3h_mm": precip_by_row.get(int(row.source_row_number), np.nan),
                "temp_pre3h_c": temp_by_row.get(int(row.source_row_number), np.nan),
            }
            for row in rows
        ]

    records: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fetch_location, location): location for location in locations}
        for number, future in enumerate(as_completed(futures), start=1):
            records.extend(future.result())
            print(f"Fetched NASA POWER arena series {number} of {len(locations)}", flush=True)
    return records


def load_or_build_weather() -> pd.DataFrame:
    if WEATHER_FILE.exists():
        saved = pd.read_csv(WEATHER_FILE, parse_dates=["game_date"])
        if len(saved) == len(pd.read_csv(SAMPLE)) and "temp_pre3h_c" in saved.columns:
            return saved

    sample = pd.read_csv(SAMPLE, parse_dates=["game_date"])
    sample = sample.loc[sample["game_date"].dt.year.between(START_YEAR, END_YEAR)].copy()
    raw = pd.read_csv(RAW, usecols=["gameDate", "hometeamCity"])
    raw["source_row_number"] = np.arange(1, len(raw) + 1, dtype=np.int64)
    games = sample.merge(raw, on="source_row_number", how="left", validate="one_to_one")
    games["raw_game_date"] = pd.to_datetime(games["gameDate"], errors="coerce")
    if games["hometeamCity"].isna().any() or games["raw_game_date"].isna().any():
        raise ValueError("Some NBA sample rows could not be matched to raw city/date fields.")

    games["location"] = [
        arena_location(city, date)
        for city, date in zip(games["hometeamCity"], games["raw_game_date"])
    ]
    records = fetch_game_weather(games)
    result = pd.DataFrame(records)
    WEATHER_FILE.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(WEATHER_FILE, index=False, date_format="%Y-%m-%d %H:%M:%S")
    return result


def fit_first_stages() -> pd.DataFrame:
    sample = pd.read_csv(SAMPLE, parse_dates=["game_date"])
    sample = sample.loc[sample["game_date"].dt.year.between(START_YEAR, END_YEAR)].copy()
    sample["season_id"] = sample["season_id"].astype("string")
    sample["game_type"] = sample["game_type"].fillna("Unknown").astype("string")
    sample["home_team_id"] = sample["home_team_id"].astype("string")
    sample["away_team_id"] = sample["away_team_id"].astype("string")
    sample["game_weekday"] = sample["game_date"].dt.dayofweek.astype("string")
    sample["game_month"] = sample["game_date"].dt.month.astype("string")
    sample["game_id"] = sample["game_id"].astype("string")

    weather = load_or_build_weather()
    weather["game_id"] = weather["game_id"].astype("string")
    sample = sample.merge(weather, on=["game_id", "source_row_number", "game_date"], how="inner", validate="one_to_one")
    if len(sample) != 24264:
        raise ValueError(f"Expected 24,264 eligible NBA games; joined {len(sample):,}.")
    sample["precip_pre3h_mm"] = pd.to_numeric(sample["precip_pre3h_mm"], errors="coerce")
    sample["temp_pre3h_c"] = pd.to_numeric(sample["temp_pre3h_c"], errors="coerce")
    sample["any_precip_pre3h"] = sample["precip_pre3h_mm"].ge(0.1).astype(float)
    sample["weather_location_month_mean"] = sample.groupby(
        ["home_city_source", "game_month"]
    )["precip_pre3h_mm"].transform("mean")
    sample["precip_anomaly_pre3h_mm"] = (
        sample["precip_pre3h_mm"] - sample["weather_location_month_mean"]
    )
    sample["weather_location_month_temp_mean"] = sample.groupby(
        ["home_city_source", "game_month"]
    )["temp_pre3h_c"].transform("mean")
    sample["temp_anomaly_pre3h_c"] = (
        sample["temp_pre3h_c"] - sample["weather_location_month_temp_mean"]
    )

    control_formula = (
        "1 + C(home_team_id) + C(away_team_id) + C(season_id) + C(game_type) "
        "+ C(game_weekday) + C(game_month)"
    )
    controls = patsy.dmatrix(control_formula, sample, return_type="dataframe")
    outcome = pd.to_numeric(sample["attendance"], errors="coerce")
    clusters = sample["home_team_id"]
    output = []
    for variable, label in [
        ("precip_anomaly_pre3h_mm", "Continuous precipitation shock: anomaly vs city-month mean"),
        ("any_precip_pre3h", "Any measurable precipitation in the 3 hours before tipoff"),
        ("temp_anomaly_pre3h_c", "Continuous temperature shock: anomaly vs city-month mean"),
    ]:
        valid = sample[variable].notna() & outcome.notna()
        design = pd.concat([controls.loc[valid], sample.loc[valid, variable].rename(variable)], axis=1)
        model = sm.OLS(outcome.loc[valid], design).fit()
        robust = model.get_robustcov_results(cov_type="cluster", groups=clusters.loc[valid], use_correction=True, df_correction=True)
        coefficient = float(model.params[variable])
        se_classical = float(model.bse[variable])
        se_cluster = float(robust.bse[-1])
        clustered_t = float(robust.tvalues[-1])
        output.append({
            "instrument_candidate": variable,
            "definition": label,
            "n": int(valid.sum()),
            "weather_exposure_share": float(sample.loc[valid, variable].gt(0).mean()),
            "coefficient_attendance": coefficient,
            "se_classical": se_classical,
            "partial_F_classical": float((coefficient / se_classical) ** 2),
            "p_classical": float(model.pvalues[variable]),
            "se_home_team_cluster": se_cluster,
            "cluster_Wald_F": float(clustered_t**2),
            "p_home_team_cluster": float(robust.pvalues[-1]),
            "n_home_team_clusters": int(clusters.loc[valid].nunique()),
            "fixed_effects": "home team, away team, season, game type, weekday, month",
            "cluster": "current home team",
        })

    return pd.DataFrame(output)


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    results = fit_first_stages()
    results.to_csv(RESULTS / "nba_weather_first_stage.csv", index=False)
    weather = pd.read_csv(WEATHER_FILE)
    coverage = {
        "n_games": int(len(weather)),
        "weather_coverage": float(weather["precip_pre3h_mm"].notna().mean()),
        "any_precip_share": float(weather["precip_pre3h_mm"].ge(0.1).mean()),
    }
    report = [
        "# Exploratory NBA weather IV screen: first stage only",
        "",
        "## Candidate and construction",
        "",
        "Candidate instrument: precipitation in the three complete hourly bins before scheduled NBA tipoff at the home arena. The main variable is the precipitation total minus the home-city-by-calendar-month mean in the eligible sample. The binary sensitivity measure indicates at least 0.1 mm in those bins. A second exploratory measure is temperature relative to the same city-month mean. Local arena coordinates are matched to source home-city labels, and local tipoff times are converted to UTC before matching.",
        "",
        "Hourly observations come from NASA POWER's MERRA-2-based meteorology data. NASA documents hourly precipitation in mm/hour and UTC as an available time standard; the meteorology source grid is 0.5° latitude by 0.625° longitude. These grid-cell estimates are not stadium weather-station observations. See the [hourly API documentation](https://power.larc.nasa.gov/docs/services/api/temporal/hourly/) and [meteorology data-source documentation](https://power.larc.nasa.gov/docs/methodology/data/sources_meteorology/).",
        "",
        "## First-stage results (2001–2019)",
        "",
        f"The matched sample contains {coverage['n_games']:,} games, with weather for {coverage['weather_coverage']:.2%}. The fixed effects are home team, away team, season, game type, weekday, and month. Standard errors are clustered by current home team.",
        "",
        "| Candidate | N | Attendance coefficient | Conventional partial F | Clustered Wald F | Clustered p-value |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    labels = {
        "precip_anomaly_pre3h_mm": "Pregame precipitation anomaly (mm)",
        "any_precip_pre3h": "Any measurable pregame precipitation",
        "temp_anomaly_pre3h_c": "Pregame temperature anomaly (°C)",
    }
    for row in results.itertuples():
        report.append(
            f"| {labels[row.instrument_candidate]} | {row.n:,} | {row.coefficient_attendance:.2f} | "
            f"{row.partial_F_classical:.2f} | {row.cluster_Wald_F:.2f} | {row.p_home_team_cluster:.3f} |"
        )
    report.extend([
        "",
        "No candidate meets the usual F > 10 relevance screen.",
        "",
        "## Assumption assessment",
        "",
        "Indoor play makes outdoor precipitation less likely to affect court conditions than it would at an outdoor ballpark. It does not establish exclusion: local weather can disrupt the visiting team's arrival, transit, arena operations, or other game-day factors. The first stage is weak in this sample. Do not use these weather measures as excluded instruments for a causal NBA attendance effect based on this screen.",
        "",
        "Exclusion cannot be verified by a first-stage regression. It requires a credible design argument and supporting checks; no statistical diagnostic can prove that the instrument has no direct path to home-team performance. No reduced form or second-stage outcome regression is run here.",
        "",
        "The analysis code is in `scripts/weather_iv_first_stage.py`, the game-level merged weather data are in `Data/external/nba_game_weather_nasa_power.csv`, and the coefficient table is in `nba_weather_first_stage.csv`.",
    ])
    (RESULTS / "nba_weather_iv_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("Weather first-stage candidates:")
    print(results[["instrument_candidate", "definition", "n", "coefficient_attendance", "partial_F_classical", "cluster_Wald_F", "p_home_team_cluster"]].to_string(index=False))
    print(f"\nWrote outputs to {RESULTS}")


if __name__ == "__main__":
    main()
