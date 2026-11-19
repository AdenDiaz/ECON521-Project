# Reproduce the ECON521 progress update

Snapshot: `AdenDiaz/ECON521-Project`, default branch `main`, commit `51c94a98731180e5be3415892c6846a0590f0250`, verified November 19, 2026. This bundle adds preliminary stage-two work; the source commit contains first stages only. No commit, push or assignment submission was made.

## Contents

- `scripts/second_stage_update/`: new analysis, prespecified plan and amendment, exact Python dependencies, estimator notes, trusted-library validation, franchise-cluster sensitivity.
- `results/second_stage_update/`: all nine league/specification result sets (four equations each), AR confidence sets, sample manifests, data audit, provenance, checks and inference sensitivity.
- `historical_evidence/`: preserved first-stage/cleaning/candidate outputs including the entire 772-row inventory; numerical extracts and research-history audit.
- `research_update.md`, `research_update.pdf`, `report_assets/`, `source_map.md`: complete research documentation.
- `authoring/work/`: slide source, exhibit JSON, report assembly, and submission-PDF builder. Native editable exhibits are also in the separately delivered PPTX.
- `review/`: independent econometric checks and review, plus final package validation evidence.

## New econometric analysis

Use a fresh clone and isolated Python 3.12 environment. Python 3.12.14 was used. The original raw and processed data are already tracked at the pinned commit; no historical search, cleaning rerun or weather fetch is required.

```powershell
git clone https://github.com/AdenDiaz/ECON521-Project.git ECON521-Project
git -C ECON521-Project checkout --detach 51c94a98731180e5be3415892c6846a0590f0250
Copy-Item -Recurse scripts/second_stage_update ECON521-Project/scripts/
Set-Location ECON521-Project
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r scripts/second_stage_update/requirements.lock.txt
.venv/Scripts/python.exe scripts/second_stage_update/weekend_iv.py
.venv/Scripts/python.exe scripts/second_stage_update/validate_main.py
.venv/Scripts/python.exe scripts/second_stage_update/franchise_cluster_sensitivity.py
```

Run these from the extracted bundle's directory initially; change the clone name if it already exists. macOS/Linux use `cp -R` and `.venv/bin/python`. The scripts read existing data and write only `results/second_stage_update/`; they do not modify historical outputs. Calendar-week fixed effects are the most expensive models (approximately 1 GB transient memory). Exact input SHA-256 hashes and Python/package versions are recorded in the outputs. CSV floats may differ at numerical roundoff across BLAS/library versions.

Main: regular-season decisive games in calendar years 2001–2019; attendance in thousands; binary current home win; Saturday/Sunday instrument; home- and away-team-by-season FE, year-month FE and both teams' pregame rest, prior result and signed margin. No current start-hour control in main because its pregame status is unverified. Sensitivities use pooled month, ISO calendar-week, recorded hour and MLB doubleheader omission. All four equations use the same observations/controls within each specification. `model_results.csv` gives coefficients in probability units for outcome equations; multiply by 100 for percentage points.

The trusted-library check compares every main 2SLS coefficient and covariance element with `linearmodels`, after matching full absorbed-FE degrees of freedom. The separate MLB franchise sensitivity merges FLO/MIA and MON/WAS for clustering only; it preserves main estimates and core output hashes. AR confidence sets remain conditional on instrument validity and approximate few-cluster inference. Strong relevance is not evidence of exclusion.

## Research report and slide source

The delivered PPTX is the editable presentation source and contains native text, tables and charts. `authoring/work/build_slides.mjs` defines `build(presentation, deckData)`. The deck was created and reviewed in Codex Artifact Session using `@oai/artifact-tool` bundled runtime 26.1117.11355, Arial, 1280×720 logical pixels.

The delivered PPTX also includes three embedded Excel data snapshots for the native charts. Chart caches are rounded to 12 significant digits to preserve literal values across Excel and PowerPoint; full estimator precision stays in the results CSVs. This has no visible effect on the rendered slides. The final package passed first-party import, chart/workbook data agreement, required native-table/chart, font and layout checks. See `review/final_pptx_validation.json`.

To recreate in a new Artifact Session, import the module and JSON from absolute paths in that environment, then run:

```javascript
await artifactSession.run(async ({ presentation }) => {
  build(presentation, deckData);
  await presentation.render({ scale: 2 });
  await presentation.export({ format: 'pptx', fileName: 'research_progress.pptx' });
}, { artifactType: 'presentation' });
```

The completed run returns the directory containing `slide-1.png` through `slide-12.png` and the editable deck. `make_submission_pdf.py RENDER_DIRECTORY OUTPUT.pdf` creates the 12-page submission from those validated 2560×1440 renders at 192 dpi. It needs `reportlab`, `Pillow` and `pypdf`. This avoids font-export differences while the PPTX keeps editable evidence.

The optional report builder expects a workspace structure: its own `work/` directory, a pinned clone at `work/ECON521-Project`, and an `outputs/` directory. `authoring/work/` provides the source JSON, history notes and `assemble_update.py`; place the clone there and overlay the new analysis scripts, then run all three analysis commands above. Install `matplotlib`, `pandas`, `reportlab`, `Pillow` and `pypdf` in an isolated authoring environment and run `python work/assemble_update.py`. It rebuilds the numerical deck JSON, Markdown/PDF report and four scientific figures. The historical extract is cached and no historical model is re-estimated.

## Interpretation

The main IV estimates are +0.276 pp per 1,000 attendees for MLB and −1.089 pp for NBA; NBA is imprecise and sensitive to recorded-hour controls. Both remain preliminary and conditional on independence/exclusion. Weekend can affect rest, travel, game timing and matchup selection directly. NFL remains a calibration reference, with a separate design needed for causal work. See the report for all source discrepancies, seed-paper differences, candidate multiplicity and limitations.
