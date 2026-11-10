"""Screen Retrosheet's recorded game-weather fields as MLB attendance predictors.

This is a diagnostic IV screen only. Conditions recorded during a game can
directly affect baseball performance, so strong first stages here do not imply
credible exclusion. Models absorb exact game date and home/away team-season
fixed effects, plus game type, start hour, rest, and previous-game form.
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
RAW = ROOT / "Data" / "raw" / "MLB Data.csv"
OUT = ROOT / "results" / "instrument_candidates" / "mlb_recorded_weather_first_stage.csv"


def _codes(values: pd.Series) -> tuple[np.ndarray, int]:
    codes, levels = pd.factorize(values, sort=True)
    return codes.astype(np.int64), len(levels)


def _fit(frame: pd.DataFrame, variable: str, risk: str) -> dict[str, object] | None:
    z = pd.to_numeric(frame[variable], errors="coerce")
    y = pd.to_numeric(frame.attendance, errors="coerce")
    controls = patsy.dmatrix(
        "0 + C(game_type) + C(game_hour) + home_rest_days + away_rest_days + "
        "home_prev_win + away_prev_win + home_prev_margin_signed + away_prev_margin_signed",
        frame,
        return_type="dataframe",
    )
    valid = z.notna() & y.notna() & controls.notna().all(axis=1)
    if valid.sum() < 100 or z.loc[valid].nunique() < 2:
        return None
    data = frame.loc[valid]
    matrix = np.column_stack([
        y.loc[valid].to_numpy(float), z.loc[valid].to_numpy(float),
        controls.loc[valid].to_numpy(float),
    ])
    home_season, _ = _codes(data.home_team_id.astype(str) + "|" + data.season_id.astype(str))
    away_season, _ = _codes(data.away_team_id.astype(str) + "|" + data.season_id.astype(str))
    date, n_date = _codes(data.date_key)
    absorber = pyhdfe.create(
        np.column_stack([home_season, away_season, date]),
        drop_singletons=False,
        compute_degrees=False,
        residualize_method="map",
        options={"transform": "symmetric", "acceleration": "cg", "tol": 1e-10, "iteration_limit": 100000},
    )
    matrix = absorber.residualize(matrix)
    design = np.column_stack([matrix[:, 2:], matrix[:, 1]])
    model = sm.OLS(matrix[:, 0], design).fit()
    team, n_team = _codes(data.home_team_id)
    robust = model.get_robustcov_results(cov_type="cluster", groups=team, use_correction=True, df_correction=True)
    covariance, _, _ = cov_cluster_2groups(model, team, date, use_correction=True)
    pos = design.shape[1] - 1
    coef = float(model.params[pos])
    se_two = float(np.sqrt(max(covariance[pos, pos], 0.0)))
    t_two = coef / se_two if se_two > 0 else np.nan
    return {
        "candidate": variable,
        "n": int(valid.sum()),
        "home_teams": n_team,
        "dates": n_date,
        "exposure_share_or_mean": float(z.loc[valid].mean()),
        "coefficient_attendance": coef,
        "partial_F_classical": float((coef / model.bse[pos]) ** 2),
        "home_team_cluster_Wald_F": float(robust.tvalues[pos] ** 2),
        "team_date_two_way_Wald_F": float(t_two**2),
        "p_team_date_two_way": float(2 * student_t.sf(abs(t_two), min(n_team, n_date) - 1)),
        "fixed_effects": "home-team x season; away-team x season; exact date",
        "controls": "game type; start hour; rest; previous-game wins and margins",
        "exclusion_risk": risk,
    }


def main() -> None:
    frame = expanded.load_league("MLB")
    raw = pd.read_csv(
        RAW, low_memory=False,
        usecols=["precip", "temp", "windspeed", "sky", "fieldcond"],
    )
    raw["source_row_number"] = np.arange(1, len(raw) + 1)
    frame = frame.merge(raw, on="source_row_number", how="left", validate="one_to_one")
    frame = frame.loc[
        frame.game_date.dt.year.between(2001, 2019)
        & frame.sky.astype("string").str.casefold().isin({"sunny", "cloudy", "overcast", "night"})
    ].copy()

    precip = frame.precip.astype("string").str.strip().str.casefold()
    precip_valid = precip.isin({"none", "rain", "drizzle", "showers", "snow", "heavy fog"})
    frame["recorded_any_precip"] = precip.isin({"rain", "drizzle", "showers", "snow"}).where(precip_valid).astype(float)
    field = frame.fieldcond.astype("string").str.strip().str.casefold()
    frame["recorded_wet_field"] = field.isin({"wet", "damp", "soaked", "muddy"}).where(field.isin({"dry", "wet", "damp", "soaked", "muddy"})).astype(float)
    frame["recorded_sky_cloudy"] = frame.sky.astype("string").str.casefold().isin({"cloudy", "overcast"}).where(
        frame.sky.astype("string").str.casefold().isin({"sunny", "cloudy", "overcast"})
    ).astype(float)

    temp = pd.to_numeric(frame.temp, errors="coerce")
    frame["recorded_temp_f"] = temp.where(temp.between(20, 120))
    wind = pd.to_numeric(frame.windspeed, errors="coerce")
    frame["recorded_wind_mph"] = wind.where(wind.between(0, 75))
    for cutoff in (45, 50, 55, 60, 65):
        frame[f"recorded_temp_below_{cutoff}f"] = frame.recorded_temp_f.le(cutoff).where(frame.recorded_temp_f.notna()).astype(float)
    for cutoff in (80, 85, 90):
        frame[f"recorded_temp_at_least_{cutoff}f"] = frame.recorded_temp_f.ge(cutoff).where(frame.recorded_temp_f.notna()).astype(float)
    for cutoff in (15, 20):
        frame[f"recorded_wind_at_least_{cutoff}mph"] = frame.recorded_wind_mph.ge(cutoff).where(frame.recorded_wind_mph.notna()).astype(float)

    risk = (
        "Severe exclusion concern: recorded rain, temperature, wind, field, and sky conditions "
        "can alter pitching, ball flight, player performance, delays, or game completion directly."
    )
    candidates = [
        "recorded_any_precip", "recorded_wet_field", "recorded_sky_cloudy",
        "recorded_temp_f", "recorded_wind_mph",
        *[f"recorded_temp_below_{c}f" for c in (45, 50, 55, 60, 65)],
        *[f"recorded_temp_at_least_{c}f" for c in (80, 85, 90)],
        *[f"recorded_wind_at_least_{c}mph" for c in (15, 20)],
    ]
    rows = [_fit(frame, variable, risk) for variable in candidates]
    result = pd.DataFrame([row for row in rows if row is not None]).sort_values("team_date_two_way_Wald_F", ascending=False)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT, index=False)
    print(
        f"Games in analysis subset: {len(frame):,}; home teams: {frame.home_team_id.nunique()}; "
        f"recorded precipitation coverage: {frame.recorded_any_precip.notna().mean():.1%}; "
        f"recorded temperature coverage: {frame.recorded_temp_f.notna().mean():.1%}"
    )
    print(result[["candidate", "n", "exposure_share_or_mean", "coefficient_attendance", "partial_F_classical", "home_team_cluster_Wald_F", "team_date_two_way_Wald_F", "p_team_date_two_way"]].to_string(index=False))
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
