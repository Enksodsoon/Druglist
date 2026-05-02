# Remaining Work Plan

Generated: 2026-05-02

## Current Branch

`feature/full-drug-assistant-rebuild`

## What Already Works

- `python3 scripts/build_all.py` completes successfully.
- `python3 scripts/validate_engine.py` passes.
- `pytest -q` passes.
- The static app loads locally from `index.html` and generated `data/core/app_seed_runtime.json`.
- Admin, Validation, and the drug detail drawer expose manual-review and source-gap state.
- Product layer contains 910 products from the primary workbook.
- Runtime layer contains OPD complaint, disease, and regimen indexes.
- Pediatric auto-dose remains disabled while source-gated review is incomplete.

## Expected Warnings

- `source_coverage_zero_pending_manual_source_extraction` is expected because no reviewed guideline PDFs, URLs, or source registry rows have been linked yet.

## High-Risk Items

- Clinical source extraction is incomplete and must remain manual-review gated.
- Pediatric dose automation must stay blocked until source, age/body-weight, concentration, route/form, max-dose, indication, and duration gates are satisfied.
- Antibiotic rows must remain disease-gated and source/manual-review gated.
- Source workbooks and internal review worklists must not be exposed in deployable `dist/`.
- Existing workbook Thai sig text is label-reference only and is not guideline authority.

## Remaining Work

1. Add a source-gap export/import workflow for human-reviewed guideline source links.
2. Add source-gated OPD runtime readiness fields for FAST MODE rows.
3. Add a pediatric dose review workflow for reviewed pediatric rule imports.
4. Add an antibiotic stewardship review workflow.
5. Add deterministic OPD FAST MODE regression cases.
6. Build a safe `dist/` deployment pipeline for GitHub Pages.
7. Update release readiness docs and known limitations.

## Next Tasks

- Implement `scripts/source_workflow.py` and `docs/source_review_playbook.md`.
- Add tests for source registry import validation and unresolved gap preservation.
- Rebuild, validate, and keep the expected zero-source-coverage warning until real reviewed sources are provided.
