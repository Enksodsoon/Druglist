# Workbook Source Refresh Diff

- Added source/citation/readiness refresh columns to regimen, pediatric, and antibiotic sheets.
- Source acquisition claims are applied idempotently by regimen/product/disease key.
- Rows are not promoted when source-backed claims conflict with the workbook row.
- Unsupported rows remain source_gap, manual_review_required, blocked, or usable_with_warning.
