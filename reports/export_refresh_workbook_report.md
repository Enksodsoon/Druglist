# Export Refresh Workbook Report

- Generated at: 2026-05-16T17:28:51.500951+00:00
- Workbook: `exports/Druglist_Data_Refresh_Master.xlsx`
- CSV directory: `exports/refresh_csv/`
- Total products: 910
- Total complaints: 522
- Total disease keys: 186
- Total regimen rows: 1570
- Rows with missing product_id: 251
- Rows with missing disease_key: 0
- Rows with missing source: 1570
- Rows with blocked/manual_review status: 1096
- Duplicate product names: 0
- Duplicate regimen IDs in fast regimen master: 0
- Repeated regimen IDs across complaint aliases: 188

## Tabs

- 1_Product_Master_Export: 910 rows
- 2_Regimen_Master_Export: 1570 rows
- 3_Complaint_Disease_Map: 522 rows
- 4_Top_50_Defaults: 50 rows
- 5_Clinic_Defaults: 564 rows
- 6_Pediatric_Dosing: 93 rows
- 7_Antibiotic_Rows: 295 rows
- 8_Source_Evidence_Queue: 103 rows
- 9_Clinical_QC: 950 rows
- 10_Import_Diff_Template: 1 rows
- 11_OPD_Fast_Index_Template: 217 rows
- 12_Drug_Short_Lookup_Template: 910 rows

## Sample 20 High-Risk Rows

