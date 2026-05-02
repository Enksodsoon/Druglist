# Antibiotic Stewardship Workflow

This workflow keeps antibiotics disease-gated, source-gated, and reviewable. It does not make antibiotic prescribing decisions by itself.

## Export Review Rows

Run:

```bash
python3 scripts/antibiotic_workflow.py export-review
```

This writes `reports/antibiotic_review_worklist.csv` with:

- no-routine-antibiotic framework rows for viral URI, acute bronchitis, simple diarrhea, allergic rhinitis, dry eye, and allergic conjunctivitis
- local antibiotic product rows that require disease-specific review before FAST MODE use
- beta-lactam review markers for products that need penicillin-allergy handling

## Manual Review

For each antibiotic rule, a reviewer must confirm the disease key, bacterial criteria, no-antibiotic criteria, first-line or alternative status, allergy alternative notes, dose rule links, duration, red flags, referral criteria, and source IDs.

Use Thai RDU, NLEM, MOPH, Thai society guidelines, or other approved local sources when available. If a source is inaccessible or not yet reviewed, use `pending_source`, not `verified`.

## Import Reviewed Rules

Create `reports/antibiotic_reviewed.csv` with the exported columns, then run:

```bash
python3 scripts/antibiotic_workflow.py import-reviewed reports/antibiotic_reviewed.csv
```

Allowed `reviewer_status` values are:

- `verified`
- `pending_source`
- `local_rule_only`
- `do_not_use`
- `manual_review`

`verified` requires `source_ids`, `disease_key`, `generic_name`, `bacterial_criteria`, `duration`, and either `adult_dose_rule_id` or `peds_dose_rule_id`. Source IDs must already exist in the source registry workflow.

## Safety Rules

- Viral URI, acute bronchitis without criteria, simple diarrhea, allergic rhinitis, dry eye, and allergic conjunctivitis must not routinely receive antibiotics.
- Antibiotics in RX NOW require a bacterial disease row or criteria-dependent source-linked rule.
- Antibiotics in SWAPS must remain criteria-dependent until verified.
- Pediatric antibiotic rules require pediatric source and dose rule review.
- Do not fabricate indications, doses, durations, criteria, or guideline references.

After import, rerun:

```bash
python3 scripts/build_all.py
python3 scripts/validate_engine.py
pytest -q
```
