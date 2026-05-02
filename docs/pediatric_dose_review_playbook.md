# Pediatric Dose Review Playbook

Pediatric dosing is source-gated. Product label text and the original workbook Thai sig are label references only; they are not verified pediatric dosing authority.

## Export Review Worklist

```bash
python3 scripts/peds_workflow.py export-review
```

This writes `reports/peds_dose_review_worklist.csv` from the current pediatric candidate queue.

## Fill Reviewed Pediatric Rows

Create `reports/peds_dose_reviewed.csv` with these columns:

`peds_dose_rule_id,generic_name,disease_key,indication_text,age_min_value,age_min_unit,age_max_value,age_max_unit,weight_min_kg,weight_max_kg,dose_basis,dose_mg_per_kg_per_dose,dose_mg_per_kg_per_day,fixed_dose,fixed_dose_unit,frequency,max_per_dose,max_per_day,duration,route,source_ids,reviewer_status,reviewer_note`

Allowed `reviewer_status` values:

- `verified`
- `pending_source`
- `do_not_use`
- `label_reference_only`
- `manual_review`

## Import Reviewed Rows

```bash
python3 scripts/peds_workflow.py import-reviewed reports/peds_dose_reviewed.csv
```

`verified` rows require source IDs plus disease-specific indication, dose basis, frequency, duration, and route. Antibiotic pediatric rows also require disease-specific indication, duration, and source. Cough/cold/decongestant combinations should stay warning-gated until a reviewed age rule is attached.

## After Import

```bash
python3 scripts/build_all.py
python3 scripts/validate_engine.py
pytest -q
```

## Safety Rules

- Do not fabricate pediatric doses, max doses, frequencies, durations, or indications.
- `label_reference_only` is not FAST MODE allowed.
- `pending_source` remains manual-review gated.
- Auto-calculable pediatric rules require source IDs and concentration support.
- Pediatric auto-dose remains disabled unless all source, age/body-weight, concentration, route/form, max-dose, indication, and duration requirements are satisfied.
