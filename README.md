# Druglist

Druglist is a static Drug Assistant Runtime System for clinic formulary lookup, OPD fast-mode workflows, pediatric review gates, safety guardrails, and source tracking.

## Local Run

The app is static, but the frontend loads generated JSON, so serve the repo root over HTTP:

```bash
python3 -m http.server 8000
```

Open `http://localhost:8000/index.html`.

## Rebuild

Required source workbook:

```text
source_workbooks/Drug list for physician usage added -update 29022024.xlsx
```

Run the full pipeline:

```bash
python3 scripts/build_all.py
```

Individual phases are also available as `scripts/build_product_layer.py`, `scripts/build_guideline_layer.py`, `scripts/build_pediatric_layer.py`, `scripts/build_safety_layer.py`, `scripts/build_runtime_json.py`, and `scripts/build_frontend_seed.py`.

## Validate

```bash
python3 scripts/validate_engine.py
pytest -q
```

If `pytest` is installed in the user Python bin, use:

```bash
PATH="$HOME/Library/Python/3.9/bin:$PATH" pytest -q
```

## Build Dist

Build the frontend-only deployment artifact:

```bash
python3 scripts/build_dist.py
```

Preview it locally:

```bash
python3 -m http.server 8000 --directory dist
```

Open `http://localhost:8000/`.

## Deploy To GitHub Pages

Deploy only `dist/`. Do not deploy the repo root.

This project supports two deployment modes:

- If source workbooks are committed and available in CI, GitHub Actions can run `build_all`, `validate_engine`, and `build_dist`.
- If source workbooks are local-only, build locally, commit `dist/`, and let GitHub Actions validate/deploy the existing artifact.

In GitHub, configure:

```text
Settings -> Pages -> Source: GitHub Actions
```

Expected URL:

```text
https://enksodsoon.github.io/Druglist/
```

## Safety Limitations

Druglist is a prescribing assistant, not an autonomous prescriber. This build does not fabricate clinical doses, pediatric doses, max doses, durations, indications, contraindications, cautions, side effects, prices, or guideline references.

Unsupported data remains blank or marked `manual_review`. Pediatric dosing is allowed only after verified source-linked review. Antibiotics require disease criteria and source-linked rules. Original workbook Thai sig text is label reference only, not guideline authority.

## Manual Review

Start with `data/meta/manual_review_queue.json`, `data/guidelines/source_gap_list.json`, and `reports/validation_report.md`. Add exact source documents/URLs, extract page or section evidence, then promote rules from inactive/manual-review to active only after review.

Workflow commands:

```bash
python3 scripts/source_workflow.py export-gaps
python3 scripts/source_workflow.py export-template
python3 scripts/peds_workflow.py export-review
python3 scripts/antibiotic_workflow.py export-review
python3 scripts/test_opd_cases.py
```
