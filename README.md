# ECON521 Project: Fan Attendance and Home-Team Performance

## Research question

What is the causal effect of fan attendance on home-team win percentage? The planned outcome is the current game's home-team result, and the treatment is paid/recorded attendance. The proposed instrument is whether each team's immediately previous game was close.

This repository currently completes data preparation and the first-stage relevance analysis only. It does **not** estimate a home-win outcome equation or a second-stage IV effect. The exclusion restriction also remains an open concern: a close previous game may affect subsequent performance through team confidence, fatigue, or other channels besides attendance.

## League scope

- **MLB and NBA:** analysis samples and first-stage models.
- **NFL:** calibration reference only. A one-score reference game is defined as an absolute score margin of at most 3 points.
- **NHL:** excluded because a suitable dataset was not available.

The NFL source file covers seasons **2001–2019**, with calendar dates from 2001-09-09 through 2019-12-29. It has no 2000 or 2020–2023 records, so it does not cover the entire requested 2000–2023 period. In the available file, 1,103 of 4,808 score-valid games (22.94%) ended with a margin of 3 points or less. That lower-tail share is the common percentile anchor used for MLB and NBA.

## First-stage result

The NFL anchor maps to an MLB cutoff of 1 run and an NBA cutoff of 5 points. In the main 1960-onward samples, the joint excluded-instrument F statistics are 1.08 for MLB and 0.07 for NBA. Neither league meets the requested F > 10 relevance screen. A common grid from the 5th through 95th percentile was searched, including league-specific alternatives; the largest conventional joint F was 2.03 for MLB (85th percentile) and 2.53 for NBA (65th percentile). Home-team-clustered p-values at those largest-F thresholds are 0.102 and 0.072. Full-history sensitivity results are in `results/first_stage/full_history_sensitivity.csv`.

No tested threshold meets both F > 10 and the 5% clustered-significance screen, so the processed first-stage samples retain the NFL anchor and are explicitly marked as not passing F > 10. The threshold search is documented in `results/first_stage/report.md` and its CSV outputs. These findings should be considered before proceeding to a second stage.

## Data and folders

| Path | Contents |
|---|---|
| `Data/raw/` | Original league CSVs, preserved without edits. |
| `Data/processed/` | Canonical cleaned game-level files and first-stage samples. |
| `scripts/prepare_data.py` | Cleans raw sources and builds within-season prior-game histories. |
| `scripts/first_stage.py` | Computes the NFL anchor, calibrates margins, estimates first stages, and writes summaries. |
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
```

The preparation script keeps raw files unchanged. It standardizes dates, season IDs, team IDs, scores, attendance, and game types; excludes NBA preseason and MLB exhibition/All-Star games from team-game histories; and adds the preceding same-season game for each side. Histories are built before excluding current games with unusable attendance, so a game can remain a valid prior game even if its own attendance is missing.

Attendance must be positive and numeric for a current-game first-stage observation. NBA attendance below 100 or above 100,000 is flagged as implausible. Ambiguous same-day MLB doubleheader order is marked and not used for lag construction. NFL January/February dates are assigned to the calendar year after the season-start year, while `season_id` remains the source season year.

The main MLB and NBA screen starts in January 1960, matching the exploratory notebook's provisional scope; full-history sensitivity is also reported. The percentile grid tests 5%, 10%, …, 95% plus the exact NFL anchor. The models include home-team, away-team, season, game-type, weekday, and month fixed effects, and use separate close-prior-game indicators for the current home and away teams. Standard errors are clustered by current home team.

## Data sources

| League | Source |
|---|---|
| MLB | [MLB Stats Format](https://github.com/btelle/mlb-stats-format) |
| NBA | [Historical NBA Data](https://www.kaggle.com/datasets/eoinamoore/historical-nba-data-and-player-box-scores) |
| NFL | [NFL Attendance Data](https://github.com/emilp-tuwien/nfl-attendance-prediction) |

**Course:** ECON521 — Causal Econometrics
