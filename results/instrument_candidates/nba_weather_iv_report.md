# Exploratory NBA weather IV screen: first stage only

## Candidate and construction

Candidate instrument: precipitation in the three complete hourly bins before scheduled NBA tipoff at the home arena. The main variable is the precipitation total minus the home-city-by-calendar-month mean in the eligible sample. The binary sensitivity measure indicates at least 0.1 mm in those bins. A second exploratory measure is temperature relative to the same city-month mean. Local arena coordinates are matched to source home-city labels, and local tipoff times are converted to UTC before matching.

Hourly observations come from NASA POWER's MERRA-2-based meteorology data. NASA documents hourly precipitation in mm/hour and UTC as an available time standard; the meteorology source grid is 0.5° latitude by 0.625° longitude. These grid-cell estimates are not stadium weather-station observations. See the [hourly API documentation](https://power.larc.nasa.gov/docs/services/api/temporal/hourly/) and [meteorology data-source documentation](https://power.larc.nasa.gov/docs/methodology/data/sources_meteorology/).

## First-stage results (2001–2019)

The matched sample contains 24,264 games, with weather for 99.98%. The fixed effects are home team, away team, season, game type, weekday, and month. Standard errors are clustered by current home team.

| Candidate | N | Attendance coefficient | Conventional partial F | Clustered Wald F | Clustered p-value |
|---|---:|---:|---:|---:|---:|
| Pregame precipitation anomaly (mm) | 24,260 | -14.16 | 1.50 | 1.31 | 0.261 |
| Any measurable pregame precipitation | 24,264 | -65.20 | 4.02 | 1.35 | 0.256 |
| Pregame temperature anomaly (°C) | 24,260 | 6.46 | 5.33 | 2.66 | 0.114 |

No candidate meets the usual F > 10 relevance screen.

## Assumption assessment

Indoor play makes outdoor precipitation less likely to affect court conditions than it would at an outdoor ballpark. It does not establish exclusion: local weather can disrupt the visiting team's arrival, transit, arena operations, or other game-day factors. The first stage is weak in this sample. Do not use these weather measures as excluded instruments for a causal NBA attendance effect based on this screen.

Exclusion cannot be verified by a first-stage regression. It requires a credible design argument and supporting checks; no statistical diagnostic can prove that the instrument has no direct path to home-team performance. No reduced form or second-stage outcome regression is run here.

The analysis code is in `scripts/weather_iv_first_stage.py`, the game-level merged weather data are in `Data/external/nba_game_weather_nasa_power.csv`, and the coefficient table is in `nba_weather_first_stage.csv`.
