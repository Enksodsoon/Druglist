# Release Checklist

## Before Release

- `python3 scripts/build_all.py` passes.
- `python3 scripts/validate_engine.py` passes.
- `pytest -q` passes.
- JavaScript syntax check passes if available.
- Live preview smoke test passes if available.
- `index.html` loads `data/core/app_seed_runtime.json` over HTTP.
- Required tabs are visible: main, peds, catalog, compare, validation, inventory, admin, rules.
- Admin panel shows build version, source coverage, and manual-review count.
- Drug detail drawer shows source status and manual-review status.
- `python3 scripts/source_workflow.py export-gaps` works.
- `python3 scripts/peds_workflow.py export-review` works.
- `python3 scripts/antibiotic_workflow.py export-review` works.
- `python3 scripts/test_opd_cases.py` works.
- `python3 scripts/build_dist.py` passes.

## Data Safety

- No unsupported clinical data was added.
- Pediatric auto-dose remains disabled unless all source requirements are satisfied.
- Antibiotic rules require indication/duration/source before clinical activation.
- Source coverage warnings are documented for release notes.
- No source-unverified row is silently marked ready.
- Original workbook Thai sig remains label reference only.

## Deploy

Deploy only `dist/`.

Before push, verify:

- `dist/index.html` exists and is non-empty.
- `dist/data/core/app_seed_runtime.json` exists.
- `dist/` contains no `source_workbooks/`.
- `dist/` contains no `.xlsx`, `.xls`, `.sqlite`, `.db`, or review `.csv` files.
- `dist/` contains no `reports/`, `scripts/`, or `tests/`.

GitHub Pages source must be set to GitHub Actions.
