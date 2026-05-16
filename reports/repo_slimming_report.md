# Repo Slimming Report

## Summary

- Removed tracked raw accepted-evidence cache files from `imports/accepted_evidence/`.
- Removed duplicated evidence acquisition reports from `reports/` and `reports/evidence_acquisition/`.
- Removed oversized derived Gold sweep JSON files that are regenerated outputs, not runtime inputs.
- Added ignore rules for local source caches, generated source queues, evidence bundles, UI smoke artifacts, and temporary automation packs.
- Added tests to prevent raw accepted-evidence caches and duplicate large evidence reports from being committed again.

## Size Impact

- Tracked files: 8,835 -> 504
- Tracked bytes: ~228 MB -> ~69 MB
- Local working directory after cleanup: ~130 MB

## Kept

- Runtime data under `data/core/` and `dist/data/core/`
- Gold overlay outputs under `data/gold/` and `dist/gold/`
- Reviewable Gold reports that tests and validation use
- App code, tests, build scripts, and clinical status outputs

## Removed From Git

- `imports/accepted_evidence/**` raw/cache payloads, except `README.md` and `.gitignore`
- `reports/evidence_acquisition/**`
- `reports/source_download_results.csv`
- `reports/source_download_queue.csv`
- `reports/evidence_manifest.jsonl`
- `reports/manual_download_todo.csv`
- `reports/dailymed_candidates.csv`
- `data/gold/long_accredited_source_acquisition_queue.json`
- `data/gold/accredited_source_sweep_evidence.json`
- `data/gold/all_drug_accredited_sweep.json`
- Older generated Gold sweep zip bundle

## Verification

- `python3 scripts/build_dist.py`
- `python3 scripts/check_runtime_artifacts.py`
- `python3 -m pytest -q`
- `python3 scripts/ui_smoke_test.py`
- `make verify`

`make verify` retained the expected warning:
`source_coverage_zero_pending_manual_source_extraction`.
