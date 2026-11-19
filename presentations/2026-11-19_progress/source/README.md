# Editable presentation source

The parent directory contains the reviewed 12-slide PDF and editable PPTX. The PPTX has native tables and charts, with embedded Excel chart data snapshots.

`build_slides.mjs` exports `build(presentation, deckData)` for Codex Artifact Session or `@oai/artifact-tool`. `deck_data.json` contains the verified exhibit values. Call the builder inside an Artifact Session callback, render at scale 2, and export PPTX. `make_submission_pdf.py RENDER_DIRECTORY OUTPUT.pdf` creates the 12-page PDF from the resulting `slide-1.png` through `slide-12.png` renders. It requires reportlab, Pillow and pypdf.

Full estimation precision is in `results/second_stage_update/model_results.csv`. Chart caches use 12 significant digits for portable embedded Excel data. The analysis base is main@51c94a98731180e5be3415892c6846a0590f0250; this is the input snapshot, not the later publication commit.
