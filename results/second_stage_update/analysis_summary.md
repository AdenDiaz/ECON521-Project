# New preliminary weekend-IV estimates

Source: main at 51c94a98731180e5be3415892c6846a0590f0250. All results below newly estimated on 2026-11-19; no NFL causal estimate. Main specification excludes recorded hour.

## Main estimates

| League | Model | Estimate | Clustered SE | 95% CI | N |
|---|---|---:|---:|---:|---:|
| MLB | OLS: home-win pp / 1000 attendees | -0.030 | 0.046 | [-0.123, 0.063] | 45,642 |
| MLB | FS: attendees for weekend | 5385.556 | 400.453 | [4568.827, 6202.284] | 45,642 |
| MLB | RF: home-win pp for weekend | 1.488 | 0.416 | [0.639, 2.338] | 45,642 |
| MLB | 2SLS: home-win pp / 1000 attendees | 0.276 | 0.085 | [0.103, 0.449] | 45,642 |
| NBA | OLS: home-win pp / 1000 attendees | -0.284 | 0.242 | [-0.779, 0.210] | 22,693 |
| NBA | FS: attendees for weekend | 698.714 | 102.117 | [489.861, 907.568] | 22,693 |
| NBA | RF: home-win pp for weekend | -0.761 | 0.700 | [-2.192, 0.670] | 22,693 |
| NBA | 2SLS: home-win pp / 1000 attendees | -1.089 | 0.944 | [-3.021, 0.842] | 22,693 |

MLB home-team/date clusters = 32/3,392 (t df31); NBA = 30/3,033 (df29). MLB historical IDs are not consolidated across relocations/code changes.

Classical partial F: MLB 8,912.91; NBA 947.04. Two-way clustered Wald F (one excluded instrument): MLB 180.87; NBA 46.82. Partial R-squared: .1672/.0424. These diagnostics concern relevance, not validity.

## Weak-instrument-robust confidence sets

- MLB 95% AR set: [0.113, 0.464] home-win percentage points per 1,000 attendees.
- NBA 95% AR set: [-2.941, 1.123] home-win percentage points per 1,000 attendees.

AR sets are conditional on exclusion/independence and approximate clustered inference; they do not remove scheduling confounding.

## Predetermined sensitivity estimates

| League | Specification | 2SLS pp / 1000 | 95% CI | N |
|---|---|---:|---:|---:|
| MLB | main | 0.276 | [0.103, 0.449] | 45,642 |
| MLB | pooled_month | 0.272 | [0.090, 0.454] | 45,642 |
| MLB | calendar_week | 0.249 | [0.077, 0.421] | 45,642 |
| MLB | recorded_hour | 0.293 | [0.083, 0.503] | 45,642 |
| MLB | no_doubleheaders | 0.285 | [0.117, 0.453] | 44,877 |
| NBA | main | -1.089 | [-3.021, 0.842] | 22,693 |
| NBA | pooled_month | -1.119 | [-3.097, 0.858] | 22,693 |
| NBA | calendar_week | -1.052 | [-2.975, 0.870] | 22,693 |
| NBA | recorded_hour | -0.411 | [-2.051, 1.229] | 22,693 |

The NBA recorded-hour comparison changes the point estimate from -1.089 to -0.411 pp / 1,000, illustrating sensitivity to timing controls. Recorded hour is excluded from main because scheduled versus realized timing is unverified. MLB omitting doubleheaders changes +.276 to +.285 pp /1,000 (765 doubleheader rows omitted). No specification was selected using outcome significance.

## Data and design limitations

- Main sample: 45,647 regular MLB first-stage observations minus 5 ties; 22,699 NBA minus 2 anomalous tied-score games and 4 games with unusable immediate prior controls.
- IDs and source-row raw joins are unique and matched; prior links are to the correct team, same season, chronological game (same-day MLB links respect recorded game order).
- Attendance counts have not been validated as paid admissions versus people present. Weekend and date clusters follow stored dates; source timezone is unspecified.
- Exact-date FE or full weekday FE would absorb weekend. Rest and prior-form controls cannot remove all travel, game-time, broadcast, opponent-selection or player-usage effects.
- Home-team/date clustering follows existing robustness; few home-team clusters and arbitrary away-team serial dependence remain limitations. No small-cluster bootstrap or correction for instrument search selection is performed.
- NBA null/negative point estimates do not prove attendance is harmful; confidence intervals are wide and identification remains provisional. MLB positive estimates remain conditional on unresolved IV assumptions.
- The broader instrument search is exploratory. Strong relevance does not establish exclusion, independence or monotonicity.

## Independent estimator validation

Main estimates and all covariance elements match linearmodels IV2SLS after accounting for the exact absorbed-FE degrees-of-freedom factor. See *_trusted_library_check.json. For equations and inference details, see scripts/second_stage_update/README.md.
