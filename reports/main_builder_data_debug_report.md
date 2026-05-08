# Main Builder Data Debug Report

- Runtime path: `data/core/app_seed_runtime.json`
- Complaint count: 391
- Disease/regimen key count: 133
- Runtime regimen rows: 987
- Complaints linked to regimen rows: 391
- Rows hidden by `fast_mode_allowed=false`: 513
- Fast regimen master rows: 133
- OPD fast index entries: 3
- Clinical audit issues: 253
- Regimen corrections configured: 2

## Readiness

- blocked: 33
- manual_review_required: 480
- usable_with_warning: 474

## Source Status

- pending_manual_review: 513
- source_gap: 474

## Evidence Status

- pending_source_collection: 987

## Samples

- Linked rows sample: CI0001 | allergic rhinitis | FRM0001 | Allergic rhinitis | Zyrtec [Cetirizine dihydrochloride 10 mg.]
- Only blocked/manual rows sample: CI0009 | dry eye | FRM0007 | Symptomatic dry eye syndrome | Vislube [Sodium Hyaluronate 0.18% (Sodium Hyaluronate 1.8 mg.+Sodium Chloride 2.8 mg.+Potassium Chloride 1 mg.+Disodium Hydrogenphosphate 3.2 mg.+Sodium Citrate 0.3 mg.+Magnesium Chloride 0.09 mg.+Calcium Chloride 0.09 mg.)]
- No linked regimen sample: none | 

## Frontend Contract Fields

- complaint: `i`, `c`, `r`
- regimen: `i`, `d`, `m`, `y`, `w`
- row: `i`, `n`, `t`, `o`, `u`, `p`, `clinical_readiness`, `fast_mode_allowed`, `source_status`, `evidence_status`, `blocked_reason`, `missing_requirements`, `next_action`
