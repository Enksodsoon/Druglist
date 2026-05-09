#!/usr/bin/env python3
"""Run conservative official-source acquisition for first-unlock needs."""

from __future__ import annotations

from urllib.parse import urlparse

from medical_refresh_common import fetch_url, official_domain, read_json, stable_id, write_json, write_report

CANDIDATES = [
    {
        "source_need_pack": "acyclovir_herpes_zoster_adult",
        "source_id": "br_moh_herpes_treatment",
        "source_title": "Herpes - Tratamento",
        "organization": "Ministério da Saúde",
        "url_or_file": "https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/h/herpes/tratamento/tratamento",
        "source_type": "guideline",
        "country": "Brazil",
        "year_version": "source_version_unknown",
        "target_claim_types": ["adult_dose", "frequency", "duration", "timing_window"],
    },
    {
        "source_need_pack": "acyclovir_herpes_zoster_adult",
        "source_id": "cdc_shingles_clinical_overview",
        "source_title": "Clinical Overview of Shingles (Herpes Zoster)",
        "organization": "Centers for Disease Control and Prevention",
        "url_or_file": "https://www.cdc.gov/shingles/hcp/clinical-overview/index.html",
        "source_type": "guideline",
        "country": "United States",
        "year_version": "2024",
        "target_claim_types": ["disease_strategy", "timing_window", "red_flags"],
    },
    {
        "source_need_pack": "viral_uri_no_antibiotic",
        "source_id": "nice_acute_cough_antimicrobial_ng120",
        "source_title": "Cough (acute): antimicrobial prescribing",
        "organization": "National Institute for Health and Care Excellence",
        "url_or_file": "https://www.nice.org.uk/guidance/ng120/chapter/recommendations",
        "source_type": "guideline",
        "country": "United Kingdom",
        "year_version": "2019",
        "target_claim_types": ["no_antibiotic_criteria", "referral_criteria"],
    },
    {
        "source_need_pack": "viral_uri_no_antibiotic",
        "source_id": "cdc_common_cold_treatment",
        "source_title": "Manage Common Cold",
        "organization": "Centers for Disease Control and Prevention",
        "url_or_file": "https://www.cdc.gov/common-cold/treatment/index.html",
        "source_type": "guideline",
        "country": "United States",
        "year_version": "2026",
        "target_claim_types": ["no_antibiotic_criteria"],
    },
    {
        "source_need_pack": "bacterial_conjunctivitis_topical_antibiotic",
        "source_id": "cdc_conjunctivitis_treatment",
        "source_title": "How to Treat Pink Eye",
        "organization": "Centers for Disease Control and Prevention",
        "url_or_file": "https://www.cdc.gov/conjunctivitis/treatment/index.html",
        "source_type": "guideline",
        "country": "United States",
        "year_version": "2024",
        "target_claim_types": ["no_antibiotic_criteria", "disease_strategy"],
    },
]


def main() -> int:
    priority = read_json("data/source_refresh/source_acquisition_priority.json", {"source_needs": []}).get("source_needs", [])
    need_by_pack = {need["source_pack_id"]: need for need in priority}
    candidates = []
    for seed in CANDIDATES:
        need = need_by_pack.get(seed["source_need_pack"], {})
        url = seed["url_or_file"]
        ctype, raw, err = fetch_url(url, timeout=20)
        text_ready = bool(raw and "text/html" in ctype.lower() and official_domain(url))
        if text_ready:
            status = "text_check_ready"
            reason = "official domain fetched as HTML for text extraction"
            confidence = 0.9
        elif raw and urlparse(url).path.lower().endswith(".pdf"):
            status = "official_but_needs_manual_access"
            reason = "official PDF requires separate text extraction/OCR"
            confidence = 0.65
        elif err:
            status = "source_unreachable"
            reason = err[:240]
            confidence = 0.0
        else:
            status = "candidate_needs_text_check"
            reason = "candidate discovered but not text-checked"
            confidence = 0.45
        candidates.append(
            {
                "candidate_id": stable_id("cand", seed["source_id"], need.get("source_need_id", "")),
                "source_need_id": need.get("source_need_id", ""),
                "source_pack_id": seed["source_need_pack"],
                "source_id": seed["source_id"],
                "source_title": seed["source_title"],
                "organization": seed["organization"],
                "url_or_file": url,
                "source_type": seed["source_type"],
                "country": seed["country"],
                "year_version": seed["year_version"],
                "target_claim_types": seed["target_claim_types"],
                "candidate_status": status,
                "reason": reason,
                "confidence_score": confidence,
                "expected_rows_covered": need.get("expected_unlock_count", 0),
            }
        )
    write_json("data/source_refresh/source_acquisition_candidates.json", {"candidates": candidates})
    ready = sum(1 for c in candidates if c["candidate_status"] == "text_check_ready")
    write_report(
        "reports/source_refresh/source_acquisition_search_report.md",
        "Source Acquisition Search Report",
        [
            "- Internet/source acquisition run: yes",
            f"- Candidate sources checked: {len(candidates)}",
            f"- Text-check-ready official sources: {ready}",
            "- Sources were not accepted from title alone; only fetched official HTML proceeds to extraction.",
            "- Product-label-only sources were not used to unlock disease-specific regimens.",
        ],
    )
    print(f"source_acquisition_search: candidates={len(candidates)} text_ready={ready}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
