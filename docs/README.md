# Codex Project Export

This bundle contains the files needed to continue the druglist tool project in Codex.

## Recommended starting point
Use:

- `apps/current/druglist_complete_tool_v3_1_fullfeatures_fix5_drugdetail_delegated.html`

That is the latest all-in-one build with:
- Main Builder
- Pediatric Builder
- Catalog
- Cheaper-in-class
- Validation
- Inventory
- Admin
- Smart add-ons
- Duplicate-role cleaner
- Favorites / Clinic Profile
- Export bundle
- Rule Editor

## Known issue
The latest all-in-one builds still have an unresolved **drug detail freeze** bug.
If you want to debug that path in Codex, compare against these fallback/reference builds:

- `apps/reference/druglist_complete_tool_v3_1_light_rules_editor.html`
- `apps/reference/druglist_complete_tool_v3_1_light_exportbundle.html`
- `apps/reference/druglist_complete_tool_v3_1_light_smartaddons_favorites_profile.html`
- `apps/reference/druglist_master_explorer_merge_builder_v4.html`
- `apps/reference/druglist_pediatric_builder_agefilter_v2_verifiedfirst.html`

## Core data files
Main app data:
- `data/core/druglist_master_data.json`
- `data/core/druglist_master_data_pretty.json`
- `data/core/druglist_normalized_full.json`
- `data/core/druglist_normalized_pretty.json`

Pediatric libraries:
- `data/pediatric/pediatric_target_dose_library.json`
- `data/pediatric/pediatric_age_gate_library.json`
- `data/pediatric/pediatric_product_age_indication_library_review.json`
- plus CSV/pretty/summary companions in the same folder

## Original source files
- `source_workbooks/drug_list_final_userfriendly_engine_ready_v7.xlsx`
- `source_workbooks/drug_list_final_userfriendly.xlsx`
- `source_workbooks/Drug-Table-Notion.txt`

## Suggested Codex workflow
1. Start from the latest all-in-one HTML in `apps/current`.
2. Keep `druglist_master_data.json` as the main embedded data source.
3. Keep pediatric logic driven by:
   - target-dose library
   - age-gate library
   - product age review library
4. Fix the drug detail path before adding more features.
5. If needed, diff against the reference builds to recover any behavior that regressed.

## Manifest
See `docs/manifest.json` for a machine-readable file list.
