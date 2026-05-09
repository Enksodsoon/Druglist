# Gold Pipeline Final Summary

Rows are RX eligible only when exact source-backed evidence passes the validator. Incomplete rows are hidden from prescribing output.
- Workbook used: `source_workbooks/drug_list_final_userfriendly_engine_ready_v7.xlsx`
- Products found: 910
- Draft regimen rows found: 987
- Source queries generated: 2441
- Accredited source metadata available: 8
- Evidence fields extracted: 9
- RX NOW ready count: 0
- SWAPS ready count: 0
- Pediatric formula-ready count: 0
- Antibiotic gate-ready count: 0
- Reference-only count: 910
- Hidden/not-ready count: 984
- Conflict count: 3
- Source acquisition queue count: 2441
- Output bundle: `exports/Druglist_Gold_Source_Acquisition_Output_20260509.zip`
- Promotion was not run.
- Next command: `python3 scripts/gold/run_gold_pipeline.py && python3 scripts/gold/09_validate_gold_readiness.py`
