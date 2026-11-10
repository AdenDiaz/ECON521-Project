"""Search longer pregame-weather windows for NBA attendance relevance.

This writes new files and preserves the original three-hour screen. Weather
is matched at approximate arenas from hourly NASA POWER MERRA-2 estimates.
"""
from __future__ import annotations

import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timezone
import hashlib
from io import TextIOWrapper
from pathlib import Path
from tempfile import gettempdir
from urllib.parse import urlencode
from urllib.request import HTTPError, Request, urlopen
from zoneinfo import ZoneInfo
import time

import numpy as np
import pandas as pd

import expanded_iv_screen as expanded
import weather_iv_first_stage as nba_weather

ROOT = Path(__file__).resolve().parents[1]
WEATHER_FILE = ROOT / "Data" / "external" / "nba_game_weather_nasa_power_windows.csv"
RESULT_FILE = ROOT / "results" / "instrument_candidates" / "nba_weather_window_first_stage.csv"
API = "https://power.larc.nasa.gov/api/temporal/hourly/point"
START_YEAR, END_YEAR = 2001, 2019
WINDOWS = (3, 6, 12, 24)


def fetch_windows(games: pd.DataFrame) -> pd.DataFrame:
    grouped = {}
    for row in games.itertuples(index=False):
        location = nba_weather.arena_location(str(row.hometeamCity), pd.Timestamp(row.gameDate))
        grouped.setdefault(location, []).append(row)
    cache_dir = Path(gettempdir()) / "econ521_nba_weather_window_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    def fetch_location(location):
        rows = grouped[location]
        specs, needed = [], set()
        for row in rows:
            local = pd.Timestamp(row.gameDate).to_pydatetime().replace(tzinfo=ZoneInfo(location[2]))
            start = pd.Timestamp(local.astimezone(timezone.utc)).floor("h")
            keys = [(start - pd.Timedelta(hours=i)).strftime("%Y-%m-%dT%H") for i in range(1, 25)]
            needed.update(keys)
            specs.append((row, keys))
        sig = hashlib.sha1(repr((location, START_YEAR, END_YEAR, sorted(needed))).encode()).hexdigest()[:16]
        cache = cache_dir / f"hours_{sig}.csv"
        if cache.exists():
            cached = pd.read_csv(cache)
            observed = {str(r.hour): (float(r.precip), float(r.temp)) for r in cached.itertuples(index=False)}
        else:
            params = {
                "parameters": "PRECTOTCORR,T2M", "community": "RE",
                "longitude": f"{location[1]:.4f}", "latitude": f"{location[0]:.4f}",
                "start": f"{START_YEAR}0101", "end": f"{END_YEAR}1231",
                "format": "CSV", "time-standard": "UTC",
            }
            request = Request(f"{API}?{urlencode(params)}", headers={"User-Agent": "ECON521-project/1.0"})
            response = None
            for attempt in range(2):
                try:
                    response = urlopen(request, timeout=180)
                    break
                except HTTPError as exc:
                    detail = exc.read().decode("utf-8", errors="replace")
                    if exc.code == 429 and attempt == 0:
                        print("NASA POWER rate limit; retrying in 65 seconds.", flush=True)
                        time.sleep(65)
                        continue
                    raise RuntimeError(f"NASA POWER request failed ({exc.code}): {detail}") from exc
            observed = {}
            with response as stream:
                reader = csv.reader(TextIOWrapper(stream, encoding="utf-8", newline=""))
                for header in reader:
                    if header[:6] == ["YEAR", "MO", "DY", "HR", "PRECTOTCORR", "T2M"]:
                        break
                else:
                    raise ValueError(f"No hourly data returned for {location}.")
                for record in reader:
                    if len(record) < 6:
                        continue
                    y, m, d, h = map(int, record[:4])
                    key = f"{y:04d}-{m:02d}-{d:02d}T{h:02d}"
                    if key in needed:
                        p, t = float(record[4]), float(record[5])
                        observed[key] = (np.nan if p <= -900 else p, np.nan if t <= -900 else t)
            pd.DataFrame([{"hour": k, "precip": v[0], "temp": v[1]} for k, v in observed.items()]).to_csv(cache, index=False)
        output = []
        for row, keys in specs:
            vals = [observed.get(k) for k in keys]
            item = {
                "game_id": str(row.game_id), "source_row_number": int(row.source_row_number),
                "game_date": row.game_date, "home_city_source": str(row.hometeamCity),
                "arena_latitude": location[0], "arena_longitude": location[1], "arena_timezone": location[2],
            }
            for window in WINDOWS:
                x = vals[:window]
                if all(v is not None and np.isfinite(v[0]) and np.isfinite(v[1]) for v in x):
                    item[f"precip_{window}h_mm"] = float(sum(v[0] for v in x))
                    item[f"temp_{window}h_mean_c"] = float(np.mean([v[1] for v in x]))
                else:
                    item[f"precip_{window}h_mm"] = np.nan
                    item[f"temp_{window}h_mean_c"] = np.nan
            output.append(item)
        return output

    result = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fetch_location, loc): loc for loc in grouped}
        for i, future in enumerate(as_completed(futures), start=1):
            result.extend(future.result())
            print(f"Fetched weather location {i}/{len(grouped)}", flush=True)
    return pd.DataFrame(result)


