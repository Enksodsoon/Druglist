# Current Main Health Check

Generated: 2026-05-03

Branch: `main`

## Result

Current `main` is healthy for the restored Druglist app entry, runtime loader, validation workflow, and deployable `dist/` output.

## Checks Run

- `python3 scripts/build_all.py` - passed
- `python3 scripts/validate_engine.py` - passed
- `python3 scripts/build_dist.py` - passed
- `python3 -m pytest -q` - passed, 38 tests
- `python3 scripts/ui_smoke_test.py` - passed in Chromium

## Critical File Verification

- `index.html` exists and is non-empty: 1,699,374 bytes
- `dist/index.html` exists and is non-empty: 1,699,374 bytes
- `data/core/app_seed_runtime.json` is valid JSON with 910 products
- `dist/data/core/app_seed_runtime.json` is valid JSON with 910 products
- `dist/` excludes source workbooks, raw Excel files, SQLite files, scripts, tests, and report CSV worklists

## Expected Warning

- `source_coverage_zero_pending_manual_source_extraction`

This warning is expected because guideline/source extraction is pending. It is not a build failure and must not be resolved by fabricating sources.
