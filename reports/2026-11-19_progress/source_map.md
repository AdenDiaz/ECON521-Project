# Slide source map

Snapshot: [AdenDiaz/ECON521-Project](https://github.com/AdenDiaz/ECON521-Project), default branch `main`, commit [`51c94a98731180e5be3415892c6846a0590f0250`](https://github.com/AdenDiaz/ECON521-Project/commit/51c94a98731180e5be3415892c6846a0590f0250), verified with the connected GitHub plugin and a matching local clone on November 19, 2026. New work is uncommitted. No push or submission was made.

Repository paths below refer to this exact commit unless marked **new**. New paths are reproduced inside the analysis bundle. Seed locators give printed page first, then the 1-based PDF page. The seed PDF is `references/seed_paper/ganz-allsop-2023-a-mere-fan-effect-on-home-court-advantage.pdf`.

| Slide | Claims / exhibits | Authoritative source |
|---|---|---|
| 1 | Research question; historical/new status | `README.md`, Research question and League scope; **new** `scripts/second_stage_update/analysis_plan.md` |
| 2 | Seed comparison: question, main sample, attendance, outcome, IV, controls, support | Seed pp. 31–36 (PDF 2–7), Table 1 p. 41 (PDF 12), pp. 44–45 (PDF 15–16); `README.md`; **new** model plan |
| 3 | Table 1: cleaned coverage and distinct estimation samples | `results/cleaning/data_coverage.csv`; `results/first_stage/selected_first_stage.csv`; **new** `results/second_stage_update/data_audit.json` and `model_results.csv` |
| 4 | Original instrument rationale, NFL anchor and qualifications | `README.md`; `scripts/first_stage.py`; `results/first_stage/report.md`; `results/first_stage/nfl_reference.csv`; original proposal `git show 1b87852:README.md` |
| 5 | Table 2: NFL-anchor closeness results; Figure 1: integer-percentile grid | `results/first_stage/selected_first_stage.csv`; `common_percentile_grid.csv`; `report.md`; plot includes 1–99% only, notes full-transition extremes |
| 6 | Table 3: exploratory candidate comparison and F definitions | `results/instrument_candidates/team_season_fe_robustness.csv` (weekend, holiday); `team_season_date_fe_robustness.csv` (opener, prior-five gates); `nba_weather_threshold_robustness.csv`; `mlb_dome_weather_robustness.csv`; `schedule_conflict_first_stage.csv` (baseline ±2h, home-team-only Wald F); inventory supplies row count |
| 7 | Figure 2: adjusted weekend first stages across models | Historical `team_season_fe_robustness.csv`; **new** `model_results.csv` main and prespecified month/week sensitivity rows; `scripts/expanded_iv_screen.py` defines weekend |
| 8 | New outcome, controls, FE, clustering and identified variation | **new** model plan, `weekend_iv.py`, `data_audit.json`, `model_results.csv`; historical `team_season_fe_candidate_robustness.py` |
| 9 | Table 4: same-sample OLS, FS, RF and proper 2SLS with intervals and diagnostics | **new** `results/second_stage_update/model_results.csv`; structural-residual two-way clustered covariance code in `weekend_iv.py` |
| 10 | Figure 3: IV point estimates and confidence intervals; OLS benchmark; AR sets | **new** `model_results.csv`; `anderson_rubin.json` |
| 11 | Exclusion, scheduling, measurement and inference limitations | `expanded_candidate_report.md`; candidate scripts; **new** model plan and audit; research update report |
| 12 | Completed historical work, newly estimated work, unresolved/planned work | All above; historical claims end at the snapshot; new outcome models are explicitly preliminary |

## Exhibit numbering and interpretation

No assigned project Table 1–4 / Figure 1–3 scheme was found in the current README, result reports, scripts, guided notebook or archived notebook source. This presentation assigns: Table 1 data/sample; Table 2 closeness first stages; Table 3 alternatives; Table 4 new outcome models; Figure 1 closeness threshold grid; Figure 2 weekend first stages; Figure 3 preliminary outcome estimates. These are distinct from the seed paper's own exhibit numbers.

CSV-specific numeric fields take precedence over prose summaries. `all_candidate_inventory.csv` is preserved as an index, with its known labeling problems documented in the research report. F statistics are explicitly labeled classical partial or clustered Wald; none is a validity test.