| regimen_id | disease_key | product_id | drug_name | readiness | source | next_action |
|---|---|---|---|---|---|---|
| FRM0001 | allergic_rhinitis_adult | BDS004213 | Zyrtec [Cetirizine dihydrochloride 10 mg.] | usable_with_warning | source_gap | attach accepted source evidence |
| FRM0001 | allergic_rhinitis_adult | BDS002805 | Nasonex 60 doses [Mometasone Furoate Monohydrate (eq. to Mometasone Furoate 50 m | manual_review_required | pending_manual_review | attach accepted source evidence |
| FRM0001 | allergic_rhinitis_adult | BDS003747 | Telfast 180 mg [Fexofenadine HCl 180 mg.] | usable_with_warning | source_gap | attach accepted source evidence |
| FRM0001 | allergic_rhinitis_adult | BDS045630 | Nasotapp [Brompheniramine Maleate 4 mg.+Phenylephrine HCl 10 mg.] | usable_with_warning | source_gap | attach accepted source evidence |
| FRM0001 | allergic_rhinitis_adult | BDS004213 | Zyrtec [Cetirizine dihydrochloride 10 mg.] | usable_with_warning | source_gap | attach accepted source evidence |
| FRM0001 | allergic_rhinitis_adult | BDS002805 | Nasonex 60 doses [Mometasone Furoate Monohydrate (eq. to Mometasone Furoate 50 m | manual_review_required | pending_manual_review | attach accepted source evidence |
| FRM0001 | allergic_rhinitis_adult | BDS003747 | Telfast 180 mg [Fexofenadine HCl 180 mg.] | usable_with_warning | source_gap | attach accepted source evidence |
| FRM0001 | allergic_rhinitis_adult | BDS045630 | Nasotapp [Brompheniramine Maleate 4 mg.+Phenylephrine HCl 10 mg.] | usable_with_warning | source_gap | attach accepted source evidence |
| FRM0002 | uri_wet_cough_adult | BDS003762 | Tylenol 500 mg strip 10s [Paracetamol 500 mg.] | usable_with_warning | source_gap | attach accepted source evidence |
| FRM0002 | uri_wet_cough_adult | BDS045630 | Nasotapp [Brompheniramine Maleate 4 mg.+Phenylephrine HCl 10 mg.] | usable_with_warning | source_gap | attach accepted source evidence |
| FRM0002 | uri_wet_cough_adult | BDS002655 | Mucolid [Ambroxol HCl 30 mg.] | usable_with_warning | source_gap | attach accepted source evidence |
| FRM0002 | uri_wet_cough_adult | BDS002901 | Nac Long [Acetylcysteine 600 mg.] | usable_with_warning | source_gap | attach accepted source evidence |
| FRM0002 | uri_wet_cough_adult | BDS003762 | Tylenol 500 mg strip 10s [Paracetamol 500 mg.] | usable_with_warning | source_gap | attach accepted source evidence |
| FRM0002 | uri_wet_cough_adult | BDS045630 | Nasotapp [Brompheniramine Maleate 4 mg.+Phenylephrine HCl 10 mg.] | usable_with_warning | source_gap | attach accepted source evidence |
| FRM0002 | uri_wet_cough_adult | BDS002655 | Mucolid [Ambroxol HCl 30 mg.] | usable_with_warning | source_gap | attach accepted source evidence |
| FRM0002 | uri_wet_cough_adult | BDS002901 | Nac Long [Acetylcysteine 600 mg.] | usable_with_warning | source_gap | attach accepted source evidence |
| FRM0003 | uri_diarrhea_adult | BDS003762 | Tylenol 500 mg strip 10s [Paracetamol 500 mg.] | usable_with_warning | source_gap | attach accepted source evidence |
| FRM0003 | uri_diarrhea_adult | BDS004213 | Zyrtec [Cetirizine dihydrochloride 10 mg.] | usable_with_warning | source_gap | attach accepted source evidence |
| FRM0003 | uri_diarrhea_adult | BDS008282 | Cera ORS รสส้ม [Glucose Anhydrous 3 g.+Sodium Chloride 0.53 g.+Potassium Chlorid | manual_review_required | pending_manual_review | attach accepted source evidence |
| FRM0003 | uri_diarrhea_adult | BDS001248 | Bioflor [Lyophilized Saccharomyces boulardii 250 mg.] | manual_review_required | pending_manual_review | attach accepted source evidence |

## Runtime Schema Fields Found

```json
{
  "runtime_meta": [
    "antibioticCount",
    "antibiotic_rdu_issue_count",
    "antiviral_audit_issue_count",
    "build_version",
    "classCompareCount",
    "cleanCategoryCount",
    "cleanGenericCount",
    "clinical_audit_blocker_count",
    "clinical_audit_issue_count",
    "clinical_status",
    "complaintCount",
    "correction_overlay_applied_count",
    "defaultCount",
    "doctorPickCount",
    "drugCount",
    "evidence_antibiotic_auto_verified_count",
    "evidence_auto_resolved_gap_count",
    "evidence_auto_verified_count",
    "evidence_blocked_conflict_count",
    "evidence_blocked_low_confidence_count",
    "evidence_blocked_missing_required_safety_field_count",
    "evidence_peds_auto_verified_count",
    "evidence_pending_source_collection_count",
    "evidence_status",
    "generated_at",
    "guideline_patch_manual_review_count",
    "guideline_patch_pediatric_shortcut_count",
    "guideline_patch_runtime_count",
    "manual_review_count",
    "manual_review_product_count",
    "manual_review_queue_count",
    "manual_review_reason_counts",
    "pediatric_do_not_use_count",
    "pediatric_label_reference_only_count",
    "pediatric_pending_source_count",
    "pediatric_review_count",
    "pediatric_source_gap_count",
    "pediatric_verified_count",
    "pedsCount",
    "price_updated_at",
    "pricedDrugCount",
    "regimenCount",
    "regimen_safety_blocker_count",
    "registered_source_count",
    "runtime_index_count",
    "schema_version",
    "source",
    "source_coverage",
    "source_gap_count",
    "source_manifest_todo_count",
    "top50Count",
    "verified_source_count",
    "version",
    "workbook_qa_issue_count"
  ],
  "product_fields": [
    "ag",
    "auto_resolution_status",
    "c",
    "cc",
    "dp",
    "evidence_confidence",
    "evidence_required_fields_missing",
    "evidence_score",
    "evidence_source_ids",
    "evidence_status",
    "f",
    "fa",
    "g",
    "i",
    "manual_review_reasons",
    "manual_review_required",
    "n",
    "p",
    "pr",
    "price_confidence",
    "price_source",
    "source_ids",
    "source_status",
    "tl"
  ],
  "complaint_fields": [
    "a",
    "c",
    "d",
    "g",
    "i",
    "manual_review",
    "mt",
    "p",
    "r",
    "src"
  ],
  "regimen_line_fields": [
    "antibiotic_gate_status",
    "auto_resolution_status",
    "blocked_reason",
    "clinical_audit_status",
    "clinical_readiness",
    "correction_status",
    "evidence_confidence",
    "evidence_required_fields_missing",
    "evidence_score",
    "evidence_source_ids",
    "evidence_status",
    "fast_mode_allowed",
    "i",
    "manual_review_required",
    "missing_requirements",
    "n",
    "next_action",
    "non_drug_action",
    "o",
    "p",
    "pediatric_gate_status",
    "product_match_status",
    "quick_caution",
    "quick_side_effects",
    "regimen_safety_status",
    "s",
    "source_gap_priority",
    "source_status",
    "t",
    "u"
  ]
}
```
