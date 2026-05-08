# Medical Refresh Workbook Intake Report

- CSV source: `/Users/a12/Documents/GitHub/Druglist/exports/refresh_csv`

## 1_Product_Master_Export

- Row count: 910
- Columns: product_id, brand_name, generic_name, composition, strength, dosage_form, route, pack, price, BDS, indication_text, caution, side_effect, contraindication, pregnancy_lactation, pediatric_flag, antibiotic_flag, source_status, clinical_readiness, manual_review_required, blocked_reason, old_runtime_status, source_runtime_path
- Missing IDs: {'product_id': 0}
- Duplicate IDs: {'product_id': 0}
- Rows without verified source: 910
- Blocked/manual/source-gap rows: 0

## 2_Regimen_Master_Export

- Row count: 987
- Columns: regimen_id, disease_key, disease_name, ICD10, complaint_key, role, tier, default_row, product_id, drug_name, composition, BDS, sig, duration, dispense, caution, side_effect, clinical_readiness, fast_mode_allowed, evidence_status, source_status, blocked_reason, missing_requirements, next_action, old_runtime_status, source_runtime_path
- Missing IDs: {'regimen_id': 0, 'disease_key': 0, 'complaint_key': 0, 'product_id': 0}
- Duplicate IDs: {'regimen_id': 132, 'disease_key': 132, 'complaint_key': 329, 'product_id': 79}
- Rows without verified source: 987
- Blocked/manual/source-gap rows: 987

## 3_Complaint_Disease_Map

- Row count: 391
- Columns: complaint_key, complaint_text, disease_key, disease_name, category, age_group, match_type, priority, regimen_ids, source_status, manual_review, source_runtime_path, complaint_index_matches
- Missing IDs: {'complaint_key': 0, 'disease_key': 0}
- Duplicate IDs: {'complaint_key': 0, 'disease_key': 130}
- Rows without verified source: 391
- Blocked/manual/source-gap rows: 0

## 4_Top_50_Defaults

- Row count: 50
- Columns: regimen_id, disease_key, disease_name, ICD10, complaint_key, role, tier, default_row, product_id, drug_name, composition, BDS, sig, duration, dispense, caution, side_effect, clinical_readiness, fast_mode_allowed, evidence_status, source_status, blocked_reason, missing_requirements, next_action, old_runtime_status, source_runtime_path
- Missing IDs: {'regimen_id': 0, 'disease_key': 0, 'complaint_key': 0, 'product_id': 0}
- Duplicate IDs: {'regimen_id': 7, 'disease_key': 7, 'complaint_key': 12, 'product_id': 11}
- Rows without verified source: 50
- Blocked/manual/source-gap rows: 50

## 5_Clinic_Defaults

- Row count: 336
- Columns: regimen_id, disease_key, disease_name, workflow_label, default_row, product_id, line_id, role, drug_name, sig, duration, dispense, clinical_readiness, fast_mode_allowed, source_status, next_action, source_runtime_path
- Missing IDs: {'regimen_id': 0, 'disease_key': 0, 'product_id': 0, 'line_id': 0}
- Duplicate IDs: {'regimen_id': 111, 'disease_key': 111, 'product_id': 63, 'line_id': 5}
- Rows without verified source: 336
- Blocked/manual/source-gap rows: 336

## 6_Pediatric_Dosing

- Row count: 93
- Columns: product_id, display_name, generic_key, form, route, concentration, dose_output_status, auto_dose_enabled, age_bw_rule, dose_basis, max_dose, source_ids, review_reasons, source_runtime_path
- Missing IDs: {'product_id': 0}
- Duplicate IDs: {'product_id': 0}
- Rows without verified source: 0
- Blocked/manual/source-gap rows: 0

## 7_Antibiotic_Rows

- Row count: 192
- Columns: regimen_id, disease_key, disease_name, ICD10, complaint_key, role, tier, default_row, product_id, drug_name, composition, BDS, sig, duration, dispense, caution, side_effect, clinical_readiness, fast_mode_allowed, evidence_status, source_status, blocked_reason, missing_requirements, next_action, old_runtime_status, source_runtime_path, row_source, issue_id, severity, issue_type, recommended_action
- Missing IDs: {'regimen_id': 0, 'disease_key': 0, 'complaint_key': 48, 'product_id': 0, 'issue_id': 144}
- Duplicate IDs: {'regimen_id': 35, 'disease_key': 35, 'complaint_key': 33, 'product_id': 19, 'issue_id': 0}
- Rows without verified source: 192
- Blocked/manual/source-gap rows: 144

## 8_Source_Evidence_Queue

- Row count: 103
- Columns: gap_id, entity_type, entity_id, required_source_priority, status, manual_review, queue_type, source_file, source_runtime_path, affected_products, todo_id, source_id_suggestion, title_query, organization_target, clinical_domain, related_drugs, related_complaints, evidence_needed, preferred_source_type, search_query, priority, review_status, source_url_candidates, notes, missing_item, review_note
- Missing IDs: {'gap_id': 31, 'entity_id': 31, 'todo_id': 72}
- Duplicate IDs: {'gap_id': 36, 'entity_id': 36, 'todo_id': 0}
- Rows without verified source: 0
- Blocked/manual/source-gap rows: 0

## 9_Clinical_QC

