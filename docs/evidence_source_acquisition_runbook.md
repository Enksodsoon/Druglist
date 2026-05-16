# Evidence Source Acquisition Runbook

This workflow downloads and caches official/public evidence source files only. It does not verify regimens, match DailyMed candidates, or mark any row Gold-ready.

## Commands

```bash
cd /Users/a12/Documents/GitHub/Druglist
python3 -m venv .venv-evidence
source .venv-evidence/bin/activate
python -m pip install -r tools/evidence_automation/requirements.txt
python scripts/run_evidence_source_pipeline.py --links-xlsx druglist_all_download_links_2026-05-13.xlsx
```

For a dry queue/batch/manifest pass without HTTP downloads:

```bash
python scripts/run_evidence_source_pipeline.py --skip-download
```

## Outputs

- `reports/evidence_acquisition/source_download_queue.csv`: deduplicated URL queue from the link workbook.
- `reports/evidence_acquisition/source_download_results.csv`: HTTP download result per queued URL.
- `reports/evidence_acquisition/manual_download_todo.csv`: rows that require manual review or browser/login-safe handling.
- `reports/evidence_acquisition/dailymed_candidates.csv`: DailyMed SPL candidates for ranks 1-3.
- `reports/evidence_acquisition/evidence_manifest.jsonl`: cached file manifest with SHA256 and metadata.
- `batches/evidence_extraction/batch_001/task_list.csv`: first extraction task batch.
- `batches/evidence_extraction/batch_001/prompt.md`: extraction prompt for the batch.

Compatibility aliases are also written under `reports/` for the queue, manual todo, DailyMed candidates, and manifest.

## Manual Todo

Open `reports/evidence_acquisition/manual_download_todo.csv` for sources that were not automatically downloaded. Typical reasons include MIMS, Thai FDA dynamic pages, search result URLs, access-controlled pages, or large/unstable endpoints.

Do not bypass login, paywalls, CAPTCHA, or other access controls. If a source requires interactive/manual handling, save any permitted file under `imports/accepted_evidence/` and include source URL, local path, SHA256, download timestamp, HTTP/content notes, and source/task identifiers.

## Automated Scope

Automated:

- Reads all target sheets in `druglist_all_download_links_2026-05-13.xlsx`.
- Deduplicates by normalized URL while preserving linked workbook rows.
- Downloads public HTTP files and HTML pages into `imports/accepted_evidence/`.
- Writes `.meta.json` next to every downloaded file.
- Resolves DailyMed queries and caches SPL XML candidates for ranks 1-3.
- Builds a manifest and extraction batch scaffolding.

Still manual:

- Verifying that a downloaded source supports a regimen.
- Matching DailyMed candidates to exact local drug/product rows.
- Handling dynamic websites, login-required sources, paywalled sources, CAPTCHA, or unstable bulk endpoints.
- Promoting any row to Gold-ready.

## Next Step

Use the generated extraction batches to extract evidence claims from cached sources. Keep extracted claims separate from source acquisition results until manual review and regimen verification are complete.
