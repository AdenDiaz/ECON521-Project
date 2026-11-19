# ECON521 Project: Fan Attendance and Home-Team Performance

## Research question

What is the causal effect of fan attendance on the probability of a home-team win? The outcome is the current game's binary home-team result, and the treatment is recorded attendance. A common paid-versus-present attendance definition has not been verified. The initial instrument proposal was whether each team's immediately previous game was close; its tested first stages are weak. Alternative candidates are documented in the historical first-stage screens below.

The November 19, 2026 update adds **new preliminary OLS, first-stage, reduced-form and 2SLS analysis** for MLB and NBA using weekend games as a working instrument. The earlier work stopped at relevance screens. The exclusion restriction remains unresolved for every candidate, including weekend; the new results are conditional exploratory estimates, not established causal effects.

## November 19 research progress update

- [Submission-ready presentation PDF: 12 slides](presentations/2026-11-19_progress/research_progress.pdf)
- [Editable PowerPoint with native tables/charts and embedded chart data](presentations/2026-11-19_progress/research_progress.pptx)
- [Research update report (PDF)](reports/2026-11-19_progress/research_update.pdf) and [editable report](reports/2026-11-19_progress/research_update.md)
- [Slide source map](reports/2026-11-19_progress/source_map.md) and [presentation source](presentations/2026-11-19_progress/source/)
- [New analysis code and inference notes](scripts/second_stage_update/) and [machine-readable results](results/second_stage_update/model_results.csv)
- [Frozen reproducibility bundle](reports/2026-11-19_progress/reproducibility_bundle.zip), [independent review](reports/2026-11-19_progress/review/independent_review.md), and [publication record](reports/2026-11-19_progress/PUBLICATION.md)

The new main samples contain decisive regular-season games in calendar years 2001–2019. Attendance is measured in thousands; outcome coefficients below are percentage points in home-win probability per 1,000 additional recorded attendees.

| League | Main N | Preliminary 2SLS effect | 95% home-team/date clustered t interval |
|---|---:|---:|---:|
| MLB | 45,642 | +0.276 | [0.103, 0.449] |
| NBA | 22,693 | −1.089 | [−3.021, 0.842] |

Both stages use home-team-by-season and away-team-by-season effects, year-month effects, and both teams' pregame rest, prior-game result and signed margin. The main model omits recorded current start hour because scheduled-versus-realized timing is unverified; a separate sensitivity adds it. Exact-date effects and a full weekday set would absorb weekend. OLS, first stage, reduced form and IV use identical rows and controls within each specification. Proper 2SLS structural-residual inference, Anderson–Rubin confidence sets, substantive sensitivities and trusted-library covariance checks are saved with the results.

Weekend may directly affect rest, travel, game timing and matchup selection. NBA estimates are imprecise and change with recorded-hour controls. About 30 home-team clusters, attendance measurement and the exploratory search also limit interpretation. NFL remains calibration only. Raw data and historical analyses are preserved. The analysis input snapshot is `main@51c94a98731180e5be3415892c6846a0590f0250`; frozen handoff artifacts describe their original local-delivery status, before the user subsequently authorized GitHub publication.

## League scope

- **MLB and NBA:** historical first stages and new preliminary game-outcome models.
- **NFL:** calibration reference only. The project's closeness reference is an absolute score margin of at most 3 points; this is not every football one-possession game.
- **NHL:** excluded because a suitable dataset was not available.

The NFL source file covers seasons **2001–2019**, with calendar dates from 2001-09-09 through 2019-12-29. It has no 2000 or 2020–2023 records, so it does not cover the entire requested 2000–2023 period. In the available file, 1,103 of 4,808 score-valid games (22.94%) ended with a margin of 3 points or less. That lower-tail share is the common percentile anchor used for MLB and NBA.

## Historical closeness first-stage result

The supplied NFL file covers calendar years 2001–2019, so current-game MLB/NBA first stages are restricted to those same years. At the 22.94% NFL anchor, the cutoff is 1 run for MLB (28.25% achieved close share) and 5 points for NBA (27.81%). The conventional joint partial F statistics are 3.47 for MLB and 1.72 for NBA; neither meets F > 10.

