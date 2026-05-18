# Gold OPD Engine v5 Import Pack

This folder is the non-destructive handoff area for **Gold OPD Engine v5 — Production Candidate**.

## Purpose

Integrate the v5 runtime pack into the Druglist app without replacing the current legacy runtime until validation passes.

```text
short OPD input -> OPD_Fast_Index_v5 -> disease_key -> Final_RX_NOW_v5 -> Final_SWAPS_Tiered_v5 -> gates -> copyable OPD output
```

## Required v5 CSV files

Place these files in this folder before running the importer:

- `opd_fast_index_v5.csv`
- `drug_short_lookup_v5.csv`
- `final_rx_now_v5.csv`
- `final_swaps_tiered_v5.csv`
- `peds_runtime_rules_v5.csv`
- `antibiotic_runtime_gates_v5.csv`
- `safety_runtime_gates_v5.csv`
- `clinical_test_cases_v5.csv`
- `clinical_expected_outputs_v5.csv`
- `clinical_gap_report_v5.csv`
- `runtime_patch_v5.csv`
- `app_integration_map_v5.csv`
- `validation_v5_report.csv`
- `change_log_v5.csv`

## Integration rules

1. Use `opd_fast_index_v5.csv` first for complaint matching.
2. Do not scan the full 910-product lookup on each query.
3. Use `final_rx_now_v5.csv` for default orders.
4. Use `final_swaps_tiered_v5.csv` for tiered alternatives.
5. Use `drug_short_lookup_v5.csv` only to fill product/BDS/pack/price fields.
6. Antibiotics require a matching row in `antibiotic_runtime_gates_v5.csv`.
7. Pediatric output requires a matching row in `peds_runtime_rules_v5.csv`.
8. Red flags and restricted products must pass `safety_runtime_gates_v5.csv`.
9. Reference-only products must stay searchable but hidden from automatic FAST MODE prescribing.
10. Keep the legacy app runtime active until v5 tests pass.

## Suggested local workflow

```bash
python3 scripts/import_gold_opd_v5.py
python3 scripts/validate_gold_opd_v5_import.py
python3 scripts/build_all.py
python3 scripts/validate_engine.py
pytest -q
python3 scripts/build_dist.py
```

## Status label

```text
Gold OPD Engine v5 = production-candidate, not final clinical validation.
```

This pack is intended for app testing and workflow integration. It does not claim every individual brand is independently label-verified. Pediatric and antibiotic rows remain gate-controlled.
