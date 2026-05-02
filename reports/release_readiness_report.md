# Release Readiness Report

Generated: 2026-05-02T06:45:17Z

## Status

The static app is prepared for GitHub Pages deployment through a clean `dist/` artifact.

## Completed

- Source-gap export/import workflow is available.
- Pediatric dose review workflow is available.
- Antibiotic stewardship workflow is available.
- Runtime rows include source-gated readiness fields.
- OPD FAST MODE regression harness covers 40 common cases and red-flag inputs.
- Safe `dist/` builder excludes source workbooks, review CSVs, reports, scripts, tests, and database files.
- GitHub Pages workflow is present at `.github/workflows/deploy-pages.yml`.

## Final Commands

```bash
python3 scripts/build_all.py
python3 scripts/validate_engine.py
python3 scripts/build_dist.py
pytest -q
```

## Expected Warning

`source_coverage_zero_pending_manual_source_extraction` is expected because verified guideline source documents or URLs have not been imported yet.

## Deployment

Deploy only `dist/`. Configure GitHub Pages:

```text
Settings -> Pages -> Source: GitHub Actions
```

Expected URL:

```text
https://enksodsoon.github.io/Druglist/
```
