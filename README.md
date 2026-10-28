# ECON521 Project: The Causal Effect of Fan Attendance on Home-Field Advantage

## Overview

This project investigates the causal effect of fan attendance on home-team performance across the four major North American professional sports leagues: MLB, NBA, NFL, and NHL.

**Research Question:** What is the causal effect of fan attendance on home-team win percentage, and how does this effect differ across sports?

## Research Design

- **Outcome Variable:** Home-team win percentage.
- **Treatment Variable:** Fan attendance, measured by the number of spectators at a game.
- **Proposed Instrumental Variable (IV):** Closeness of the team's previous game.

Attendance is not randomly assigned, as factors such as team popularity and expected performance may influence both attendance and game outcomes. An IV approach will be used to address this potential endogeneity.

The proposed instrument will be evaluated based on its relevance and the plausibility of the exclusion restriction. The latter is a particular concern because previous-game closeness could influence subsequent team performance through channels other than attendance.

The analysis will also compare attendance effects across sports, accounting for differences in scoring systems and typical attendance levels.

## Data Sources

| League | Source |
|---|---|
| MLB | [MLB Stats Format (GitHub)](https://github.com/btelle/mlb-stats-format) |
| NBA | [Historical NBA Data (Kaggle)](https://www.kaggle.com/datasets/eoinamoore/historical-nba-data-and-player-box-scores) |
| NFL | [NFL Attendance Data (GitHub)](https://github.com/emilp-tuwien/nfl-attendance-prediction) |
| NHL | Historical attendance and game-result data source still being investigated. |

**Course:** ECON521 — Causal Econometrics
