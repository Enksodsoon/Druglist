# Current Repo Mapping

- Current active workbook/import seed: `source_workbooks/drug_list_final_userfriendly_engine_ready_v7.xlsx` if present; legacy engine also references `source_workbooks/Drug list for physician usage added -update 29022024.xlsx`.
- Product/runtime data: `data/core/drug_master_rebuilt.json`, `data/core/fast_regimen_master.json`, `data/core/app_seed_runtime.json`.
- Frontend entrypoint: `index.html`; deploy artifact: `dist/`.
- Build scripts: `scripts/build_all.py`, `scripts/build_runtime_json.py`, `scripts/build_frontend_seed.py`, `scripts/build_dist.py`.
- Validation scripts: `scripts/validate_engine.py`, `scripts/check_runtime_artifacts.py`, `scripts/validate_source_refreshed_workbook.py`.
- Existing source/evidence logic: `data/evidence/`, `data/source_refresh/`, `scripts/source_acquisition_*`, `scripts/exact_claim_extractor.py`.
- RX NOW/SWAPS currently render from runtime complaint/regimen lines in `data/core/app_seed_runtime.json` and frontend builder code in `index.html`.
- Gold overlay connects through `data/gold/rx_eligibility_map.json` and optional copied `dist/gold/*.json`; current production runtime is not overwritten.
- Must not overwrite: `source_workbooks/`, raw workbooks, `data/core/app_seed_runtime.json`, and generated production runtime unless explicit promotion is requested.
- Products found in export: 910
- Draft regimen rows found in export: 987
- Pediatric rows found in export: 93
- Antibiotic rows found in export: 192
- Test/build commands found: `make verify`, `python3 -m pytest -q`, `python3 scripts/validate_engine.py`, `python3 scripts/build_dist.py`.
- Repo-specific risks: embedded seed in `index.html` is large; source coverage is still low; accepted claims may conflict with workbook rows; pediatric/antibiotic gates must remain conservative.
