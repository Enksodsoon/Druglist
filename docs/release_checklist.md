# Release Checklist

## Before Release

- `python3 scripts/build_all.py` passes.
- `python3 scripts/validate_engine.py` passes.
- `pytest -q` passes.
- `index.html` loads `data/core/app_seed_runtime.json` over HTTP.
- Required tabs are visible: main, peds, catalog, compare, validation, inventory, admin, rules.
- Admin panel shows build version, source coverage, and manual-review count.
- Drug detail drawer shows source status and manual-review status.

## Data Safety

- No unsupported clinical data was added.
- Pediatric auto-dose remains disabled unless all source requirements are satisfied.
- Antibiotic rules require indication/duration/source before clinical activation.
- Source coverage warnings are documented for release notes.

## Deploy

Deploy `index.html`, `data/`, `docs/`, `reports/`, `scripts/`, and tests as appropriate for the static hosting workflow. The app itself requires `index.html` plus generated `data/` JSON files.