- Row count: 874
- Columns: issue_id, severity, disease_key, regimen_id, product_id, generic_name, current_sig, current_dose, current_duration, issue_type, why_suspect, source_status, evidence_status, recommended_action, source_gap_needed, test_case_needed, source_file, source_runtime_path, display_name, issues, id, reasons, source_row, status, correction_id, target_id, action
- Missing IDs: {'issue_id': 336, 'disease_key': 570, 'regimen_id': 570, 'product_id': 341, 'correction_id': 872, 'target_id': 872}
- Duplicate IDs: {'issue_id': 9, 'disease_key': 95, 'regimen_id': 95, 'product_id': 51, 'correction_id': 0, 'target_id': 0}
- Rows without verified source: 874
- Blocked/manual/source-gap rows: 169

## 10_Import_Diff_Template

- Row count: 1
- Columns: change_id, target_type, stable_id, field_name, old_value, new_value, source_id, reviewer, review_status, notes
- Missing IDs: {'change_id': 1, 'stable_id': 1, 'source_id': 1}
- Duplicate IDs: {'change_id': 0, 'stable_id': 0, 'source_id': 0}
- Rows without verified source: 0
- Blocked/manual/source-gap rows: 0

## 11_OPD_Fast_Index_Template

- Row count: 164
- Columns: disease_id, display_name, complaints, regimen_ids, manual_review, source_runtime_path
- Missing IDs: {'disease_id': 0}
- Duplicate IDs: {'disease_id': 0}
- Rows without verified source: 0
- Blocked/manual/source-gap rows: 0

## 12_Drug_Short_Lookup_Template

- Row count: 910
- Columns: product_id, display_name, product_name, composition, generic, form, route, category, manual_review, source_runtime_path
- Missing IDs: {'product_id': 0}
- Duplicate IDs: {'product_id': 0}
- Rows without verified source: 0
- Blocked/manual/source-gap rows: 0

## High-Risk Row Samples

| regimen_id | disease_key | product_id | drug_name | readiness | source |
|---|---|---|---|---|---|
| FRM0002 | uri_wet_cough_adult | BDS003762 | Tylenol 500 mg strip 10s [Paracetamol 500 mg.] | usable_with_warning | source_gap |
| FRM0002 | uri_wet_cough_adult | BDS045630 | Nasotapp [Brompheniramine Maleate 4 mg.+Phenylephrine HCl 10 mg.] | usable_with_warning | source_gap |
| FRM0002 | uri_wet_cough_adult | BDS002655 | Mucolid [Ambroxol HCl 30 mg.] | usable_with_warning | source_gap |
| FRM0002 | uri_wet_cough_adult | BDS002901 | Nac Long [Acetylcysteine 600 mg.] | usable_with_warning | source_gap |
| FRM0002 | uri_wet_cough_adult | BDS003762 | Tylenol 500 mg strip 10s [Paracetamol 500 mg.] | usable_with_warning | source_gap |
| FRM0002 | uri_wet_cough_adult | BDS045630 | Nasotapp [Brompheniramine Maleate 4 mg.+Phenylephrine HCl 10 mg.] | usable_with_warning | source_gap |
| FRM0002 | uri_wet_cough_adult | BDS002655 | Mucolid [Ambroxol HCl 30 mg.] | usable_with_warning | source_gap |
| FRM0002 | uri_wet_cough_adult | BDS002901 | Nac Long [Acetylcysteine 600 mg.] | usable_with_warning | source_gap |
| FRM0007 | dry_eye_adult | BDS004035 | Vislube [Sodium Hyaluronate 0.18% (Sodium Hyaluronate 1.8 mg.+Sodium Chloride 2. | manual_review_required | pending_manual_review |
| FRM0007 | dry_eye_adult | BDS001552 | Cellufresh [Carboxymethylcellulose Sodium (CMC) 0.5%+Calcium Chloride+Magnesium  | manual_review_required | pending_manual_review |
| FRM0008 | acute_watery_diarrhea_peds | BDS008282 | Cera ORS รสส้ม [Glucose Anhydrous 3 g.+Sodium Chloride 0.53 g.+Potassium Chlorid | manual_review_required | pending_manual_review |
| FRM0009 | uri_dry_cough_adult | BDS003762 | Tylenol 500 mg strip 10s [Paracetamol 500 mg.] | usable_with_warning | source_gap |
| FRM0009 | uri_dry_cough_adult | BDS045630 | Nasotapp [Brompheniramine Maleate 4 mg.+Phenylephrine HCl 10 mg.] | usable_with_warning | source_gap |
| FRM0009 | uri_dry_cough_adult | BDS002211 | Icolid (ควบคุมจำนวน) [Dextromethorphan HBr 15 mg.] | usable_with_warning | source_gap |
| FRM0009 | uri_dry_cough_adult | BDS007973 | Fartussin (ควบคุมจำนวน) [Dextromethorphan HBr 15 mg.+Glyceryl Guaiacolate 100 mg | usable_with_warning | source_gap |
| FRM0009 | uri_dry_cough_adult | BDS003747 | Telfast 180 mg [Fexofenadine HCl 180 mg.] | usable_with_warning | source_gap |
| FRM0009 | uri_dry_cough_adult | BDS003762 | Tylenol 500 mg strip 10s [Paracetamol 500 mg.] | usable_with_warning | source_gap |
| FRM0009 | uri_dry_cough_adult | BDS045630 | Nasotapp [Brompheniramine Maleate 4 mg.+Phenylephrine HCl 10 mg.] | usable_with_warning | source_gap |
| FRM0009 | uri_dry_cough_adult | BDS002211 | Icolid (ควบคุมจำนวน) [Dextromethorphan HBr 15 mg.] | usable_with_warning | source_gap |
| FRM0009 | uri_dry_cough_adult | BDS007973 | Fartussin (ควบคุมจำนวน) [Dextromethorphan HBr 15 mg.+Glyceryl Guaiacolate 100 mg | usable_with_warning | source_gap |
