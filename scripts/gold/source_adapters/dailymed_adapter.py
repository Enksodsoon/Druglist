#!/usr/bin/env python3
"""DailyMed official label adapter for Phase 2 Gold first unlocks."""

from __future__ import annotations

from datetime import date
from typing import Any

from .common import AdapterOutput, fetch_json, fetch_text, quote, text_window


def run(candidate_rows: list[dict[str, str]]) -> AdapterOutput:
    out = AdapterOutput()
    cetirizine_rows = [
        row for row in candidate_rows
        if row.get("disease_key") == "allergic_rhinitis_adult"
        and row.get("product_id") == "BDS004213"
        and "cetirizine" in (row.get("composition", "") + row.get("drug_name", "")).lower()
    ]
    if not cetirizine_rows:
        out.search_tasks.append({"adapter": "dailymed", "query": "cetirizine 10 mg tablet DailyMed allergic rhinitis dose", "status": "not_applicable_no_matching_candidate"})
        return out
    try:
        search = fetch_json(f"https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json?drug_name={quote('cetirizine 10 mg tablet')}")
        match = next((item for item in search.get("data", []) if "10 MG" in item.get("title", "").upper()), None)
        if not match:
            raise RuntimeError("DailyMed cetirizine 10 mg label not found")
        setid = match["setid"]
        label_url = f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={setid}"
        xml_url = f"https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/{setid}.xml"
        text = fetch_text(xml_url)
    except Exception as exc:
        out.rejected_sources.append({"adapter": "dailymed", "query": "cetirizine 10 mg tablet", "status": "source_unreachable", "reason": str(exc)})
        return out

    required = {
        "indication": text_window(text, "temporarily relieves these symptoms due to hay fever or other upper respiratory allergies"),
        "adult_dose": text_window(text, "one 10 mg tablet once daily"),
        "max_dose": text_window(text, "do not take more than one 10 mg tablet in 24 hours"),
        "contraindication": text_window(text, "Do not use if you have ever had an allergic reaction"),
        "precaution": text_window(text, "Ask a doctor before use if you have liver or kidney disease"),
        "side_effect": text_window(text, "drowsiness may occur"),
        "pregnancy_lactation": text_window(text, "If pregnant or breast-feeding"),
    }
    missing = [name for name, snippet in required.items() if not snippet]
    if missing:
        out.rejected_sources.append({"adapter": "dailymed", "source_url": label_url, "status": "missing_required_snippets", "missing": missing})
        return out

    source_id = f"dailymed_cetirizine_10mg_tablet_{setid[:8]}"
    out.accepted_sources.append(
        {
            "source_id": source_id,
            "source_title": match.get("title", "Cetirizine Hydrochloride Tablets, 10 mg"),
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
    fields = [
        ("adult_indication", required["indication"]),
        ("adult_dose", required["adult_dose"]),
        ("adult_route", required["adult_dose"]),
        ("adult_frequency", required["adult_dose"]),
        ("adult_duration", required["indication"]),
        ("adult_max_dose", required["max_dose"]),
        ("contraindication", required["contraindication"]),
        ("precaution", required["precaution"]),
        ("common_side_effect", required["side_effect"]),
        ("pregnancy_lactation", required["pregnancy_lactation"]),
        ("composition_strength_form_route", required["adult_dose"]),
    ]
    for field, snippet in fields:
        out.evidence_claims.append(
            {
                "claim_id": f"claim_{source_id}_{field}",
                "source_id": source_id,
                "source_title": match.get("title", "Cetirizine Hydrochloride Tablets, 10 mg"),
                "source_org": "DailyMed / U.S. National Library of Medicine",
                "source_url": label_url,
                "source_type": "official_product_label",
                "evidence_field": field,
                "evidence_snippet": snippet[:700],
                "confidence": 0.94,
                "linked_product_id": "BDS004213",
                "linked_regimen_id": "; ".join(sorted({row.get("regimen_id", "") for row in cetirizine_rows})),
                "linked_disease_key": "allergic_rhinitis_adult",
                "linked_generic_name": "cetirizine",
                "adapter_name": "dailymed_adapter",
            }
        )
    return out
