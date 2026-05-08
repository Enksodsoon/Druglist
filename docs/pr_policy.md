# Pull Request Safety Policy

Druglist PRs must preserve the source-gated clinical safety contract. UI changes, data changes, and workflow changes are not merge-ready until the checks below pass.

## Required Checks

Run all of these before merge:

```bash
python3 scripts/build_all.py
python3 scripts/validate_engine.py
python3 scripts/build_dist.py
python3 -m pytest -q
python3 scripts/ui_smoke_test.py
```

The only expected validation warning is:

```text
source_coverage_zero_pending_manual_source_extraction
```

## Required App Entry Checks

- `index.html` must exist and be non-empty.
- `dist/index.html` must exist and be non-empty.
- `data/core/app_seed_runtime.json` must be valid JSON with product rows.
- `dist/data/core/app_seed_runtime.json` must be valid JSON with product rows.
- `dist/` must not include source workbooks, raw Excel files, SQLite files, scripts, tests, report CSV worklists, or private notes.

## Clinical Safety Rules

- Do not fabricate doses, pediatric doses, max doses, durations, indications, prices, BDS, cautions, contraindications, or guideline references.
- Do not mark `source_verified`, `auto_verified`, or equivalent unless a real source URL, source file, or reviewed source registry row exists.
- Pediatric auto-dose must remain blocked unless source, age/body-weight, dose basis, required max dose, concentration, route/form, and indication/duration gates are satisfied.
- Antibiotic RX NOW behavior must require source-backed bacterial disease criteria or remain blocked/manual-review.

## Stale UI PRs

Old UI experiment branches should not be merged after the full rebuild. Recreate specific UI ideas on current `main` with the required checks above.
