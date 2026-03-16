# Next Update Analysis (based on uploaded data, docs, and source workbook)

## Scope reviewed
- Runtime app: `index.html` (current all-in-one light build).
- Core data bundle: `data/core/druglist_master_data.json`.
- Pediatric support data:
  - `data/pediatric/pediatric_target_dose_library.json`
  - `data/pediatric/pediatric_age_gate_library.json`
  - `data/pediatric/pediatric_product_age_indication_library_review.json`
- Workbook source: `source_workbooks/drug_list_final_userfriendly_engine_ready_v7.xlsx`.

## What the current app can already do
The current UI and logic supports:
- Main Builder (complaint -> regimen -> output)
- Pediatric Builder (age/weight + pediatric-target layer)
- Catalog
- Cheaper-in-class comparison
- Validation panel
- Inventory panel
- Admin panel
- Rule editor logic and section present in page

## Data readiness summary (high-level)
From the current dataset and embedded app seed:
- **910** total drug rows, **391** complaints, **133** regimens.
- Complaint-to-regimen coverage is complete at disease-key level (no complaints missing regimens).
- Pediatric layer has full product alignment by BDS key across the 3 pediatric files.
- Pediatric support depth is still limited:
  - `no_pediatric_target_found`: **765 / 910** (~84.1%)
  - `calculator_ready_manual_target_needed`: **91 / 910** (~10.0%)
  - `reference_exists_but_not_parseable`: **34 / 910** (~3.7%)
  - `auto_mapped_from_same_generic_reference`: **20 / 910** (~2.2%)
- Price coverage in app seed is sparse: **26 / 910** rows have numeric `pr` (pack price).

## Key product implications

### 1) Pediatric calculator potential is high but blocked by reference completeness
You already have a strong scaffold (target library + age-gate + review table), and all 910 products are linked across files. The next gain comes from converting the large `no_pediatric_target_found` block into either:
- auto-calculable rules, or
- manual-target-ready rules with clear guardrails.

### 2) Cost optimization features are currently underpowered by data sparsity
The app includes a cheaper-in-class and class comparison workflow, but only a small fraction of rows have price. Increasing price coverage from 26 rows to even 40-60% would materially improve recommendation confidence.

### 3) Rule management is partially hidden in navigation
`index.html` contains `section-rules` and `renderRules()` paths, but there are **two `tabs()` function definitions**, and the latter omits the `rules` tab from visible navigation. This makes the rule editor hard/impossible to access from normal UI flow.

### 4) Workbook structure is rich enough for an import/update pipeline
The source workbook has many domain sheets (e.g., defaults, top 50, doctor picks, category-specific option sheets, pediatric shortcuts). This is enough to justify a predictable delta import process for monthly updates instead of manual embedding.

## Recommended next-update roadmap

### Priority A (immediate, high impact)
1. **Restore Rule Editor tab visibility**
   - Remove/merge duplicate `tabs()` definitions and keep the variant with `rules` tab.
   - Add a quick regression check: tab renders + section switch + rule pack export.

2. **Pediatric target expansion sprint (Phase 1)**
   - Focus first on high-use classes and top default regimens.
   - Convert “manual target needed” items into fully specified dose targets where possible.
   - Add parser rules for common concentration text patterns to shrink “not parseable”.

3. **Price ingestion baseline**
   - Add importer step from `Price_Estimates_Online` sheet into seed field `pr`.
   - Track `price_updated_at` metadata and surface stale-price warnings in compare panel.

### Priority B (next cycle)
4. **Clinical guardrail hardening in Pediatric Builder**
   - Show hard stop/warning when product form is age-gated (solid oral, lozenge, spray).
   - Make pediatric output include explicit rationale text from `age_gate_reason` and target status.

5. **Update pipeline from workbook -> JSON seed**
   - Create one script to regenerate embedded seed + pediatric JSONs from workbook.
   - Emit validation report (row counts, missing fields, parse failures, duplicate checks).

6. **Outcome-focused validation dashboard**
   - Add KPI counters in Admin/Validation:
     - % drugs with price
     - % drugs with pediatric target
     - % complaints with default regimen
     - # parse failures by reason

### Priority C (quality & scalability)
7. **Data contract/versioning**
   - Add `schema_version` and `build_version` across all generated JSONs.
   - Add compatibility checks on app boot to fail fast when incompatible data is loaded.

8. **Automated consistency tests**
   - Assert 1:1 BDS alignment across pediatric files.
   - Assert complaint->regimen referential integrity.
   - Assert no duplicate drug IDs and no broken category/generic references.

## Suggested success metrics for the next release
- Rule Editor navigable from tabs (binary pass/fail).
- Pediatric target coverage improved from **16% -> >=35%** in first pass.
- Numeric price coverage improved from **26 rows -> >=300 rows**.
- Zero integrity regressions in automated checks.

## Practical implementation sequence (2-week sprint option)
- **Day 1-2**: fix `tabs()` duplication + add smoke checks.
- **Day 3-7**: pediatric reference curation + parser enhancements.
- **Day 8-10**: price import mapping + staleness metadata.
- **Day 11-12**: workbook-to-json build script and validation report.
- **Day 13-14**: QA pass, release candidate export, clinic UAT notes.

