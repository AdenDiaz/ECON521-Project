# Alternative IV candidate screen: first stage only

## Scope and decision

The screen uses the MLB and NBA game samples for calendar years 2001–2019, the years available in the supplied NFL file. NFL is used only to define the original sample window; this report does not use NFL games as an outcome sample. No home-win reduced form or second-stage estimate is run.

**No candidate tested here is ready to use as a credible IV for both leagues.** The available data allow first-stage relevance screens, but they cannot prove the exclusion restriction. The schedule-conflict candidate is modestly predictive of MLB attendance in one narrow definition but does not pass a clustered F > 10 screen and has direct-path risks. The weather candidates have weak NBA first stages.

## Candidate results

| League | Candidate | Attendance change when exposed | Conventional partial F | Home-team-clustered Wald F | Clustered p-value | Screen |
|---|---|---:|---:|---:|---:|---|
| MLB | Other-league game in same metro on same date | -284 | 2.00 | 1.08 | 0.308 | Weak |
| MLB | Other-league game in same metro starts within 2 hours | -1,059 | 12.67 | 5.59 | 0.024 | Promising association, but below clustered F > 10 |
| NBA | Other-league game in same metro on same date | -9 | 0.02 | 0.01 | 0.943 | No first-stage evidence |
| NBA | Other-league game in same metro starts within 2 hours | +136 | 2.18 | 1.63 | 0.212 | Weak |
| NBA | Pre-tipoff precipitation anomaly | -14 per mm | 1.50 | 1.31 | 0.261 | Weak |
| NBA | Any measurable pre-tipoff precipitation | -65 | 4.02 | 1.35 | 0.256 | Weak |
| NBA | Pre-tipoff temperature anomaly | +6 per °C | 5.33 | 2.66 | 0.114 | Weak |

The schedule-conflict baseline regressions include home-team, away-team, season, game-type, weekday, month, and current start-hour fixed effects. NBA weather models use home-team, away-team, season, game-type, weekday, and month fixed effects. Both cluster standard errors by current home team. Exact model output is in `schedule_conflict_first_stage.csv` and `nba_weather_first_stage.csv`.

A stricter schedule-conflict check adds exact calendar-date fixed effects, absorbing common day-level shocks. For the within-two-hours instrument, MLB's coefficient is -1,025 fans (conventional partial F 12.13; clustered Wald F 4.49, p = 0.042), while NBA's coefficient is +124 (conventional F 1.44; clustered F 1.22, p = 0.278). The MLB association persists, but clustered strength remains below 10. The exact-date specification is included in the same CSV.

## Exclusion assessment

### Cross-league schedule conflict

A nearby game in the same metro can divert fans away from the current game, which is a plausible attendance channel. However, concurrent events may also affect traffic, parking, transport, media, or team arrival and game operations. League schedules may also respond to predictable local demand. This is therefore a candidate to investigate, not an established exclusion restriction. The MLB association is the strongest result here, but its cluster-robust Wald F is 5.59, below the conventional F > 10 rule of thumb. The NBA first stage is weak.

### NBA pregame weather

Because NBA games are indoors, local precipitation is less likely to alter playing conditions. It can still disrupt visiting-team travel or other game-day operations. In addition, every measure tested has a low first-stage F. This screen does not support using weather as the NBA instrument.

### MLB weather

Weather at open-air ballparks can directly change the field, ball, player conditions, delays, and game completion. A fixed-roof-only analysis would reduce some of those pathways but has a very small sample concentrated in three teams; inference clustered by team would be unreliable. It is not a defensible fix with the current records alone.

## Recommended next step

Do not estimate a causal second stage using these instruments. To continue with the attendance question, add an external source for a more plausibly exogenous attendance shock, such as localized public-transit service disruptions near the venue, or redesign the estimand around an instrument supported by ticket-sales or attendance-supply data. For any new IV, check first-stage strength with inference that matches the chosen error structure, and make the exclusion argument separately. A significant first stage cannot establish exclusion.

## Reproduction

Run `python scripts/schedule_conflict_iv_first_stage.py` for the schedule-conflict screen. Run `python scripts/weather_iv_first_stage.py` for the NASA POWER NBA weather screen; the matched game-level weather data are cached in `Data/external/` in the repository.
