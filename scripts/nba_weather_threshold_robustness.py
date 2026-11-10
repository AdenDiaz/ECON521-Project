"""Search NBA weather thresholds with exact-date and team-season effects.

Threshold cutoffs are exploratory. Weather is measured at approximate arena
locations using NASA POWER grid-cell estimates; localized weather could still
affect travel and therefore violate exclusion.
"""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
import patsy
import pyhdfe
import statsmodels.api as sm
from scipy.stats import t as student_t
from statsmodels.stats.sandwich_covariance import cov_cluster_2groups

import expanded_iv_screen as expanded

ROOT = Path(__file__).resolve().parents[1]
WEATHER = ROOT / "Data" / "external" / "nba_game_weather_nasa_power_windows.csv"
OUT = ROOT / "results" / "instrument_candidates" / "nba_weather_threshold_robustness.csv"
WINDOWS = (3, 6, 12, 24)
QUANTILES = (0.02, 0.05, 0.10, 0.15, 0.20, 0.25, 0.75, 0.80, 0.85, 0.90, 0.95, 0.98)


def _codes(values: pd.Series) -> tuple[np.ndarray, int]:
    codes, levels = pd.factorize(values, sort=True)
    return codes.astype(np.int64), len(levels)


def main() -> None:
    frame = expanded.load_league("NBA")
    frame = frame.loc[frame.game_date.dt.year.between(2001, 2019)].copy()
    weather = pd.read_csv(WEATHER, parse_dates=["game_date"])
    frame["game_id"] = frame.game_id.astype("string")
    weather["game_id"] = weather.game_id.astype("string")
    frame = frame.merge(weather, on=["game_id", "source_row_number", "game_date"], how="inner", validate="one_to_one")

    candidates: list[tuple[str, str]] = []
    for window in WINDOWS:
        temp = frame[f"temp_{window}h_mean_c"]
        city_month_group = frame.groupby(["home_city_source", "game_month"], sort=False)[temp.name]
        month_mean = city_month_group.transform("mean")
        frame[f"temp_anomaly_{window}h_c"] = temp - month_mean
        for q in QUANTILES:
            cutoffs = city_month_group.transform(lambda x, q=q: x.quantile(q))
            pct = int(round(q * 100))
            if q < 0.5:
                name = f"temp_{window}h_citymonth_below_q{pct:02d}"
                frame[name] = temp.le(cutoffs).where(temp.notna() & cutoffs.notna()).astype(float)
                desc = f"Temperature below city-month {pct}th percentile, prior {window}h"
            else:
                name = f"temp_{window}h_citymonth_above_q{pct:02d}"
                frame[name] = temp.ge(cutoffs).where(temp.notna() & cutoffs.notna()).astype(float)
                desc = f"Temperature above city-month {pct}th percentile, prior {window}h"
            candidates.append((name, desc))
        candidates.append((f"temp_anomaly_{window}h_c", f"Continuous temperature anomaly, prior {window}h"))

        precip = frame[f"precip_{window}h_mm"]
        for cutoff in (0.1, 0.5, 1.0, 2.0):
            name = f"precip_{window}h_ge_{str(cutoff).replace('.', '_')}mm"
            frame[name] = precip.ge(cutoff).where(precip.notna()).astype(float)
            candidates.append((name, f"Precipitation at least {cutoff:g} mm, prior {window}h"))
        positive = precip.loc[precip.gt(0.1)]
        for q in (0.75, 0.90, 0.95):
            cutoff = float(positive.quantile(q)) if len(positive) else np.inf
            name = f"precip_{window}h_positive_q{int(q * 100)}"
            frame[name] = precip.ge(cutoff).where(precip.notna()).astype(float)
            candidates.append((name, f"Top {100 * (1 - q):g}% of positive precipitation, prior {window}h"))

    controls = patsy.dmatrix(
        "0 + C(game_type) + C(game_hour) + home_rest_days + away_rest_days + "
        "home_prev_win + away_prev_win + home_prev_margin_signed + away_prev_margin_signed",
        frame, return_type="dataframe",
    )
    home_season, _ = _codes(frame.home_team_id.astype(str) + "|" + frame.season_id.astype(str))
    away_season, _ = _codes(frame.away_team_id.astype(str) + "|" + frame.season_id.astype(str))
    date, n_date = _codes(frame.date_key)
    ids = np.column_stack([home_season, away_season, date])
    risk = "NBA is indoors, but weather may alter fan and team travel; arena exposures use approximate NASA POWER grid cells."
    rows = []
    for candidate, definition in candidates:
        z = pd.to_numeric(frame[candidate], errors="coerce")
        y = pd.to_numeric(frame.attendance, errors="coerce")
        valid = z.notna() & y.notna() & controls.notna().all(axis=1)
        if valid.sum() < 100 or z.loc[valid].nunique() < 2:
            continue
        data = frame.loc[valid]
        matrix = np.column_stack([
            y.loc[valid].to_numpy(float), z.loc[valid].to_numpy(float),
            controls.loc[valid].to_numpy(float),
        ])
        absorber = pyhdfe.create(
            ids[valid.to_numpy()], drop_singletons=False, compute_degrees=False,
            residualize_method="map",
            options={"transform": "symmetric", "acceleration": "cg", "tol": 1e-10, "iteration_limit": 100000},
        )
        residual = absorber.residualize(matrix)
        design = np.column_stack([residual[:, 2:], residual[:, 1]])
        model = sm.OLS(residual[:, 0], design).fit()
        team, n_team = _codes(data.home_team_id)
        date_valid, n_date_valid = _codes(data.date_key)
        robust = model.get_robustcov_results(cov_type="cluster", groups=team, use_correction=True, df_correction=True)
        covariance, _, _ = cov_cluster_2groups(model, team, date_valid, use_correction=True)
        pos = design.shape[1] - 1
        coef = float(model.params[pos])
        se_two = float(np.sqrt(max(covariance[pos, pos], 0.0)))
        t_two = coef / se_two if se_two > 0 else np.nan
        rows.append({
            "league": "NBA", "candidate": candidate, "definition": definition,
            "n": int(valid.sum()), "home_teams": n_team, "dates": n_date_valid,
            "exposure_share_or_mean": float(z.loc[valid].mean()),
            "coefficient_attendance": coef,
            "partial_F_classical": float((coef / model.bse[pos]) ** 2),
            "home_team_cluster_Wald_F": float(robust.tvalues[pos] ** 2),
            "team_date_two_way_Wald_F": float(t_two ** 2),
            "p_team_date_two_way": float(2 * student_t.sf(abs(t_two), min(n_team, n_date_valid) - 1)),
            "fixed_effects": "home-team x season; away-team x season; exact date",
            "controls": "game type; start hour; rest; previous-game wins and margins",
            "exclusion_risk": risk,
        })
    result = pd.DataFrame(rows).sort_values("team_date_two_way_Wald_F", ascending=False)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT, index=False)
    print(result[["candidate", "n", "exposure_share_or_mean", "coefficient_attendance", "partial_F_classical", "home_team_cluster_Wald_F", "team_date_two_way_Wald_F", "p_team_date_two_way"]].to_string(index=False))
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
