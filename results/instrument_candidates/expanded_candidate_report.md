# Expanded attendance-instrument search

## What this report covers

This is an exploratory **first-stage-only** search for instruments for game attendance in the home-team win-percentage model. It retains the earlier closer-previous-game, same-market schedule-conflict, and NBA weather screens, then adds calendar/schedule measures, lagged attendance, NBA weather thresholds, and MLB weather. No reduced form or second stage was estimated. A first-stage F statistic measures relevance; it cannot establish the exclusion restriction.

Current MLB and NBA games are restricted to calendar years **2001–2019**, matching the available NFL reference file. The NFL source does not contain the full 2000–2023 span. NHL remains excluded because no suitable dataset was available. The new searches are exploratory: many definitions and cutoffs were examined, so the reported nominal p-values are not confirmatory.

## Schedule-based candidates above F = 10 in both leagues

The weekend and holiday rows report home-team/date two-way clustered Wald F statistics after absorbing home-team-by-season and away-team-by-season effects and controlling for game type, schedule timing where applicable, rest, and previous-game wins/margins. The home-opener row also absorbs exact-date fixed effects. Calendar indicators are omitted from their own control set. Weekend and holiday indicators vary only by date, so exact-date fixed effects absorb them.

| Candidate | MLB attendance change | MLB robust F | NBA attendance change | NBA robust F | Exclusion assessment |
|---|---:|---:|---:|---:|---|
| Weekend (Saturday/Sunday) | +5,379 | 131.79 | +829 | 64.93 | Best broad compromise to discuss: fan availability is a clear attendance channel. Team routines, rest, travel, and league scheduling may also affect performance directly. Cannot include exact-date FE because weekend is constant within date. |
| Home opener | +17,101 | 193.25 | +2,011 | 110.66 | Remains strong with exact-date FE and team-season FE. Ceremonies, motivation, opening-day roster choices, and strategic scheduling create direct paths to performance. |
| U.S. federal holiday | +4,235 | 43.34 | +470 | 14.20 | Clears 10 in both under team-season FE. Holiday schedules are selected and may change travel and preparation; an exact-date FE absorbs this indicator. |

These are attendance changes in fans per game. F values above are two-way clustered Wald F statistics, calculated as the square of the instrument t statistic. The corresponding classical partial F and home-team-only clustered F are also in the candidate CSVs. Treat F > 10 as a screening rule, not proof of a strong or valid instrument under every clustering design.

## Other candidates

| Candidate family | Strongest results | Main exclusion concern |
|---|---|---|
| Prior home-game attendance | With team-season and exact-date FE, the five-game average has F=206.13 for MLB and F=188.65 for NBA. The most recent home gate has F=196.99 and F=112.81. | Prior crowd size reflects persistent popularity, local demand, team quality, and possible morale effects. It is highly relevant but a poor exclusion argument. |
| Prior-game attendance | With team-season and exact-date FE, attendance at the immediately preceding game has F=163.50 for MLB and F=43.55 for NBA. | Prior crowd and opponent effects can carry through to current team performance; latent team popularity and form remain plausible direct paths. |
| Prior-season average attendance | F=45.98 for MLB and F=17.42 for NBA with exact-date and team-season FE. | It proxies for market/team popularity and latent quality; the within-season measure may also respond to prior performance. |
| MLB dome-marked outside cold | In games with Retrosheet `sky=dome` at the selected dome-capable sites, outside mean temperature below 13°C in the prior 12 hours has F=14.86 (attendance change −1,923); below 14°C has F=13.49; below 10°C in the prior 3 hours has F=12.54. These survive exact-date and team-season FE. | A dome setting reduces the direct playing-weather path, but outside weather can affect team travel. NASA POWER exposure is an approximate grid-cell measure. Only 5,775 complete observations and 10 home-team clusters remain. Many cutoffs were searched. |
| MLB recorded game temperature | Among 32,580 outdoor-marked games, temperature below 55°F has F=35.52; below 65°F F=25.06; recorded temperature as a continuous variable F=22.46, with exact-date and team-season FE. | Severe exclusion risk: temperature directly changes ball flight, pitching, player conditions, and game operations. The source precipitation field has only 117 usable observations in this period, so its estimate is not informative. |
| NBA local weather | Under exact-date and team-season FE, the best searched threshold is 12-hour precipitation of at least 0.5 mm (F=8.95); it does not clear 10. A separate window screen's strongest two-way F is 6.61 for the 12-hour temperature anomaly. | Indoor play helps, but local weather can affect both fan and team travel. NASA POWER measurements approximate arena exposure. No tested NBA weather threshold meets the target. |
| Same-market sports schedule conflicts | The earlier NFL/other-league conflict measures do not reach F=10. MLB's within-two-hours result is below 10 even with exact-date controls; NBA results are weak. | Crowd diversion is plausible, but congestion, transport, team arrival, and schedule coordination can directly affect game conditions. |
| Previous-game closeness | The original NFL-calibrated close-game instrument did not produce a useful first stage in either league. No ordinary joint partial F exceeded 10 across the tested margin grid; extreme clustered results occur at degenerate cutoffs. | Closeness can affect current team form, confidence, fatigue, and fan engagement. This candidate remains weak as well as difficult to exclude. |
| Rest/back-to-back and game-time variables | Several are associated with attendance, but they either weaken with team-season controls or fail to provide a cross-league robust F above 10. Full outputs remain in the grids. | Fatigue, circadian timing, and travel directly affect performance, making exclusion especially difficult. |

