# Known Limitations

- Druglist is a prescribing assistant, not an autonomous prescriber.
- Missing sources remain `manual_review`.
- Pediatric dosing is available only when verified by source-linked review.
- Antibiotics require disease criteria and source-linked rules.
- Prices may be missing, imputed, stale, or unavailable.
- Original workbook Thai sig text is label reference only, not guideline authority.
- Online `dist/` data is visible to people with access to the deployed link.
- Source coverage is currently expected to remain `0.0` until reviewed guideline PDFs, files, or URLs are imported.
- Local product availability and doctor-pick priority affect ranking only; they do not override guideline, RDU, pediatric, allergy, red-flag, or antibiotic stewardship gates.
