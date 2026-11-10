# ECON521 Project: Fan Attendance and Home-Team Performance

## Research question

What is the causal effect of fan attendance on home-team win percentage? The planned outcome is the current game's home-team result, and the treatment is paid/recorded attendance. The initial instrument proposal was whether each team's immediately previous game was close; its tested first stages are weak. Alternative candidates are documented in the first-stage-only screen below.

This repository currently completes data preparation and first-stage relevance analysis only. It does **not** estimate a home-win outcome equation or a second-stage IV effect. The exclusion restriction cannot be established from a first-stage regression and remains unresolved for every candidate tested so far.

## League scope

- **MLB and NBA:** analysis samples and first-stage models.
- **NFL:** calibration reference only. A one-score reference game is defined as an absolute score margin of at most 3 points.
- **NHL:** excluded because a suitable dataset was not available.

The NFL source file covers seasons **2001–2019**, with calendar dates from 2001-09-09 through 2019-12-29. It has no 2000 or 2020–2023 records, so it does not cover the entire requested 2000–2023 period. In the available file, 1,103 of 4,808 score-valid games (22.94%) ended with a margin of 3 points or less. That lower-tail share is the common percentile anchor used for MLB and NBA.

## First-stage result

The supplied NFL file covers calendar years 2001–2019, so current-game MLB/NBA first stages are restricted to those same years. At the 22.94% NFL anchor, the cutoff is 1 run for MLB (28.25% achieved close share) and 5 points for NBA (27.81%). The conventional joint partial F statistics are 3.47 for MLB and 1.72 for NBA; neither meets F > 10.

At the NFL anchor, the home-team-clustered Wald p-values are 0.014 for MLB and 0.068 for NBA. The search tests each integer percentile from 1% through 99%, every observed margin-cutoff transition, and the exact NFL anchor. No conventional joint partial F exceeds 10. The highest conventional F is 3.47 for MLB at a 1-run cutoff and 4.17 for NBA at a zero-point cutoff. Some other thresholds have clustered Wald p-values below .05, but their conventional partial F values remain below 10. The largest clustered Wald F values (184.99 for NBA and 21.39 for MLB) occur at near-degenerate cutoffs that classify 0.008% of NBA prior games or 99.998% of MLB prior games as close; they are not treated as useful first stages. The complete grid and edge cases are documented in `results/first_stage/report.md` and `results/first_stage/common_percentile_grid.csv`.

Because no tested threshold meets F > 10, the processed first-stage samples retain the NFL anchor and are explicitly marked as not passing that relevance screen. The repository stops before the second stage, as requested.

## Data and folders

| Path | Contents |
|---|---|
| `Data/raw/` | Original league CSVs, preserved without edits. |
| `Data/processed/` | Canonical cleaned game-level files and first-stage samples. |
| `scripts/prepare_data.py` | Cleans raw sources and builds within-season prior-game histories. |
| `scripts/first_stage.py` | Computes the NFL anchor, calibrates margins, estimates first stages, and writes summaries. |
| `scripts/schedule_conflict_iv_first_stage.py` | Screens same-market cross-league scheduling conflicts as attendance instruments, including an exact-date fixed-effect check. |
| `scripts/weather_iv_first_stage.py` | Screens NASA POWER pregame weather as an NBA attendance instrument. |
| `Data/external/` | Matched hourly NASA POWER weather by NBA game. |
| `results/instrument_candidates/` | First-stage screens and exclusion-restriction discussion for alternative IV candidates. |
| `notebooks/01_first_stage.ipynb` | Guided, reproducible first-stage workflow. |
| `notebooks/archive/FirstStage_exploratory.ipynb` | Original untracked `hidden owl` Codespaces notebook, retained as an audit trail. |
| `results/cleaning/` | Coverage, attendance-quality, and prior-history summaries. |
| `results/first_stage/` | NFL reference, percentile grid, selected thresholds, model output, and report. |
| `references/seed_paper/` | Seed paper for the presentation. |

## Reproduce

Use Python 3.10 or newer. From the repository root:

```bash
python -m pip install -r requirements.txt
python scripts/prepare_data.py
python scripts/first_stage.py
python scripts/schedule_conflict_iv_first_stage.py
python scripts/weather_iv_first_stage.py
```

The preparation script keeps raw files unchanged. It standardizes dates, season IDs, team IDs, scores, attendance, and game types; excludes NBA preseason and MLB exhibition/All-Star games from team-game histories; and adds the preceding same-season game for each side. Histories are built before excluding current games with unusable attendance, so a game can remain a valid prior game even if its own attendance is missing.

Attendance must be positive and numeric for a current-game first-stage observation. NBA attendance below 100 or above 100,000 is flagged as implausible. Ambiguous same-day MLB doubleheader order is marked and not used for lag construction. NFL January/February dates are assigned to the calendar year after the season-start year, while `season_id` remains the source season year.

Only current games in calendar years 2001–2019 enter the MLB/NBA first-stage samples; cleaned files and prior-game histories preserve full source coverage. The percentile search tests 1%, 2%, up through 99%, each discrete margin-cutoff transition, and the exact NFL anchor. The models include home-team, away-team, season, game-type, weekday, and month fixed effects, and use separate close-prior-game indicators for the current home and away teams. Standard errors are clustered by current home team.

## Alternative IV screen

The first-stage-only screen tested weather before NBA games and same-market cross-league game conflicts for MLB and NBA. None meets a clustered F > 10 screen in both leagues, and none has a proven exclusion restriction. See `results/instrument_candidates/candidate_screen_report.md`. The schedule-conflict script also reports a specification with exact calendar-date fixed effects. The weather analysis uses NASA POWER hourly MERRA-2-based estimates; its game-level matched data are saved in `Data/external/` so the screen can be reproduced without refetching.

## Data sources

| League | Source |
|---|---|
| MLB | [MLB Stats Format](https://github.com/btelle/mlb-stats-format) |
| NBA | [Historical NBA Data](https://www.kaggle.com/datasets/eoinamoore/historical-nba-data-and-player-box-scores) |
| NFL | [NFL Attendance Data](https://github.com/emilp-tuwien/nfl-attendance-prediction) |
| NBA weather | [NASA POWER hourly API](https://power.larc.nasa.gov/docs/services/api/temporal/hourly/) and [meteorology data sources](https://power.larc.nasa.gov/docs/methodology/data/sources_meteorology/) |

**Course:** ECON521 — Causal Econometrics