def main() -> None:
    frame = expanded.load_league("NBA")
    frame = frame.loc[frame.game_date.dt.year.between(START_YEAR, END_YEAR)].copy()
    if WEATHER_FILE.exists():
        weather = pd.read_csv(WEATHER_FILE, parse_dates=["game_date"])
        if len(weather) != len(frame) or "precip_24h_mm" not in weather:
            weather = fetch_windows(frame)
    else:
        weather = fetch_windows(frame)
    WEATHER_FILE.parent.mkdir(parents=True, exist_ok=True)
    weather.to_csv(WEATHER_FILE, index=False, date_format="%Y-%m-%d %H:%M:%S")
    frame["game_id"] = frame.game_id.astype("string")
    weather["game_id"] = weather.game_id.astype("string")
    frame = frame.merge(weather, on=["game_id", "source_row_number", "game_date"], how="inner", validate="one_to_one")
    if len(frame) != 24264:
        raise ValueError(f"Expected 24,264 NBA analysis games; got {len(frame):,}.")

    for window in WINDOWS:
        precip, temp = f"precip_{window}h_mm", f"temp_{window}h_mean_c"
        frame[f"any_precip_{window}h"] = frame[precip].ge(0.1).where(frame[precip].notna()).astype(float)
        frame[f"heavy_precip_{window}h"] = frame[precip].ge(1.0).where(frame[precip].notna()).astype(float)
        month_mean = frame.groupby(["home_city_source", "game_month"])[temp].transform("mean")
        frame[f"temp_anomaly_{window}h_c"] = frame[temp] - month_mean
        q10 = frame.groupby(["home_city_source", "game_month"])[temp].transform(lambda x: x.quantile(0.10))
        frame[f"cold_local_q10_{window}h"] = frame[temp].le(q10).where(frame[temp].notna() & q10.notna()).astype(float)
    positive = frame.loc[frame.precip_24h_mm.gt(0.1), "precip_24h_mm"]
    cutoff = float(positive.quantile(0.90)) if len(positive) else np.inf
    frame["heavy_precip_24h_top_decile"] = frame.precip_24h_mm.ge(cutoff).where(frame.precip_24h_mm.notna()).astype(float)

    controls = (
        "1 + C(home_team_id) + C(away_team_id) + C(season_id) + C(game_type) + "
        "C(game_weekday) + C(game_month) + C(game_hour) + home_rest_days + away_rest_days + "
        "home_prev_win + away_prev_win + home_prev_margin_signed + away_prev_margin_signed"
    )
    risk = "NBA play is indoors, but local weather may affect fan and team travel; NASA grid-cell estimates may mismeasure arena exposure."
    specs = []
    for w in WINDOWS:
        specs.extend([
            (f"any_precip_{w}h", f"Any measurable precipitation in prior {w} hours", "weather_window"),
            (f"heavy_precip_{w}h", f"At least 1 mm precipitation in prior {w} hours", "weather_threshold"),
            (f"temp_anomaly_{w}h_c", f"Temperature anomaly over prior {w} hours", "weather_window"),
            (f"cold_local_q10_{w}h", f"City-month bottom-decile temperature over prior {w} hours", "weather_threshold"),
        ])
    specs.append(("heavy_precip_24h_top_decile", f"Top decile of positive 24-hour precipitation (cutoff {cutoff:.2f} mm)", "weather_threshold"))
    rows = []
    for variable, definition, family in specs:
        row = expanded.fit_candidate(frame, "NBA", variable, definition, variable, controls, family, risk)
        if row:
            row["weather_coverage"] = float(frame[variable].notna().mean())
            rows.append(row)
    result = pd.DataFrame(rows).sort_values("two_way_cluster_Wald_F_team_date", ascending=False)
    RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(RESULT_FILE, index=False)
    cols = ["candidate", "n", "coefficient_attendance", "partial_F_classical", "cluster_Wald_F", "two_way_cluster_Wald_F_team_date", "p_two_way_team_date"]
    print(result[cols].to_string(index=False))
    print(f"\nWrote {RESULT_FILE} and {WEATHER_FILE}")


if __name__ == "__main__":
    main()
