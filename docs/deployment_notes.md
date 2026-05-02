# Deployment Notes

The deployable artifact is `dist/`. It is intentionally smaller than the working repo and contains only frontend-safe files.

## Local Preview

From the repo root:

```bash
python3 -m http.server 8000
```

Open:

```text
http://127.0.0.1:8000/index.html
```

To preview the deploy artifact after building:

```bash
python3 -m http.server 8000 --directory dist
```

Open:

```text
http://127.0.0.1:8000/
```

## Build Dist

Run:

```bash
python3 scripts/build_all.py
python3 scripts/validate_engine.py
python3 scripts/build_dist.py
```

`dist/` includes:

- `index.html`
- `data/core/app_seed_runtime.json`
- `build_info.json`

`dist/` excludes:

- `source_workbooks/`
- `source_guidelines/`
- raw Excel files
- internal CSV review worklists
- SQLite/database files
- `reports/`
- `scripts/`
- `tests/`
- private notes and local virtual environments

## Two Deployment Modes

Mode A: if source workbooks are committed and available in CI, GitHub Actions runs `build_all`, `validate_engine`, and `build_dist`.

Mode B: if source workbooks remain local-only, build locally, commit `dist/`, and let GitHub Actions validate and deploy the existing artifact.

## GitHub Pages Setup

In GitHub, open:

```text
Settings -> Pages -> Source: GitHub Actions
```

Expected URL:

```text
https://enksodsoon.github.io/Druglist/
```

## Privacy Warning

Everything inside `dist/` is visible to anyone with access to the deployed link. Do not place source workbooks, raw review worklists, private notes, scripts, tests, or databases in `dist/`.
