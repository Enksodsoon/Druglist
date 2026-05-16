# Codex Update Prompt

You are updating the Druglist repo using extracted evidence outputs.

Inputs:

- `reports/evidence_manifest.jsonl`
- `reports/extracted_evidence.jsonl`
- current workbook/runtime files

Tasks:

1. Validate every evidence claim against local source IDs.
2. Update regimen rows only when source coverage is sufficient.
3. Update safety fields from label evidence.
4. Keep blocked rows blocked when evidence is missing or conflicting.
5. Add/refresh validation reports.
6. Run the existing test/build/verify commands.
7. Create a PR summary with exact counts.

Gold-ready criteria:

- adult dose verified,
- disease indication verified,
- duration verified where applicable,
- contraindications/warnings/interactions/side effects source-backed,
- pediatric formula ready if pediatric row,
- antibiotic gate verified if antibiotic row,
- source ID and local file path recorded.

Do not modify app logic to bypass evidence gates.
