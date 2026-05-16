# Evidence Extraction Prompt

You are verifying Druglist app evidence from downloaded guideline/label files.

Use only the provided files and manifest. Do not invent missing information.

For each row in `task_list.csv`, extract:

```json
{
  "task_id": "",
  "row_type": "disease|drug|product",
  "disease_key": "",
  "drug_or_product": "",
  "indication": "",
  "adult_dose": "",
  "pediatric_dose": "",
  "pediatric_formula_ready": false,
  "max_dose": "",
  "route": "",
  "frequency": "",
  "duration": "",
  "regimen_role": "first_line|second_line|add_on|avoid|not_applicable",
  "contraindications": [],
  "warnings": [],
  "interactions": [],
  "side_effects_common": [],
  "side_effects_serious": [],
  "pregnancy_lactation": "",
  "renal_hepatic": "",
  "antibiotic_gate": "",
  "red_flags": [],
  "source_ids": [],
  "source_sections": [],
  "short_quote_or_paraphrase": "",
  "conflicts": [],
  "verification_status": "gold_ready|usable_with_warning_source_partial|manual_review|blocked_conflict|blocked_no_source",
  "reviewer_note": ""
}
```

Special rules:

- Pediatric dose must be source-backed. If not exact enough, set `pediatric_formula_ready=false`.
- Antibiotic rows need disease guideline + label evidence.
- If disease guideline and product label disagree, flag conflict.
- If only generic label is found for a Thai brand, mark `usable_with_warning_source_partial` unless brand-specific safety is essential.


Use `task_list.csv` for this batch.
