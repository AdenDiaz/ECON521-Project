# MLB franchise-cluster inference sensitivity

This is an inference audit prompted by the source-ID review, after primary estimation; it is not selected by outcome significance. Primary model_results.csv and its other saved outputs are unchanged (hashes verified).

Merge FLO and MIA into one home-franchise cluster and MON and WAS into another. All other home IDs remain distinct. These mappings consolidate renamed/relocated franchise histories. Keep date clusters, sample, point estimates, team-season effects, and exogenous controls exactly as in the main specification. Cluster count falls from 32 raw codes to 30 home franchises; dates remain 3,392. The t reference df becomes 29. CGM/CR1 formula and full absorbed-FE rank correction are unchanged.

| Equation | Estimate | Alternate SE | Alternate 95% CI |
|---|---:|---:|---:|
| OLS (home-win pp/1,000) | -0.0296 | 0.0457 | [-0.1231, 0.0640] |
| FS (attendees/weekend) | 5385.5558 | 400.2587 | [4566.9349, 6204.1767] |
| RF (home-win pp/weekend) | 1.4882 | 0.4115 | [0.6465, 2.3298] |
| 2SLS (home-win pp/1,000) | 0.2763 | 0.0839 | [0.1047, 0.4479] |

Alternate first-stage two-way clustered Wald F = 181.042; classical partial F remains unchanged because clustering does not alter the homoskedastic calculation.

All primary point estimates match to numerical precision. The 2SLS covariance also matches linearmodels IV2SLS after matching absorbed-FE degrees of freedom. Few home-franchise clusters, away-team dependence, and unresolved weekend exclusion remain limitations.

Reproduce: python scripts/second_stage_update/franchise_cluster_sensitivity.py