At the NFL anchor, the home-team-clustered Wald p-values are 0.014 for MLB and 0.068 for NBA. The search tests each integer percentile from 1% through 99%, every observed margin-cutoff transition, and the exact NFL anchor. No conventional joint partial F exceeds 10. The highest conventional F is 3.47 for MLB at a 1-run cutoff and 4.17 for NBA at a zero-point cutoff. Some other thresholds have clustered Wald p-values below .05, but their conventional partial F values remain below 10. The largest clustered Wald F values (184.99 for NBA and 21.39 for MLB) occur at near-degenerate cutoffs that classify 0.008% of NBA prior games or 99.998% of MLB prior games as close; they are not treated as useful first stages. The complete grid and edge cases are documented in `results/first_stage/report.md` and `results/first_stage/common_percentile_grid.csv`.

Because no tested close-game threshold meets F > 10, the processed first-stage samples retain the NFL anchor and are explicitly marked as not passing that relevance screen. This historical pipeline stopped before the second stage under the earlier scope. The separately named November 19 extension evaluates weekend rather than promoting the weak closeness instruments.

## Data and folders

| Path | Contents |
|---|---|
| `Data/raw/` | Original league CSVs, preserved without edits. |
| `Data/processed/` | Canonical cleaned game-level files and first-stage samples. |
| `scripts/prepare_data.py` | Cleans raw sources and builds within-season prior-game histories. |
| `scripts/first_stage.py` | Computes the NFL anchor, calibrates margins, estimates first stages, and writes summaries. |
| `scripts/schedule_conflict_iv_first_stage.py` | Screens same-market cross-league scheduling conflicts as attendance instruments, including an exact-date fixed-effect check. |
| `scripts/weather_iv_first_stage.py` | Screens NASA POWER pregame weather as an NBA attendance instrument. |
| `Data/external/` | Matched hourly NASA POWER weather by NBA game and MLB dome-site game. |
| `results/instrument_candidates/` | First-stage screens and exclusion-restriction discussion for alternative IV candidates. |
| `scripts/expanded_iv_screen.py` | Screens schedule, calendar, rest, and lagged-attendance candidates. |
| `scripts/team_season_fe_candidate_robustness.py` | Re-estimates baseline-strong alternatives with team-season fixed effects. |
| `scripts/team_season_date_fe_candidate_robustness.py` | Checks baseline-strong alternatives with team-season and exact-date fixed effects. |
| `scripts/compile_iv_candidate_inventory.py` | Combines the original and expanded first-stage grids. |
| `notebooks/01_first_stage.ipynb` | Guided, reproducible first-stage workflow. |
| `notebooks/archive/FirstStage_exploratory.ipynb` | Original untracked `hidden owl` Codespaces notebook, retained as an audit trail. |
| `results/cleaning/` | Coverage, attendance-quality, and prior-history summaries. |
| `results/first_stage/` | NFL reference, percentile grid, selected thresholds, model output, and report. |
| `references/seed_paper/` | Seed paper for the presentation. |
| `scripts/second_stage_update/` | New preliminary weekend IV analysis, decision record, validation and inference sensitivity. |
| `results/second_stage_update/` | New outcome estimates, diagnostics, AR sets, sample manifests, data audit and provenance. |
| `presentations/2026-11-19_progress/` | Reviewed 12-slide PDF, editable PPTX and authoring source. |
| `reports/2026-11-19_progress/` | Research report, sources, figures, review and frozen reproducibility bundle. |

## Reproduce

Use Python 3.10 or newer. From the repository root:

For the new preliminary analysis, use an isolated environment (Python 3.12.14 was used). Existing tracked raw/processed inputs suffice; historical searches and weather downloads need not run again:

```bash
python -m pip install -r scripts/second_stage_update/requirements.lock.txt
python scripts/second_stage_update/weekend_iv.py
python scripts/second_stage_update/validate_main.py
python scripts/second_stage_update/franchise_cluster_sensitivity.py
```

See [estimator and reproduction notes](scripts/second_stage_update/README.md). To reproduce the historical cleaning and exploratory screens separately:

