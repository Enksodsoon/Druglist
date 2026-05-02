# Data Contract

## Core

- `data/core/drug_master_rebuilt.json`: source-grounded product records from the primary workbook.
- `data/core/drug_short_lookup.json`: compact product lookup by BDS/medicine code.
- `data/core/generic_cluster_map.json`: generic-key clusters for product comparison and search.
- `data/core/complaint_index.json`: complaint aliases linked to runtime disease IDs.
- `data/core/disease_master.json`: OPD disease/runtime condition registry.
- `data/core/fast_regimen_master.json`: legacy regimen rows preserved as `legacy_unverified`.
- `data/core/opd_fast_index.json`: runtime search index and layer link map.
- `data/core/app_seed_runtime.json`: frontend-compatible generated seed loaded by `index.html`.

## Guideline

Guideline files under `data/guidelines/` are source frameworks. When no exact guideline source is attached, records use `pending_access`, `missing_verified_source`, and `manual_review: true`.

## Pediatric

Pediatric files under `data/pediatric/` separate concentration parsing from dose automation. `auto_dose_enabled` must remain false unless source IDs, age/body-weight rule, dose basis, max dose, concentration, route/form match, and indication/duration requirements are present.

## Safety

Safety files under `data/safety/` contain validation, RDU, antibiotic stewardship, and red-flag rules. Unsupported clinical assertions remain source-gated and manual-review marked.

## Meta

- `data/meta/manual_review_queue.json`: product-level review queue.
- `data/meta/build_manifest.json`: stable build manifest and output list.
