# Manual Review Workflow

## Queues

- Product queue: `data/meta/manual_review_queue.json`.
- Source gaps: `data/guidelines/source_gap_list.json`.
- Pediatric dose output: `data/pediatric/peds_product_dose_output.json`.
- Validation summary: `reports/validation_report.md`.

## Review Steps

1. Pick one queue item and identify the exact missing evidence.
2. Attach source metadata in the appropriate registry or rule file.
3. Extract only supported facts: dose, indication, duration, age/body-weight gate, max dose, route/form constraints, or safety warning.
4. Add reviewer notes and keep unsupported fields blank.
5. Rerun `python3 scripts/build_all.py`.
6. Rerun `python3 scripts/validate_engine.py` and `pytest -q`.

## Promotion Rules

Do not set a pediatric dose to automatic unless source, age/body-weight rule, dose basis, max dose where relevant, concentration, route/form match, and disease-specific indication are all present. Antibiotics also require indication, duration, and source.
