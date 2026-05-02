# Integration Plan

## Runtime Loading

`index.html` loads `data/core/app_seed_runtime.json` with a visible loading state. If HTTP loading fails, the embedded seed remains as a fallback and the boot banner explains the missing generated file.

## Data Flow

1. Product workbook builds `drug_master_rebuilt.json`.
2. Source framework builds guideline maps and gaps.
3. Pediatric builder parses concentrations and blocks unsupported auto-dose.
4. Safety builder emits validation/RDU/antibiotic/red-flag catalogs.
5. Runtime builder creates OPD indexes.
6. Frontend seed builder composes app-compatible runtime data.

## Next Integration Work

- Attach exact guideline source files or URLs under `source_guidelines/` or `data/sources/`.
- Add extraction fields with source ID, version/date, page/section, quote summary, and reviewer.
- Promote only reviewed rules into active runtime use.
- Expand frontend panels to show source details on disease and regimen records, not just drug detail records.
