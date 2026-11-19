# Prespecified weekend analysis plan

Recorded 2026-11-19 before any current-game outcome coefficient fitting. Parent agent approved this model before estimation. This is new work extending the historical first-stage-only scope.

- Separate MLB/NBA game-level analyses, calendar years 2001–2019, regular season only.
- Begin from existing first-stage samples to preserve verified same-season histories; require positive valid attendance and decisive current scores. Exclude MLB ties (5) and NBA anomalous tied-score records (2). NBA tied prior-game scores are unusable for lag controls; MLB prior ties receive 0.5 in prior result, as in source cleaning.
- Instrument: Saturday or Sunday from stored game_date, Friday excluded; no timezone conversion because source timezone is not documented.
- Outcome: binary current home win, not an aggregate win percentage. Treatment: recorded attendees / 1,000.
- Main controls: home-team-by-season and away-team-by-season FE, calendar-year-by-month FE, categorical recorded start hour, rest days for each side, immediately previous same-season game result and signed margin for each side. These build on the repository team-season specification, replacing pooled calendar month with year-month common shocks. Recorded start time is a timing proxy; no verified scheduled-versus-actual distinction is available.
- Exact date FE and complete weekday indicators are excluded explicitly because they absorb weekend. Remaining weekly/daily scheduling confounding is unresolved.
- OLS, first stage, reduced form, and 2SLS use exactly the same sample and exogenous controls. IV uses structural-residual sandwich inference, not fitted-treatment OLS standard errors.
- Two-way clusters: current home team and stored game date. Home-team dependence plus shared daily shocks follow historical robustness; few home-team clusters and away-team dependence remain limitations. Use finite-sample correction accounting for absorbed FE rank and t reference df = min(home-team, date clusters)-1.
- Report classical partial F separately from two-way clustered Wald F. Invert single-instrument Anderson–Rubin tests to obtain a weak-instrument-robust confidence set (still conditional on exclusion/independence).
- Predetermined sensitivities: pooled month FE (repository-style), season-week FE (finer calendar shocks), MLB omit all identified doubleheaders. Keep same outcome/control sample for a given model's OLS/FS/RF/2SLS.
- No NFL second-stage extension: inspect suitability but preserve NFL calibration role. Data support a new future analysis; weekend has limited weekday support and distinctive schedule selection.

No specifications or instruments will be selected by current-game outcome significance. The historical multiple-candidate/threshold search remains exploratory.

## Source-audit amendment before outcome inspection

The first execution fit MLB models and emitted progress messages only; no coefficients, standard errors, or significance were printed or inspected. The parent source audit then identified that recorded start time has not been established as a pregame schedule measure. Main, pooled-month, calendar-week, and no-doubleheader specifications therefore omit recorded hour. A separate recorded_hour sensitivity adds it, explicitly caveated as possibly realized timing. This choice is driven by measurement timing, not outcome results. No prior output estimates are selected or reported.
