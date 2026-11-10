"""Robustness for MLB dome-weather candidates with date and team-season effects."""
from __future__ import annotations

from pathlib import Path
import re
import numpy as np
import pandas as pd
import patsy
import pyhdfe
import statsmodels.api as sm
from scipy.stats import t as student_t
from statsmodels.stats.sandwich_covariance import cov_cluster_2groups

import expanded_iv_screen as expanded

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "Data" / "raw" / "MLB Data.csv"
WEATHER = ROOT / "Data" / "external" / "mlb_dome_weather_nasa_power.csv"
GRID = ROOT / "results" / "instrument_candidates" / "mlb_dome_weather_first_stage.csv"
OUT = ROOT / "results" / "instrument_candidates" / "mlb_dome_weather_robustness.csv"


def _codes(values: pd.Series) -> tuple[np.ndarray, int]:
    codes, levels = pd.factorize(values, sort=True)
    return codes.astype(np.int64), len(levels)


def main() -> None:
    frame = expanded.load_league("MLB")
    raw = pd.read_csv(RAW, low_memory=False, usecols=["site", "sky"])
    raw["source_row_number"] = np.arange(1, len(raw) + 1)
    frame = frame.merge(raw, on="source_row_number", how="left", validate="one_to_one")
    frame = frame.loc[
        frame.game_date.dt.year.between(2001, 2019)
        & frame.sky.astype("string").str.casefold().eq("dome")
        & frame.site.isin({"STP01", "HOU03", "PHO01", "MIL06", "TOR02", "MIA02", "MIN03", "MON02", "SEA03"})
    ].copy()
    weather = pd.read_csv(WEATHER, parse_dates=["game_date"])
    frame["game_id"] = frame.game_id.astype("string")
    weather["game_id"] = weather.game_id.astype("string")
    frame = frame.merge(weather, on=["game_id", "source_row_number", "game_date", "site"], how="inner", validate="one_to_one")
    # Re-run every weather threshold under the stronger date and team-season
    # fixed effects. Filtering on the baseline first-stage result here would
    # hide thresholds that become stronger after absorbing common date shocks.
    selected = pd.read_csv(GRID)
    candidates = selected.candidate.drop_duplicates().astype(str).tolist()
    generated: dict[str, pd.Series] = {}
    for candidate in candidates:
        if candidate in frame:
            continue
        match = re.fullmatch(r"cold_(\d+)h_below_(\d+)c", candidate)
        if match:
            window, cutoff = match.groups()
            temperature = frame[f"temp_{window}h_mean_c"]
            generated[candidate] = temperature.lt(float(cutoff)).where(temperature.notna()).astype(float)
            continue
        match = re.fullmatch(r"any_precip_(\d+)h", candidate)
        if match:
            precipitation = frame[f"precip_{match.group(1)}h_mm"]
            generated[candidate] = precipitation.ge(0.1).where(precipitation.notna()).astype(float)
            continue
        match = re.fullmatch(r"precip_(\d+)h_at_least_(\d+_\d+)mm", candidate)
        if match:
            window, cutoff = match.groups()
            precipitation = frame[f"precip_{window}h_mm"]
            generated[candidate] = precipitation.ge(float(cutoff.replace("_", "."))).where(precipitation.notna()).astype(float)
            continue
        match = re.fullmatch(r"temp_anomaly_(\d+)h_c", candidate)
        if match:
            temp = frame[f"temp_{match.group(1)}h_mean_c"]
            month_mean = frame.groupby(["site", "game_month"])[temp.name].transform("mean")
            generated[candidate] = temp - month_mean
    if generated:
        frame = pd.concat([frame, pd.DataFrame(generated, index=frame.index)], axis=1)
    controls = patsy.dmatrix(
        "0 + C(game_type) + C(game_hour) + home_rest_days + away_rest_days + "
        "home_prev_win + away_prev_win + home_prev_margin_signed + away_prev_margin_signed",
        frame, return_type="dataframe",
    )
    rows = []
    for candidate in candidates:
        variable = pd.to_numeric(frame[candidate], errors="coerce")
        outcome = pd.to_numeric(frame.attendance, errors="coerce")
        valid = variable.notna() & outcome.notna() & controls.notna().all(axis=1)
        data = frame.loc[valid]
        x = controls.loc[valid].to_numpy(dtype=float)
        matrix = np.column_stack([outcome.loc[valid].to_numpy(float), variable.loc[valid].to_numpy(float), x])
        home_season, n_hs = _codes(data.home_team_id.astype(str) + "|" + data.season_id.astype(str))
        away_season, n_as = _codes(data.away_team_id.astype(str) + "|" + data.season_id.astype(str))
        date, n_date = _codes(data.date_key)
        ids = np.column_stack([home_season, away_season, date])
        absorber = pyhdfe.create(
            ids, drop_singletons=False, compute_degrees=False, residualize_method="map",
            options={"transform": "symmetric", "acceleration": "cg", "tol": 1e-10, "iteration_limit": 100000},
        )
        matrix = absorber.residualize(matrix)
        design = np.column_stack([matrix[:, 2:], matrix[:, 1]])
        model = sm.OLS(matrix[:, 0], design).fit()
        team, n_team = _codes(data.home_team_id)
        robust = model.get_robustcov_results(cov_type="cluster", groups=team, use_correction=True, df_correction=True)
        covariance, _, _ = cov_cluster_2groups(model, team, date, use_correction=True)
        position = design.shape[1] - 1
        coef = float(model.params[position])
        se_two_way = float(np.sqrt(max(covariance[position, position], 0.0)))
        t_two_way = coef / se_two_way if se_two_way else np.nan
        rows.append({
            "candidate": candidate,
            "n": int(valid.sum()),
            "home_teams": int(n_team),
            "coefficient_attendance": coef,
            "partial_F_classical": float((coef / model.bse[position]) ** 2),
            "home_team_cluster_Wald_F": float(robust.tvalues[position] ** 2),
            "team_date_two_way_Wald_F": float(t_two_way ** 2),
            "p_team_date_two_way_df9": float(2 * student_t.sf(abs(t_two_way), min(n_team, n_date) - 1)),
            "home_team_season_groups": n_hs,
            "away_team_season_groups": n_as,
            "date_fixed_effects": True,
            "absorbed_fixed_effect_dimensions": 3,
        })
    result = pd.DataFrame(rows).sort_values("team_date_two_way_Wald_F", ascending=False)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT, index=False)
    print(f"Indoor-marked observations: {len(frame):,}; home teams: {frame.home_team_id.nunique()}")
    print(result.to_string(index=False))
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