```bash
python -m pip install -r requirements.txt
python scripts/prepare_data.py
python scripts/first_stage.py
python scripts/schedule_conflict_iv_first_stage.py
python scripts/weather_iv_first_stage.py
python scripts/expanded_iv_screen.py
python scripts/team_season_fe_candidate_robustness.py
python scripts/team_season_date_fe_candidate_robustness.py
python scripts/nba_weather_window_search.py
python scripts/nba_weather_threshold_robustness.py
python scripts/mlb_dome_weather_screen.py
python scripts/mlb_dome_weather_robustness.py
python scripts/mlb_recorded_weather_screen.py
python scripts/compile_iv_candidate_inventory.py
```

The preparation script keeps raw files unchanged. It standardizes dates, season IDs, team IDs, scores, attendance, and game types; excludes NBA preseason and MLB exhibition/All-Star games from team-game histories; and adds the preceding same-season game for each side. Histories are built before excluding current games with unusable attendance, so a game can remain a valid prior game even if its own attendance is missing.

Attendance must be positive and numeric for a current-game first-stage observation. NBA attendance below 100 or above 100,000 is flagged as implausible. Ambiguous same-day MLB doubleheader order is marked and not used for lag construction. NFL January/February dates are assigned to the calendar year after the season-start year, while `season_id` remains the source season year.

Only current games in calendar years 2001–2019 enter the MLB/NBA first-stage samples; cleaned files and prior-game histories preserve full source coverage. The percentile search tests 1%, 2%, up through 99%, each discrete margin-cutoff transition, and the exact NFL anchor. The models include home-team, away-team, season, game-type, weekday, and month fixed effects, and use separate close-prior-game indicators for the current home and away teams. Standard errors are clustered by current home team.

## Initial alternative IV screen

The first-stage-only screen tested weather before NBA games and same-market cross-league game conflicts for MLB and NBA. None meets a clustered F > 10 screen in both leagues, and none has a proven exclusion restriction. See `results/instrument_candidates/candidate_screen_report.md`. The schedule-conflict script also reports a specification with exact calendar-date fixed effects. The weather analysis uses NASA POWER hourly MERRA-2-based estimates; its game-level matched data are saved in `Data/external/` so the screen can be reproduced without refetching.

## Expanded IV search

The broader exploratory search tests calendar timing, openers, attendance history, NBA weather thresholds, and MLB weather. It keeps all earlier reports and outputs. The consolidated findings, first-stage comparisons, and exclusion concerns are in [`results/instrument_candidates/expanded_candidate_report.md`](results/instrument_candidates/expanded_candidate_report.md). The sortable [`all_candidate_inventory.csv`](results/instrument_candidates/all_candidate_inventory.csv) compiles each candidate and specification from the original and expanded screens.

Strong schedule-based first stages in both leagues include weekend games, home openers, and U.S. federal holidays. Home openers remain strong after exact-date effects; weekend and holiday indicators are absorbed by exact-date effects because they vary only by date. Prior attendance measures are even more predictive but have serious exclusion concerns. For MLB only, selected cold-weather thresholds for dome-marked games retain two-way clustered F > 10 after exact-date and team-season controls, using just 10 home-team clusters. MLB recorded outdoor temperature is predictive but can directly affect play. NBA weather thresholds and same-market schedule conflicts do not reach two-way clustered F > 10. Those historical screens estimate no second stage and establish no exclusion restriction. The new preliminary weekend extension is documented above. The expanded report's "prior-season average attendance" label actually describes the current season's mean of earlier home gates; the research update records this and other source discrepancies without rewriting historical outputs.

## Data sources

| League | Source |
|---|---|
| MLB | [MLB Stats Format](https://github.com/btelle/mlb-stats-format); weather fields follow [Retrosheet event-file documentation](https://www.retrosheet.org/eventfile.htm) |
| NBA | [Historical NBA Data](https://www.kaggle.com/datasets/eoinamoore/historical-nba-data-and-player-box-scores) |
| NFL | [NFL Attendance Data](https://github.com/emilp-tuwien/nfl-attendance-prediction) |
| NBA weather | [NASA POWER hourly API](https://power.larc.nasa.gov/docs/services/api/temporal/hourly/) and [meteorology data sources](https://power.larc.nasa.gov/docs/methodology/data/sources_meteorology/) |
| MLB dome-weather screen | [NASA POWER hourly API](https://power.larc.nasa.gov/docs/services/api/temporal/hourly/); dome marker from Retrosheet's `sky` field |

**Course:** ECON521 — Causal Econometrics
