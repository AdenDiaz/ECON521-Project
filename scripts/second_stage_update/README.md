# Estimator and inference notes

This folder is NEW work, added locally for the 2026-11-19 progress update. The source repository at main commit 51c94a98731180e5be3415892c6846a0590f0250 contained first stages only. Nothing here is a previously completed project result. No commits or pushes are made.

## Reproduce

From the repository root, in an isolated Python >=3.10 environment:

```text
python -m pip install -r scripts/second_stage_update/requirements.lock.txt
python scripts/second_stage_update/weekend_iv.py
```

To reproduce only the saved trusted-library main-model checks, without changing saved estimation outputs:

```text
python scripts/second_stage_update/validate_main.py
```

This writes only the MLB/NBA `*_trusted_library_check.json` files. It independently reconstructs the main 2SLS coefficient and structural-residual covariance, compares every element with `linearmodels` after the absorbed-FE degrees-of-freedom correction, verifies the saved main point estimates and standard errors, and checks that estimation-output hashes remain unchanged.

For the separately reported MLB franchise-code inference sensitivity:

```text
python scripts/second_stage_update/franchise_cluster_sensitivity.py
```

This reads existing raw and processed files, validates their joins, and writes only results/second_stage_update/. No historical search or weather download runs. The saved data_audit.json records filtering and provenance.json hashes all raw/processed CSVs. Sample manifests identify the exact games for each model. model_results.csv holds all coefficients, standard errors, confidence intervals, diagnostics, counts, and model ranks. anderson_rubin.json holds confidence sets and their underlying quadratic coefficients.

## Chosen models

Read analysis_plan.md for the decision record. The final main specification excludes recorded start hour because its pregame timing is unverified. The recorded_hour sensitivity adds this imperfect proxy; its purpose is to compare with the earlier strongest first-stage specification, not to choose by significance.

For each league separately, let Y be the binary current home win, D recorded attendance in thousands, Z Saturday/Sunday on the stored game date, and X the identical exogenous controls in all equations. Estimate:

```text
OLS: Y = beta_OLS D + X gamma + home_team*season FE + away_team*season FE + error
FS:  D = pi Z       + X eta   + home_team*season FE + away_team*season FE + v
RF:  Y = rho Z      + X theta + home_team*season FE + away_team*season FE + e
IV:  Y = beta_IV D  + X gamma + home_team*season FE + away_team*season FE + u; instrument D by Z
```

The main X includes year-month FE, both teams' rest days, prior-game result and signed score margin. Prior quantities use the immediately previous game in the same season. MLB prior ties use result=.5; NBA anomalous tied-score games are unusable as current outcomes or direct prior-result/margin controls. Current tied scores are excluded in both leagues. No current-game performance control enters any equation. Start hour is excluded from main because it may be realized timing. Exact date FE and full weekday controls are deliberately excluded as they absorb Z; this prevents controlling all daily/common weekday scheduling factors.

Predetermined sensitivities replace year-month with pooled month FE or calendar-year-week FE, add recorded start hour, or (MLB only) omit identified doubleheaders. Calendar-week FE still leave within-week weekend variation. A Sunday-specific or Friday-inclusive instrument is not substituted after outcome inspection.

## Inference

All four equations use the same sample for a given specification. Absorb home-team-by-season and away-team-by-season effects by alternating projections, then remove exactly dependent exogenous columns by pivoted QR. The exact rank of the two FE sets is their total category count minus the number of connected components in the bipartite category graph. The full model parameter count adds the rank of residualized X and one treatment/instrument coefficient.

OLS/FS/RF use regression-residual clustered scores. IV uses the 2SLS projection of the complete regressor matrix onto instruments and exogenous controls, and the STRUCTURAL residual Y-X*gamma-D*beta. Its sandwich therefore is not the invalid fitted-attendance OLS variance. A linearmodels IV2SLS comparison verifies all main-model coefficients and covariance elements after matching the absorbed-FE degrees-of-freedom correction.

For each dimension g (home team; date; home-team/date intersection), the score meat has CR1 multiplier G_g/(G_g-1) * (N-1)/(N-K_full). Two-way covariance is home-team meat + date meat - intersection meat, sandwiched by the OLS or IV bread. This accounts for absorbed fixed effects in the finite sample correction. Confidence intervals use t with min(home-team clusters,date clusters)-1 degrees of freedom. Home-team IDs include historical franchise codes/relocations, so the number of clusters can exceed 30; identities are not silently collapsed. There are relatively few home-team clusters. This reference distribution is an approximation; it does not solve few-cluster inference or arbitrary away-team dependence. No wild bootstrap was performed.

The classical partial F uses the homoskedastic residual variance with N-K_full degrees of freedom; it is separately labeled from the squared two-way clustered coefficient t statistic (clustered Wald F, one excluded instrument). Partial R-squared residualizes D and Z on the exogenous controls and FEs. None of these proves instrument validity, and the conventional F>10 heuristic does not directly validate clustered-IV inference.

The 95% Anderson-Rubin set inverts the clustered single-instrument test of the weekend coefficient in Y-b*D on X and Z. Since its coefficient is rho-b*pi, use the joint cluster covariance of RF/FS slopes to solve (rho-b*pi)^2 <= tcrit^2 Var(rho-b*pi). This is weak-instrument robust conditional on instrument validity and the cluster approximation; exclusion violations remain unaddressed.

## Interpretation and limits

A coefficient of .01 means 1 percentage point higher home-win probability per 1,000 attendees. OLS remains an adjusted association; the IV slope is preliminary and conditional on exclusion, independence, relevance, and a defensible continuous-treatment response interpretation. It is not an effect on a season-level aggregate win percentage. The design uses recorded attendance; whether this measures paid admissions or persons actually present is not verified. No capacity correction or fan-composition measure is available.

Weekend games can directly alter rest, travel, clock time, broadcast assignment, opponent selection and player usage. Rest/prior-form controls and finer calendar FE cannot establish exclusion. A positive average attendance response does not prove monotonicity. The instrument search involved multiple candidates and closeness thresholds, making relevance findings exploratory. No inference here corrects for instrument-search selection.

NFL has valid recorded attendance and 4,798 decisive outcomes, but 4,275/4,808 games fall on weekends (mostly Sunday). The retained role is calibration. This is a design/support limitation requiring new league-specific work, not a claim that NFL outcomes are absent.
