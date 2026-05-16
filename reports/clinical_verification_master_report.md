# Clinical Verification Master Report

Generated: 2026-05-02T06:45:17Z

- Product count: 910
- Complaint count: 1141
- Regimen count: 412
- Source coverage: 0.0
- Verified source count: 0
- Evidence claims: 0
- Auto verified claims: 0
- Source manifest accepted count: 0
- Acyclovir/antiviral findings: 3
- Pediatric source gap findings: 93
- Antibiotic/RDU findings: 91
- Regimen safety findings: 19
- Workbook QA findings: 234
- Correction overlay applied: 2
- Source manifest TODO count: 31

## What Is Safer Now
- Suspicious source-gap antiviral/herpes/zoster rows are audited and correction-gated.
- Pediatric candidates remain visible but calculated dosing remains blocked without source/concentration/age-BW gates.
- Antibiotic/RDU rows are audited for source-backed disease criteria.
- Correction overlays can block or downgrade unsafe runtime rows without fabricating replacement doses.

## Top 20 Blocker Issues
- `CLIN_FRM0027_RX1_ANTIVIRAL` herpes_zoster_adult BDS008065: block_until_source_verified
- `CLIN_FRM0027_RX2_ANTIVIRAL` herpes_zoster_adult BDS003762: block_until_source_verified
- `CLIN_FRM0028_RX1_ANTIBIOTIC` tinea_pruritic_rash_adult BDS001491: remove_from_RX_NOW
- `CLIN_FRM0061_RED_FLAG` screen_related_dry_eye_adult : require_red_flag_override
- `CLIN_FRM0072_RED_FLAG` eye_irritation_peds : require_red_flag_override
- `CLIN_FRM0073_RED_FLAG` dry_eye_peds_support : require_red_flag_override
- `CLIN_FRM0078_RED_FLAG` insect_bite_peds : require_red_flag_override
- `CLIN_FRM0083_RED_FLAG` abdominal_colic_peds : require_red_flag_override
- `CLIN_FRM0120_RX1_ANTIBIOTIC` dysuria_lower_uti_adult BDS007591: remove_from_RX_NOW
- `CLIN_PATCH_FRM_AAN_DPN_20260516_RED_FLAG` painful_diabetic_polyneuropathy_adult : require_red_flag_override
- `CLIN_PATCH_FRM_PEDS_DIARR_DEHYD_ORAL_20260516_RED_FLAG` acute_gastroenteritis_peds_some_dehydration : require_red_flag_override
- `CLIN_PATCH_FRM_PEDS_DIARR_NO_DEHYD_20260516_RED_FLAG` acute_watery_diarrhea_peds_no_dehydration : require_red_flag_override
- `CLIN_PATCH_FRM_PEDS_DIARR_SEV_DEHYD_20260516_RED_FLAG` acute_gastroenteritis_peds_severe_dehydration_gate : require_red_flag_override
- `AV_FRM0027_RX1_BDS008065` herpes_zoster_adult BDS008065: block_until_source_verified
- `AV_FRM0027_RX2_BDS003762` herpes_zoster_adult BDS003762: block_until_source_verified
- `ABX_FRM0028_RX1_BDS001491` tinea_pruritic_rash_adult BDS001491: remove_from_RX_NOW
- `ABX_FRM0031_RX1_BDS002003` minor_skin_infection_topical_adult BDS002003: require_antibiotic_criteria
- `ABX_FRM0033_RX1_BDS001103` bacterial_sinusitis_adult BDS001103: require_antibiotic_criteria
- `ABX_FRM0034_RX1_BDS002201` bacterial_pharyngitis_adult BDS002201: require_antibiotic_criteria
- `ABX_FRM0058_RX1_BDS001491` tinea_corporis_localized_adult BDS001491: require_antibiotic_criteria

## Next Source Files Or URLs Needed
- Acyclovir/herpes zoster/shingles adult treatment guideline with dose/frequency/duration/timing window/red flags.
- Herpes labialis treatment guideline separating topical and oral antiviral use.
- Pediatric paracetamol/ibuprofen/ORS/antihistamine dose sources with age/BW, max dose, frequency, and concentration rules.
- Antibiotic/RDU sources for no-antibiotic viral URI/simple diarrhea defaults and disease-specific bacterial criteria.
- Red-eye, dehydration, dyspnea, petechiae, GI bleed, pregnancy/renal/hepatic red-flag sources.
