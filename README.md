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

## Deploy

Deploy the repo root as a static site. The deploy entry is `index.html`; generated JSON under `data/` must be deployed with it.

## Safety Limitations

This build does not fabricate clinical doses, pediatric doses, indications, contraindications, cautions, side effects, prices, or source claims. Unsupported data remains blank or marked `manual_review`. Pediatric auto-dose is disabled until verified source-linked age/body-weight rules, max doses, concentrations, route/form matches, and indication rules are added.

## Manual Review

Start with `data/meta/manual_review_queue.json`, `data/guidelines/source_gap_list.json`, and `reports/validation_report.md`. Add exact source documents/URLs, extract page or section evidence, then promote rules from inactive/manual-review to active only after review.
