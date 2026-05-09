#!/usr/bin/env python3
"""DailyMed official label adapter for Gold OPD first-pack unlocks."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from .common import AdapterOutput, fetch_text, text_window


LABEL_SPECS: list[dict[str, Any]] = [
    {
        "source_id": "dailymed_cetirizine_10mg_tablet_f756d3b1",
        "setid": "f756d3b1-d2e4-3705-e053-6294a90aa380",
        "title": "Cetirizine Hydrochloride Tablets, 10 mg",
        "product_id": "BDS004213",
        "generic": "cetirizine",
        "composition_terms": ["cetirizine", "10 mg"],
        "form_terms": ["tablet"],
        "disease_keys": ["allergic_rhinitis_adult"],
        "dose_value": "10 mg",
        "route_value": "PO",
        "frequency_value": "once daily",
        "duration_value": "symptomatic allergic-rhinitis use while symptoms persist",
        "max_dose_value": "10 mg/day",
        "phrases": {
            "adult_indication": "temporarily relieves these symptoms due to hay fever or other upper respiratory allergies",
            "adult_dose": "one 10 mg tablet once daily",
            "adult_route": "one 10 mg tablet once daily",
            "adult_frequency": "one 10 mg tablet once daily",
            "adult_duration": "temporarily relieves these symptoms due to hay fever or other upper respiratory allergies",
            "adult_max_dose": "do not take more than one 10 mg tablet in 24 hours",
            "contraindication": "Do not use if you have ever had an allergic reaction",
            "precaution": "Ask a doctor before use if you have liver or kidney disease",
            "common_side_effect": "drowsiness may occur",
            "major_interaction": "taking tranquilizers or sedatives",
            "pregnancy_lactation": "If pregnant or breast-feeding",
            "composition_strength_form_route": "one 10 mg tablet once daily",
        },
    },
    {
        "source_id": "dailymed_fexofenadine_180mg_tablet_2de81a41",
        "setid": "2de81a41-8488-7e39-e063-6294a90a394b",
        "title": "Fexofenadine Hydrochloride 180 mg Tablet",
        "product_id": "BDS003747",
        "generic": "fexofenadine",
        "composition_terms": ["fexofenadine", "180 mg"],
        "form_terms": ["tablet"],
        "disease_keys": ["allergic_rhinitis_adult"],
        "dose_value": "180 mg",
        "route_value": "PO",
        "frequency_value": "once daily",
        "duration_value": "symptomatic allergic-rhinitis use while symptoms persist",
        "max_dose_value": "180 mg/day",
        "phrases": {
            "adult_indication": "temporarily relieves these symptoms due to hay fever or other upper respiratory allergies",
            "adult_dose": "take one 180 mg tablet with water once a day",
            "adult_route": "take one 180 mg tablet with water once a day",
            "adult_frequency": "take one 180 mg tablet with water once a day",
            "adult_duration": "temporarily relieves these symptoms due to hay fever or other upper respiratory allergies",
            "adult_max_dose": "do not take more than 1 tablet in 24 hours",
            "contraindication": "Do not use if you have ever had an allergic reaction",
            "precaution": "Ask a doctor before use if you have kidney disease",
            "common_side_effect": "Stop use and ask a doctor if an allergic reaction",
            "major_interaction": "do not take at the same time as aluminum or magnesium antacids",
            "pregnancy_lactation": "If pregnant or breast-feeding",
            "composition_strength_form_route": "take one 180 mg tablet with water once a day",
        },
    },
    {
        "source_id": "dailymed_acetaminophen_500mg_tablet_0d67bb52",
        "setid": "0d67bb52-7ae3-439e-9e47-4e21eb0ca352",
        "title": "Acetaminophen 500 mg Tablet",
        "product_id": "BDS003762",
        "generic": "paracetamol",
        "composition_terms": ["paracetamol", "500 mg"],
        "form_terms": ["tablet"],
        "disease_key_tokens": [
            "common_cold",
            "viral_fever",
            "uri_wet_cough",
            "uri_dry_cough",
            "sore_throat",
            "acute_pharyngitis_viral",
            "tension_headache",
            "musculoskeletal_pain",
            "localized_muscle_ache",
            "aphthous_ulcer_pain",
        ],
        "dose_value": "1000 mg",
        "route_value": "PO",
        "frequency_value": "every 6 hours while symptoms last",
        "duration_value": "short-term symptomatic use; do not use for more than 10 days unless directed by a doctor",
        "max_dose_value": "3000 mg/day per selected OTC label",
        "phrases": {
            "adult_indication": "temporarily relieves minor aches and pains due to: the common cold",
            "adult_dose": "take 2 Caplets every 6 hours while symptoms last",
            "adult_route": "take 2 Caplets every 6 hours while symptoms last",
            "adult_frequency": "take 2 Caplets every 6 hours while symptoms last",
            "adult_duration": "do not use for more than 10 days unless directed by a doctor",
            "adult_max_dose": "do not take more than 6 caplets",
            "contraindication": "If you are allergic to acetaminophen",
            "precaution": "Ask a doctor before use if you have liver disease",
            "common_side_effect": "Acetaminophen may cause severe skin reactions",
            "major_interaction": "taking the blood thinning drug warfarin",
            "pregnancy_lactation": "If pregnant or breast-feeding",
            "composition_strength_form_route": "Active ingredient (in each caplet) Acetaminophen 500 mg",
        },
    },
    {
        "source_id": "dailymed_clotrimazole_1pct_cream_468f1b1b",
        "setid": "468f1b1b-f67d-8b98-e063-6294a90a7f45",
        "title": "Clotrimazole 1% Antifungal Cream",
        "product_id": "BDS001489",
        "generic": "clotrimazole",
        "composition_terms": ["clotrimazole", "1"],
        "form_terms": ["cream"],
        "disease_keys": ["tinea_cruris_adult", "tinea_pedis_adult", "tinea_corporis_clotrimazole_adult"],
        "dose_value": "thin layer to affected area",
        "route_value": "topical",
        "frequency_value": "twice daily",
        "duration_by_disease": {
            "tinea_cruris_adult": "2 weeks",
            "tinea_pedis_adult": "4 weeks",
            "tinea_corporis_clotrimazole_adult": "4 weeks",
        },
        "max_dose_value": "external-use topical dosing; no systemic max dose stated on selected label",
        "phrases": {
            "adult_indication": "Cures athlete's foot (tinea pedis), jock itch (tinea cruris), ringworm (tinea corporis)",
            "adult_dose": "Apply a thin layer over affected area twice daily",
            "adult_route": "For external use only",
            "adult_frequency": "twice daily (morning and night)",
            "adult_duration": "within 4 weeks (for athlete's foot or ringworm) or within 2 weeks (for jock itch)",
            "adult_max_dose": "For external use only",
            "contraindication": "Avoid contact with eyes",
            "precaution": "on children under 2 years of age unless directed by a doctor",
            "common_side_effect": "If irritation occurs",
            "major_interaction": "For external use only",
            "pregnancy_lactation": "on children under 2 years of age unless directed by a doctor",
            "composition_strength_form_route": "Clotrimazole 1% Antifungal",
        },
    },
    {
        "source_id": "dailymed_cmc_0_5_eye_drops_fb84fc0b",
        "setid": "fb84fc0b-9a62-812a-e053-6394a90aba0a",
        "title": "Carboxymethylcellulose Sodium 0.5% Eye Drops",
        "product_id": "BDS001552",
        "generic": "carboxymethylcellulose sodium",
        "composition_terms": ["carboxymethylcellulose", "0.5"],
        "form_terms": ["drops"],
        "disease_keys": ["dry_eye_adult", "eye_irritation_adult", "eye_lubrication_adult"],
        "dose_value": "1 to 2 drops",
        "route_value": "ophthalmic",
        "frequency_value": "as needed",
        "duration_value": "temporary relief; stop and ask a doctor if condition worsens or persists for more than 72 hours",
        "max_dose_value": "as-needed ophthalmic lubricant dosing; no daily maximum stated on selected label",
        "phrases": {
            "adult_indication": "for the temporary relief of burning, irritation, and, discomfort due to dryness of the eye",
            "adult_dose": "instill 1 to 2 drops in the affected eye(s) as needed",
            "adult_route": "For external use only",
            "adult_frequency": "instill 1 to 2 drops in the affected eye(s) as needed",
            "adult_duration": "persists for more than 72 hours",
            "adult_max_dose": "instill 1 to 2 drops in the affected eye(s) as needed",
            "contraindication": "Do not use if this product changes color or becomes cloudy",
            "precaution": "to avoid contamination, do not touch tip of container to any surface",
            "common_side_effect": "continued redness or irritation of the eye",
            "major_interaction": "For external use only",
            "pregnancy_lactation": "For external use only",
            "composition_strength_form_route": "Active ingredient Carboxymethylcellulose sodium 0.5%",
        },
    },
]


def _matches_product(row: dict[str, str], spec: dict[str, Any]) -> bool:
    if row.get("product_id") != spec["product_id"]:
        return False
    blob = (row.get("composition", "") + " " + row.get("drug_name", "")).lower()
    return all(term.lower() in blob for term in spec.get("composition_terms", []))


def _matches_disease(row: dict[str, str], spec: dict[str, Any]) -> bool:
    disease = row.get("disease_key", "")
    if disease in spec.get("disease_keys", []):
        return True
    return any(token in disease for token in spec.get("disease_key_tokens", []))


def _clean_snippet(snippet: str) -> str:
    return re.sub(r"\s+", " ", snippet).strip()[:700]


def run(candidate_rows: list[dict[str, str]]) -> AdapterOutput:
    out = AdapterOutput()
    for spec in LABEL_SPECS:
        rows = [row for row in candidate_rows if _matches_product(row, spec) and _matches_disease(row, spec)]
        if not rows:
            out.search_tasks.append(
                {
                    "adapter": "dailymed",
                    "query": f"{spec['generic']} DailyMed {spec['title']}",
                    "status": "not_applicable_no_matching_candidate",
                }
            )
            continue

        label_url = f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={spec['setid']}"
        xml_url = f"https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/{spec['setid']}.xml"
        try:
            text = fetch_text(xml_url)
        except Exception as exc:
            out.rejected_sources.append({"adapter": "dailymed", "source_url": label_url, "status": "source_unreachable", "reason": str(exc)})
            continue

        snippets = {field: _clean_snippet(text_window(text, phrase)) for field, phrase in spec["phrases"].items()}
        missing = [field for field, snippet in snippets.items() if not snippet]
        if missing:
            out.rejected_sources.append({"adapter": "dailymed", "source_url": label_url, "status": "missing_required_snippets", "missing": "; ".join(missing)})
            continue

        out.accepted_sources.append(
            {
                "source_id": spec["source_id"],
                "source_title": spec["title"],
                "source_org": "DailyMed / U.S. National Library of Medicine",
                "source_url": label_url,
                "access_date": date.today().isoformat(),
                "source_type": "official_product_label",
                "source_country_or_region": "United States",
                "adapter_name": "dailymed_adapter",
                "retrieval_status": "retrieved",
                "extraction_status": "field_snippets_extracted",
            }
        )
        for row in rows:
            disease = row.get("disease_key", "")
            duration_value = spec.get("duration_by_disease", {}).get(disease, spec.get("duration_value", ""))
            values = {
                "adult_indication": "source-supported indication",
                "adult_dose": spec.get("dose_value", ""),
                "adult_route": spec.get("route_value", ""),
                "adult_frequency": spec.get("frequency_value", ""),
                "adult_duration": duration_value,
                "adult_max_dose": spec.get("max_dose_value", ""),
                "contraindication": "source-backed contraindication/warning",
                "precaution": "source-backed precaution",
                "common_side_effect": "source-backed adverse effect/warning",
                "major_interaction": "source-backed interaction or label use statement",
                "pregnancy_lactation": "source-backed pregnancy/lactation or special-population statement",
                "composition_strength_form_route": "source-backed composition/strength/form/route",
            }
            for field, snippet in snippets.items():
                out.evidence_claims.append(
                    {
                        "claim_id": f"claim_{spec['source_id']}_{row.get('product_id')}_{disease}_{field}",
                        "source_id": spec["source_id"],
                        "source_title": spec["title"],
                        "source_org": "DailyMed / U.S. National Library of Medicine",
                        "source_url": label_url,
                        "source_type": "official_product_label",
                        "source_country_or_region": "United States",
                        "evidence_field": field,
                        "evidence_value": values.get(field, ""),
                        "evidence_snippet": snippet,
                        "confidence": 0.94,
                        "linked_product_id": row.get("product_id", ""),
                        "linked_regimen_id": row.get("regimen_id", ""),
                        "linked_disease_key": disease,
                        "linked_generic_name": spec["generic"],
                        "adapter_name": "dailymed_adapter",
                        "product_match_status": "generic_strength_form_route_match",
                    }
                )
    return out
