# Druglist Evidence Skills

## Skill 1 — Build source queue

Input: `druglist_all_download_links_2026-05-13.xlsx`

Output:

- `reports/source_download_queue.csv`
- `reports/manual_download_todo.csv`

Method:

- prioritize bulk label/guideline sources,
- deduplicate URLs,
- group disease rows by disease bundle,
- group products by generic composition when possible.

## Skill 2 — Download safe HTTP sources

Input: `reports/source_download_queue.csv`

Output:

- downloaded files under `imports/accepted_evidence/`
- `reports/source_download_results.csv`

Rules:

- download direct PDFs, XML, ZIP, JSON, CSV, and static HTML pages,
- do not bypass logins/paywalls,
- mark dynamic/search pages as manual review,
- save metadata JSON for every downloaded source.

## Skill 3 — Resolve DailyMed labels

Input: drug/generic/product names.

Output:

- `reports/dailymed_candidates.csv`
- optional downloaded SPL XML labels when confidence is high.

Rules:

- query DailyMed API by drug name,
- record SETID candidates,
- do not assume the first result is correct when multiple ingredient/route/form mismatches exist.

## Skill 4 — Build source manifest

Input: `imports/accepted_evidence/`

Output: `reports/evidence_manifest.jsonl`

Each line must include:

- source_id
- local_path
- sha256
- source_type
- source_url
- downloaded_at
- file_ext
- status

## Skill 5 — Prepare ChatGPT extraction batches

Input:

- link workbook,
- downloaded evidence manifest,
- current workbook rows.

Output:

- `batches/batch_###/task_list.csv`
- `batches/batch_###/prompt.md`

Batch order:

1. common OPD diseases,
2. high-frequency doctor-pick products,
3. antibiotics,
4. pediatrics,
5. remaining products.

## Skill 6 — Codex update package

Input: extracted evidence JSON/CSV.

Output:

- source manifest updates,
- regimen row updates,
- safety row updates,
- validation report,
- PR summary.
