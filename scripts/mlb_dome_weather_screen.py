"""Test outside weather as an MLB attendance IV only when Retrosheet marks a dome.

The analysis is restricted to games whose source sky field is 'dome'. This
removes most direct weather-on-playing-conditions paths but leaves a small
sample and possible travel effects. Outputs are separate from prior reports.
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

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "Data" / "raw" / "MLB Data.csv"
WEATHER_FILE = ROOT / "Data" / "external" / "mlb_dome_weather_nasa_power.csv"
RESULT_FILE = ROOT / "results" / "instrument_candidates" / "mlb_dome_weather_first_stage.csv"
API = "https://power.larc.nasa.gov/api/temporal/hourly/point"
START_YEAR, END_YEAR = 2001, 2019
WINDOWS = (3, 12, 24)
SITES = {
    "STP01": (27.7682, -82.6534, "America/New_York"),       # Tropicana Field
    "HOU03": (29.7573, -95.3555, "America/Chicago"),        # Minute Maid Park
    "PHO01": (33.4455, -112.0667, "America/Phoenix"),        # Chase Field
    "MIL06": (43.0280, -87.9712, "America/Chicago"),         # Miller Park
    "TOR02": (43.6414, -79.3894, "America/Toronto"),         # Rogers Centre
    "MIA02": (25.7781, -80.2196, "America/New_York"),        # Marlins Park
    "MIN03": (44.9800, -93.2580, "America/Chicago"),         # Metrodome
    "MON02": (45.5580, -73.5510, "America/Toronto"),         # Olympic Stadium
    "SEA03": (47.5914, -122.3325, "America/Los_Angeles"),    # Safeco Field
}


def fetch_weather(games: pd.DataFrame) -> pd.DataFrame:
    grouped = {site: grp for site, grp in games.groupby("site", sort=False)}
    cache_dir = Path(gettempdir()) / "econ521_mlb_dome_weather_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    def fetch_site(site: str, rows: pd.DataFrame) -> list[dict[str, object]]:
        location = SITES[site]
        specs, needed = [], set()
        for row in rows.itertuples(index=False):
            minute = expanded.parse_clock(row.starttime)
            if not np.isfinite(minute):
                specs.append((row, None))
                continue
            local = pd.Timestamp(row.game_date).to_pydatetime().replace(
                hour=int(minute // 60), minute=int(minute % 60), tzinfo=ZoneInfo(location[2])
            )
            start = pd.Timestamp(local.astimezone(timezone.utc)).floor("h")
            keys = [(start - pd.Timedelta(hours=i)).strftime("%Y-%m-%dT%H") for i in range(1, 25)]
            needed.update(keys)
            specs.append((row, keys))
        signature = hashlib.sha1(repr((site, location, sorted(needed))).encode()).hexdigest()[:16]
        cache = cache_dir / f"hours_{signature}.csv"
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
                    raise ValueError(f"No NASA POWER hourly data returned for {site}.")
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
            item = {"game_id": str(row.game_id), "source_row_number": int(row.source_row_number), "game_date": row.game_date, "site": site}
            vals = [observed.get(k) for k in keys] if keys else []
            for window in WINDOWS:
                x = vals[:window]
                if len(x) == window and all(v is not None and np.isfinite(v[0]) and np.isfinite(v[1]) for v in x):
                    item[f"precip_{window}h_mm"] = float(sum(v[0] for v in x))
                    item[f"temp_{window}h_mean_c"] = float(np.mean([v[1] for v in x]))
                else:
                    item[f"precip_{window}h_mm"] = np.nan
                    item[f"temp_{window}h_mean_c"] = np.nan
            output.append(item)
        return output

    result = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fetch_site, site, rows): site for site, rows in grouped.items()}
        for i, future in enumerate(as_completed(futures), start=1):
            result.extend(future.result())
            print(f"Fetched MLB dome weather location {i}/{len(grouped)}", flush=True)
    return pd.DataFrame(result)


def main() -> None:
    frame = expanded.load_league("MLB")
    raw = pd.read_csv(RAW, low_memory=False, usecols=["site", "sky"])
    raw["source_row_number"] = np.arange(1, len(raw) + 1)
    frame = frame.merge(raw, on="source_row_number", how="left", validate="one_to_one")
    frame = frame.loc[
        frame.game_date.dt.year.between(START_YEAR, END_YEAR)
        & frame.sky.astype("string").str.casefold().eq("dome")
        & frame.site.isin(SITES)
    ].copy()
    if WEATHER_FILE.exists():
        weather = pd.read_csv(WEATHER_FILE, parse_dates=["game_date"])
        if len(weather) != len(frame) or "precip_24h_mm" not in weather:
            weather = fetch_weather(frame)
    else:
        weather = fetch_weather(frame)
    WEATHER_FILE.parent.mkdir(parents=True, exist_ok=True)
    weather.to_csv(WEATHER_FILE, index=False, date_format="%Y-%m-%d %H:%M:%S")
    frame["game_id"] = frame.game_id.astype("string")
    weather["game_id"] = weather.game_id.astype("string")
    frame = frame.merge(weather, on=["game_id", "source_row_number", "game_date", "site"], how="inner", validate="one_to_one")
    frame["game_hour"] = frame.start_minute.floordiv(60).astype("Int64").astype("string").fillna("Unknown")
    for window in WINDOWS:
        precip, temp = f"precip_{window}h_mm", f"temp_{window}h_mean_c"
        frame[f"any_precip_{window}h"] = frame[precip].ge(0.1).where(frame[precip].notna()).astype(float)
        month_mean = frame.groupby(["site", "game_month"])[temp].transform("mean")
        frame[f"temp_anomaly_{window}h_c"] = frame[temp] - month_mean
    controls = (
        "1 + C(home_team_id) + C(away_team_id) + C(season_id) + C(game_type) + "
        "C(game_weekday) + C(game_month) + C(game_hour) + home_rest_days + away_rest_days + "
        "home_prev_win + away_prev_win + home_prev_margin_signed + away_prev_margin_signed"
    )
    risk = "With the source sky field marked dome, outdoor weather should not alter playing conditions; it can still disrupt team travel. Only 11 team clusters are available."
    specs = []
    for window in WINDOWS:
        specs.extend([
            (f"any_precip_{window}h", f"Any measurable outdoor precipitation in prior {window} hours", "dome_weather"),
            (f"temp_anomaly_{window}h_c", f"Outside temperature anomaly in prior {window} hours", "dome_weather"),
        ])
        for cutoff in (0.5, 1.0, 2.0, 5.0):
            variable = f"precip_{window}h_at_least_{str(cutoff).replace('.', '_')}mm"
            rain = frame[f"precip_{window}h_mm"]
            frame[variable] = rain.ge(cutoff).where(rain.notna()).astype(float)
            specs.append((variable, f"At least {cutoff:g} mm outside precipitation in prior {window} hours", "dome_weather_threshold"))
        temp = f"temp_{window}h_mean_c"
        for cutoff in range(0, 26):
            variable = f"cold_{window}h_below_{cutoff}c"
            temperature = frame[temp]
            frame[variable] = temperature.lt(cutoff).where(temperature.notna()).astype(float)
            specs.append((variable, f"Outside mean temperature below {cutoff:g} C in prior {window} hours", "dome_weather_threshold"))
    rows = []
    for variable, definition, family in specs:
        row = expanded.fit_candidate(frame, "MLB", variable, definition, variable, controls, family, risk)
        if row:
            rows.append(row)
    result = pd.DataFrame(rows).sort_values("two_way_cluster_Wald_F_team_date", ascending=False)
    RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(RESULT_FILE, index=False)
    print(f"Games: {len(frame):,}; teams: {frame.home_team_id.nunique()}; weather coverage: {frame.precip_24h_mm.notna().mean():.2%}")
    print(result[["candidate", "n", "exposure_share_or_mean", "coefficient_attendance", "partial_F_classical", "cluster_Wald_F", "two_way_cluster_Wald_F_team_date", "p_two_way_team_date"]].to_string(index=False))
    print(f"\nWrote {RESULT_FILE} and {WEATHER_FILE}")


if __name__ == "__main__":
    main()
