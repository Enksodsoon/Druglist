# Correction Overlay Policy

Correction overlays protect runtime behavior without editing raw workbook-derived rows.

- Corrections may block, downgrade, move, or mark catalog-only rows.
- Corrections may add source gaps or required review reasons.
- Corrections must not create verified doses, durations, indications, contraindications, cautions, BDS, prices, or guideline references.
- `correct_if_source_verified` may only apply when accepted source IDs and traceable extracted evidence exist.
- Product catalog availability is preserved unless the product metadata itself is unsafe or ambiguous.
- Regimen use can be blocked even when product catalog display remains available.
