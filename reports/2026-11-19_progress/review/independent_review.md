# Independent econometric and assignment review

Reviewed the actual draft PPTX and each of its 12 rendered slide PNGs, not only the author's summary. Draft location: artifact-session export directory ending `d765bdead367d6a8568420b94372df2c37e1d4eb5a71d593e83f9c771a98f81b`; presentation `research_progress_draft.pptx`. Also read actual new analysis code, model CSV, audits, AR JSON, sample manifests, trusted-library checks, franchise-cluster sensitivity and its code, research report Markdown/PDF, and source map.

## Outcome

The analysis and draft content support the requested preliminary update. No econometric blocker or numerical inconsistency was found in the main estimates. The draft has 12 slides including the title, with Tables 1-4 and Figures 1-3. Historical work, new estimates and planned work are visibly distinguished. NFL is correctly confined to calibration. Delivery should follow the small layout and documentation corrections below and a final PDF export/page-count check.

## Verified from code and saved outputs

- New main samples: MLB45,642; NBA22,693. All nine league/specification sample manifests contain unique game IDs, positive attendance, decisive binary home-win outcomes, and stored-calendar Saturday/Sunday weekend coding. Four equation rows within every specification have identical N, cluster counts and full control rank.
- Main 2SLS estimates are probability .00276323 for MLB and −.01089224 for NBA per1,000 recorded attendees, correctly displayed as +.28pp and −1.09pp. All displayed main confidence intervals, OLS, first-stage and reduced-form values match the saved CSV after scaling/rounding.
- Code estimates 2SLS using the instrument projection and **structural residuals**. The covariance is a home-team/date inclusion–exclusion sandwich with dimension-specific CR1 factors and full FE-rank correction. It is not naive fitted-attendance OLS inference. Saved independent `linearmodels IV2SLS` comparison errors are ~1e−14 for coefficients and ~1e−16 for covariance after matching rank correction.
- Home/away team-season effects are absorbed with pyhdfe; exact categorical-FE rank comes from bipartite connected components; dependent exogenous columns are removed via pivoted QR. Main omits recorded hour and full weekday/date FE. Weekend rank and residualized variance are checked, so the model is identified algebraically.
- Independent calculations verify IV=RF/FS, clustered Wald F=t², all t-based intervals/p-values, and all AR endpoints. Each AR endpoint yields exactly the inverted t-critical boundary; AR p at zero equals RF p. Weak-relevance robustness remains conditional on valid exclusion/independence and approximate few-cluster inference, as correctly acknowledged.
- Clustering uses32 MLB source home-team codes and30 NBA IDs; MLB franchise sensitivity merges FLO/MIA and MON/WAS to30 clusters, preserves every point estimate and sample, and leaves the main 2SLS interval essentially unchanged. This is an inference audit, not outcome-selected specification search. Its files are useful additional documentation.
- Sample audit verifies one-to-one raw/current/prior joins, IDs and team-season chronology. MLB5 current ties, NBA2 anomalous current ties and4 NBA subsequent rows with invalid lag controls are excluded. Regular season restriction explains the reduction from historical first-stage N. Prior-result controls can include MLB ties=.5; current outcome remains binary.
- New sensitivities use ISO **calendar-year×week** effects, pooled calendar month, caveated recorded hour, and MLB doubleheader omission. They are not exact-date FE. No outcome-selected instrument switch is visible.
- Historical Table2/3 and Figure1/2 values match source-specific CSVs. Mixed diagnostic types are explicitly footnoted. The 772-row candidate index is characterized as candidate/specification rows rather than772 independent IVs.
- Native PPTX tables exist on slides3,5,6,9 (and comparison slide2). Native chart references exist on5,7,10. Required exhibits remain editable.

Machine-readable checks: `work/independent_review_checks.json`; reproduction: `work/analysis_env/Scripts/python.exe work/review_checks.py`. This verification does not rerun historical searches or fetch weather.

## Actionable corrections before delivery

1. **Slide10 layout:** two-line title overlaps the green tag in the inspected draft. Shorten to fit one line or move the tag/chart down. This was already identified by the author.
2. **Slide6 layout:** long takeaway wraps to a second line immediately above a crowded small caveat/footer. Shorten the takeaway and give the diagnostic/sample footnote more breathing room. This was already identified by the author.
3. **Report plan wording:** the 'New preliminary analysis: decisions and inference' block currently calls recorded hour a main control, then later explains the amendment excluding it. Clearly label that first block as the **original plan, superseded where amended**, or describe final main controls there and preserve chronology in a separate decision record. The later final-equation paragraphs and slides8/11 already state the correct final specification.
4. **Calendar terminology:** replace 'season-week FE' in the original-plan block with 'calendar-year×week FE' or label it an amended term. The code uses ISO calendar year/week, not weeks since each league's season began.
5. **Source map:** replace nonexistent generic names (`model_plan.md`, `run_weekend_iv.py`, `sample_audit.json`, `estimates.csv`, `ar_confidence_sets.json/csv`) with actual `analysis_plan.md`, `weekend_iv.py`, `data_audit.json`, `model_results.csv`, `anderson_rubin.json`. The parent has already flagged this correction.
6. Include the franchise-cluster sensitivity in the report/bundle reproduction guide if it is delivered. Clarify that32 is the MLB source-code cluster count and30 consolidated franchises is the inference sensitivity; do not silently replace main numbers.
7. Export final slide PDF and verify exactly12 pages; inspect the revised10/6 and every exported page. Only the draft existed at the time of this review; the research report PDF was11 pages, which is outside the assignment slide-count restriction as intended.

## Remaining scientific limitations, adequately disclosed

Weekend independence/exclusion are unestablished. Rest/travel/timing/broadcast/matchup selection can affect outcomes; date and full weekday effects absorb the instrument. Few home-team clusters and shared away-team dependence limit inference; no small-cluster bootstrap is claimed. Recorded gate comparability, actual versus scheduled timing, source timezone, capacity ceilings/crowd composition and MLB doubleheader attribution remain unresolved. Search was exploratory across multiple candidates/thresholds; no confirmatory interpretation is supported. Continuous-treatment 2SLS is not automatically a universal LATE or average attendance effect. These limitations qualify transparent exploratory estimation rather than prevent it.

No further econometric change is required for this class progress update, conditional on maintaining the visible preliminary/assumption qualifications.

## Final closeout review

Reviewed final `outputs/research_progress.pdf` and `research_progress.pptx`, revised `research_update.md/pdf`, and `source_map.md`. The submission PDF has exactly12 pages and editable PPTX exactly12 slides; separate research report PDF has11 pages. Re-inspected final-PDF page renders6,10,12: slide6 footer/takeaway now has adequate separation, slide10 title no longer overlaps its tag, and slide12 gives correctly qualified numerical conclusions. No new clipping or unreadable evidence was observed in these corrected pages.

The final source map now names the actual `analysis_plan.md`, `weekend_iv.py`, `data_audit.json`, `model_results.csv`, and `anderson_rubin.json`. The report's main-specification prose consistently omits recorded hour, separates the source-audit amendment chronology, and uses calendar-week terminology. The stable-franchise inference audit and reproducible helper are documented. Main estimates remain unchanged. Final PPTX retains native tables on3/5/6/9 and native charts on5/7/10.

All requested review corrections are resolved. No remaining delivery blocker was found. Submission PDF preserves rendered appearance as raster pages; editable text/tables/charts remain in the supplied PPTX. Scientific limitations remain those disclosed above.
