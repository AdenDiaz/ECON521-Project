# Data cleaning and first-stage summary

## Scope

This run cleans the three supplied game files, then estimates first-stage attendance regressions for the MLB and NBA only. It does not estimate the home-win outcome equation or a second-stage IV effect.

The MLB and NBA current-game analysis is restricted to calendar years 2001–2019, matching the years covered by the supplied NFL file. The cleaned source files retain their full history; prior-game links are built from the full schedules before the current-game date restriction.

## NFL reference coverage

The NFL file contains 4,808 score-valid rows for seasons 2001–2019 (2001-09-09 through 2019-12-29). It has no season 2000 or seasons 2020–2023. The requested 2000–2023 window therefore contains only the file's observed 2001–2019 games.
Using |winner score − loser score| ≤ 3, 1,103 of 4,808 games are close: 22.94%. The cutoff percentile is the share in the lower tail of the absolute-margin distribution. Complete 256-game seasons yield 22.76%; seasons with fewer than 256 rows: 2001:248, 2002:240, 2016:240, 2017:240.

The same percentile means the MLB/NBA margin cutoff is the empirical inverse-CDF value at this lower-tail share. Discrete scoring means the achieved close-game share may be higher than the target percentile; the output tables report both.

## First-stage findings

NFL-anchor percentile first-stage test passes F > 10 and home-team-cluster p < .05 in both leagues: False.
Common percentile in the tested 1%–99% grid and observed margin cutoffs passes both criteria in both leagues: False.
Threshold selection mode: no_strong_threshold_found.
Largest conventional joint partial F in the full tested grid: MLB: F=3.47 at p=22.940932% (cutoff 1; close share 28.25492%); NBA: F=4.17 at p=0.004066% (cutoff 0; close share 0.00813%).
Largest home-team-clustered Wald F by league: MLB: cluster-Wald F=21.39 at p=99.995934% (cutoff 22; close share 99.99786%; conventional F=0.40; clustered p=6.27e-05; active IVs=1); NBA: cluster-Wald F=184.99 at p=0.004066% (cutoff 0; close share 0.00813%; conventional F=4.17; clustered p=3.1e-17; active IVs=2).
At the NFL anchor percentile, the discrete MLB/NBA score distributions yield achieved close-game shares of MLB: 28.25% (cutoff 1); NBA: 27.81% (cutoff 5).

The selected first-stage model includes home-team, away-team, season, game-type, weekday, and month fixed effects. The excluded instruments are separate indicators for a close immediately previous game by the current home and away teams. Standard errors are clustered by current home team. The conventional joint partial F is reported alongside the home-team-cluster F and p-value.

No tested threshold from the 1st through 99th percentile or any observed margin-cutoff transition has a conventional joint partial F above 10 in either league; therefore no league-specific alternative is selected and the NFL anchor is retained for the prepared samples. Clustered Wald p-values fall below .05 at some cutoffs, but the corresponding conventional partial Fs remain below 10. The largest clustered Wald tests occur at degenerate endpoints that classify almost no NBA games or almost every MLB game as close; those sparse or nearly constant indicators are not treated as useful first stages. F > 10 is a relevance screen, not evidence that the exclusion restriction holds. A previous close game can affect later team confidence or performance directly, so the exclusion restriction remains unresolved. No second-stage estimate is included.

## Cleaning decisions

- Raw data files are preserved under `Data/raw/`; cleaned files are written to `Data/processed/`.
- Attendance is numeric. Missing, nonnumeric, zero, and negative values are unavailable for the first stage. For NBA only, values below 100 or above 100,000 are flagged as implausible and set missing; the raw files retain the source values.
- Game histories are built before restricting current-game observations to positive attendance. A game with missing attendance can still be the previous game if it has a valid score, date, and team identifiers.
- MLB game IDs' final digit orders validated same-day doubleheaders. Cases with ambiguous same-day order receive no lag instrument for the affected observation.
- NBA preseason games and MLB exhibitions/All-Star games are excluded from the franchise-game history. Playoffs and in-season NBA cup games remain in the data.
- NFL January/February dates are assigned to the calendar year after the season-start year; the season ID remains the source `year` field.

See `nfl_reference.csv`, `common_percentile_grid.csv`, `selected_thresholds.csv`, and `selected_first_stage.csv` for counts, cutoffs, coefficients, and F statistics.