## Candidate-selection notes

1. **If you want one common candidate to discuss first, use weekend as the leading candidate to evaluate.** It has the strongest combination of a large first stage in both leagues and a fan-accessibility mechanism. Its exclusion restriction is still uncertain because schedules and player routines differ by day of week.
2. **Home opener is a strong alternative** and survives exact-date fixed effects. Its ceremonies, motivation, and lineup choices make the exclusion argument weaker than the weekend candidate.
3. **Lagged attendance gives very high relevance but the weakest exclusion case.** It measures persistent market/team demand and may affect performance through morale or quality-related channels.
4. **For an MLB-only candidate, dome-marked outside temperature is worth presenting as a sensitivity candidate.** It clears the two-way F > 10 screen after exact-date and team-season controls, but the ten-cluster sample and cutoff search make the result fragile.
5. **Recorded outdoor temperature is a relevance benchmark, not a credible proposed IV.** Its direct path to baseball outcomes is particularly clear. NBA weather and same-market conflicts did not reach the two-way F > 10 threshold.

These rankings do not certify exclusion. No available first-stage test can rule out direct effects on the home-team result. The F > 10 rule is only a relevance screen; the project should separately explain each exclusion argument and treat the broad cutoff search as exploratory.

## Reproducible files

- [`all_candidate_inventory.csv`](all_candidate_inventory.csv) combines **772 candidate/specification rows** from the preserved original and expanded screens into one sortable file.
- [`expanded_first_stage_grid.csv`](expanded_first_stage_grid.csv) contains the calendar, schedule, rest, and attendance-history candidate grid.
- [`team_season_fe_robustness.csv`](team_season_fe_robustness.csv) re-estimates baseline-strong candidates with home- and away-team-by-season fixed effects.
- [`team_season_date_fe_robustness.csv`](team_season_date_fe_robustness.csv) adds exact-date fixed effects where a candidate retains variation; date-level calendar instruments are marked as absorbed.
- [`mlb_dome_weather_first_stage.csv`](mlb_dome_weather_first_stage.csv) and [`mlb_dome_weather_robustness.csv`](mlb_dome_weather_robustness.csv) preserve the full 96-row weather screen and exact-date/team-season robustness for every weather threshold.
- [`mlb_recorded_weather_first_stage.csv`](mlb_recorded_weather_first_stage.csv) screens MLB's source-file weather fields.
- [`nba_weather_window_first_stage.csv`](nba_weather_window_first_stage.csv) and [`nba_weather_threshold_robustness.csv`](nba_weather_threshold_robustness.csv) report the NBA window and percentile/precipitation-threshold searches.
- The original closer-game and same-market conflict analyses remain in [`../first_stage/report.md`](../first_stage/report.md) and [`candidate_screen_report.md`](candidate_screen_report.md).
- Matched NASA POWER observations are preserved under `Data/external/`; MLB source weather is part of the unchanged raw file.

Reproduce the expanded screens from the repository root with:

```bash
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

The NBA/MLB matched hourly files are saved under `Data/external/`, allowing the screens to rerun without another NASA POWER request. The scripts do not modify the earlier analyses or estimate a second stage.
