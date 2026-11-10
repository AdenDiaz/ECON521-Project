# Data cleaning and first-stage summary

## Scope

This run cleans the three supplied game files, then estimates first-stage attendance regressions for the MLB and NBA only. It does not estimate the home-win outcome equation or a second-stage IV effect.

The main first-stage screen follows the existing notebook's proposed January 1960 cutoff for both MLB and NBA. Full-history results are reported separately as a sensitivity check because the notebook described that cutoff as provisional.

## NFL reference coverage

The NFL file contains 4,808 score-valid rows for seasons 2001–2019 (2001-09-09 through 2019-12-29). It has no season 2000 or seasons 2020–2023. The requested 2000–2023 window therefore contains only the file's observed 2001–2019 games.
Using |winner score − loser score| ≤ 3, 1,103 of 4,808 games are close: 22.94%. The cutoff percentile is the share in the lower tail of the absolute-margin distribution. Complete 256-game seasons yield 22.76%; seasons with fewer than 256 rows: 2001:248, 2002:240, 2016:240, 2017:240.

The same percentile means the MLB/NBA margin cutoff is the empirical inverse-CDF value at this lower-tail share. Discrete scoring means the achieved close-game share may be higher than the target percentile; the output tables report both.

## First-stage findings

NFL-anchor percentile first-stage test passes F > 10 and home-team-cluster p < .05 in both leagues: False.
Common percentile in the tested 5%–95% grid passes both criteria in both leagues: False.
Threshold selection mode: no_strong_threshold_found.
Largest conventional joint F in the full tested grid: NBA: F=2.53 at p=65% (cutoff 12); MLB: F=2.03 at p=85% (cutoff 6).
At the NFL anchor percentile, the discrete MLB/NBA score distributions yield achieved close-game shares of MLB: 29.82% (cutoff 1); NBA: 28.76% (cutoff 5).
Full-history estimates at the NFL anchor: MLB: F=1.44, clustered p=0.781; NBA: F=0.08, clustered p=0.874.

The selected first-stage model includes home-team, away-team, season, game-type, weekday, and month fixed effects. The excluded instruments are separate indicators for a close immediately previous game by the current home and away teams. Standard errors are clustered by current home team. The conventional joint partial F is reported alongside the home-team-cluster F and p-value.

No tested threshold from the 5th through 95th percentile meets the F > 10 screen in either league; therefore no league-specific alternative is selected and the NFL anchor is retained for the prepared samples. F > 10 is a relevance screen, not evidence that the exclusion restriction holds. A previous close game can affect later team confidence or performance directly, so the exclusion restriction remains unresolved. No second-stage estimate is included.

## Cleaning decisions

- Raw data files are preserved under `Data/raw/`; cleaned files are written to `Data/processed/`.
- Attendance is numeric. Missing, nonnumeric, zero, and negative values are unavailable for the first stage. For NBA only, values below 100 or above 100,000 are flagged as implausible and set missing; the raw files retain the source values.
- Game histories are built before restricting current-game observations to positive attendance. A game with missing attendance can still be the previous game if it has a valid score, date, and team identifiers.
- MLB game IDs' final digit orders validated same-day doubleheaders. Cases with ambiguous same-day order receive no lag instrument for the affected observation.
- NBA preseason games and MLB exhibitions/All-Star games are excluded from the franchise-game history. Playoffs and in-season NBA cup games remain in the data.
- NFL January/February dates are assigned to the calendar year after the season-start year; the season ID remains the source `year` field.

See `nfl_reference.csv`, `common_percentile_grid.csv`, `selected_thresholds.csv`, `selected_first_stage.csv`, and `full_history_sensitivity.csv` for counts, cutoffs, coefficients, and F statistics.
