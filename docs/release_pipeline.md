# Release Pipeline (Automated)

## Goal
Run one command to build data from workbook, validate integrity, inject app seed, and generate a release report.

## Command
```bash
python scripts/release_prepare.py
```

## What it does
1. `python scripts/build_from_workbook.py`
2. `python scripts/validate_data.py`
3. `python scripts/inject_seed.py`
4. Emits `build/release_prepare_report.json`

## Outputs
- `build/app_seed.json`
- `build/build_report.json`
- `build/validation_report.json`
- `build/release_prepare_report.json`

## Notes
- `index.html` embedded seed is updated from `build/app_seed.json`.
- If any step fails, pipeline exits non-zero and writes failure context to report.
