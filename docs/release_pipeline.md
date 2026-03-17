# Release Pipeline (Automated)

## Goal
Run one command to build data from workbook, validate integrity with strict thresholds, inject app seed, and generate release + regression artifacts.

## Command
```bash
python scripts/release_prepare.py
```

## Optional threshold/regression tuning
```bash
python scripts/release_prepare.py \
  --min-price-rate 0.30 \
  --min-peds-rate 0.20 \
  --min-direct-generic-rate 0.04 \
  --min-peds-weighted-rate 0.12 \
  --max-price-regression 0.05 \
  --max-peds-regression 0.03 \
  --max-direct-generic-regression 0.03
```

## What it does
1. `python scripts/build_from_workbook.py`
2. `python scripts/validate_data.py --strict ...` (hard-fail on threshold misses)
3. `python scripts/inject_seed.py`
4. Persists release snapshots and regression trend
5. Emits `build/release_prepare_report.json`

## Outputs
- `build/app_seed.json`
- `build/build_report.json`
- `build/validation_report.json`
- `build/release_prepare_report.json`
- `build/release_history.json`
- `build/release_history.md`

## Notes
- `index.html` embedded seed is updated from `build/app_seed.json`.
- In strict mode, both integrity errors and threshold misses fail the pipeline.
- Regression checks can fail release if key KPIs drop too much versus previous run.
- Recommended for CI so release candidates are blocked when guardrails fail.
