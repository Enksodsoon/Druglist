# Source Review Playbook

This workflow exists because guideline sources are not fully available in the repo yet. Do not mark rules as verified until an actual URL, local source file, or reviewed source registry row is present.

## Export Source Gaps

```bash
python3 scripts/source_workflow.py export-gaps
```

This writes `reports/source_gap_worklist.csv`. Use it to see disease, drug class, and source requirements that still need review.

## Export Source Registry Template

```bash
python3 scripts/source_workflow.py export-template
```

This writes `reports/source_registry_template.csv`. Fill it manually using prioritized sources such as Thai RDU, NLEM, Thai FDA/NDP/NDI, MOPH/DMS, Thai society guidelines, Thai pediatric guidelines, and then international or product-label sources when appropriate.

## Fill Reviewed Source Registry

Create `reports/source_registry_reviewed.csv` with these columns:

`source_id,title,organization,country,year,version,url,file_reference,access_date,source_type,authority_level,thai_source_flag,patient_group,disease_area,drug_group,applies_to,status,notes`

Allowed `status` values:

- `verified`
- `pending_access`
- `missing`
- `manual_review`

`verified` requires `source_id`, `title`, `organization`, and either `url` or `file_reference`. Paywalled, inaccessible, or uncertain sources must stay `pending_access`, not `verified`.

## Import Reviewed Sources

```bash
python3 scripts/source_workflow.py import-sources reports/source_registry_reviewed.csv
```

The import stores reviewed sources in `data/sources/reviewed_source_registry.json` and merges them into the generated source registry. No source IDs or URLs are invented by the script.

## Fill Reviewed Source Gaps

Create `reports/source_gap_reviewed.csv` with these columns:

`gap_id,disease_key,generic_name,drug_class,missing_item,source_ids,resolution_status,reviewer_note`

Allowed `resolution_status` values:

- `linked`
- `unresolved`
- `pending_access`
- `not_applicable`
- `manual_review`

Use `linked` only when the referenced `source_ids` exist in the reviewed source registry. Unresolved rows are preserved and remain manual-review gated.

## Apply Source Links

```bash
python3 scripts/source_workflow.py apply-links reports/source_gap_reviewed.csv
```

Then rerun:

```bash
python3 scripts/build_all.py
python3 scripts/validate_engine.py
pytest -q
```

## Summarize Workflow State

```bash
python3 scripts/source_workflow.py summary
```

This writes `reports/source_workflow_summary.md`.

## Safety Rules

- Never fabricate guideline references.
- Never infer a dose, duration, indication, contraindication, caution, side effect, or pediatric rule from product existence alone.
- Original workbook Thai sig text is label-reference only.
- Keep missing or uncertain evidence as `manual_review`.
