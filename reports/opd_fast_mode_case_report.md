# OPD FAST MODE Case Report

This harness checks deterministic runtime behavior and safety gates. It does not prove complete clinical correctness.

Cases: 40
Pass: True

| # | Input | Disease / red flag | Meds | Antibiotics | Readiness | Pass |
|---|---|---|---:|---:|---|---|
| 1 | allergic rhinitis | allergic_rhinitis_adult | 4 | 0 | manual_review_required, usable_with_warning | True |
| 2 | uri with wet cough | uri_wet_cough_adult | 4 | 0 | usable_with_warning | True |
| 3 | cough sore throat sputum nasal discharge | uri_wet_cough_adult | 4 | 0 | usable_with_warning | True |
| 4 | sore throat no fever | acute_sore_throat_no_abx | 3 | 1 | manual_review_required | True |
| 5 | fever myalgia | viral_fever_bodyache_adult | 2 | 0 | usable_with_warning | True |
| 6 | diarrhea adult | uri_diarrhea_adult | 7 | 0 | manual_review_required, usable_with_warning | True |
| 7 | diarrhea 5 yr BW 20 kg | acute_watery_diarrhea_peds | 1 | 0 | manual_review_required | True |
| 8 | dry eye | dry_eye_adult | 2 | 0 | manual_review_required | True |
| 9 | bacterial conjunctivitis | bacterial_conjunctivitis_adult | 3 | 3 | manual_review_required | True |
| 10 | red eye pain no visual loss | eye_red_flag | 0 | 0 | n/a | True |
| 11 | red eye with vision loss | eye_red_flag | 0 | 0 | n/a | True |
| 12 | tinea cruris | tinea_cruris_adult | 2 | 0 | usable_with_warning | True |
| 13 | aphthous ulcer | aphthous_ulcer_pain_adult | 3 | 0 | manual_review_required, usable_with_warning | True |
| 14 | herpes labialis | herpes_labialis_adult | 1 | 0 | manual_review_required | True |
| 15 | lip dermatitis | itchy_dermatitis_adult | 3 | 0 | manual_review_required, usable_with_warning | True |
| 16 | dyspepsia | dyspepsia_gas_adult | 3 | 0 | usable_with_warning | True |
| 17 | GERD | gerd_alarm_or_refractory | 4 | 0 | manual_review_required | True |
| 18 | constipation with hemorrhoid | constipation | 0 | 0 | n/a | True |
| 19 | dysuria | dysuria_lower_uti_adult | 1 | 1 | manual_review_required | True |
| 20 | urinary frequency pelvic pain | urinary_red_flag | 0 | 0 | n/a | True |
| 21 | dysmenorrhea | dysmenorrhea | 0 | 0 | n/a | True |
| 22 | one-sided headache no neurodef | tension_headache_adult | 2 | 0 | usable_with_warning | True |
| 23 | nausea dizzy | vertigo_adult | 1 | 0 | usable_with_warning | True |
| 24 | pterygium inflamed | pterygium | 0 | 0 | n/a | True |
| 25 | eyelid painful bump | bacterial_eyelid_infection_adult | 2 | 2 | manual_review_required | True |
| 26 | uri 10 yr BW 28 kg can take pill | uri_wet_cough_peds | 4 | 0 | manual_review_required | True |
| 27 | fever 1 yr BW 10 kg | viral_fever_peds_support | 1 | 0 | manual_review_required | True |
| 28 | fever 5 yr BW 20 kg | viral_fever_peds_support | 1 | 0 | manual_review_required | True |
| 29 | allergic rhinitis 6 yr BW 20 kg | allergic_rhinitis_peds | 2 | 0 | manual_review_required | True |
| 30 | cough cold 3 yr BW 14 kg | post_uri_cough_peds | 2 | 0 | manual_review_required | True |
| 31 | suspected antibiotic allergy | allergy_review | 0 | 0 | n/a | True |
| 32 | penicillin allergy with bacterial disease | allergy_review | 0 | 0 | n/a | True |
| 33 | NSAID allergy | allergy_review | 0 | 0 | n/a | True |
| 34 | pregnancy with pain | pregnancy_review | 0 | 0 | n/a | True |
| 35 | renal disease with NSAID request | renal_review | 0 | 0 | n/a | True |
| 36 | diarrhea with blood | dehydration_or_invasive_diarrhea | 0 | 0 | n/a | True |
| 37 | dyspnea with cough | dyspnea_red_flag | 0 | 0 | n/a | True |
| 38 | petechiae fever | systemic_red_flag | 0 | 0 | n/a | True |
| 39 | severe eye pain photophobia | eye_red_flag | 0 | 0 | n/a | True |
| 40 | vomiting severe dehydration | dehydration_red_flag | 0 | 0 | n/a | True |
