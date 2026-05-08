#!/usr/bin/env python3
"""Create conservative, snippet-backed evidence claims from accepted sources."""

from __future__ import annotations

from medical_refresh_common import ROOT, read_json, stable_id, text_window, write_json, write_report

KEYWORD_CLAIMS = [
    {
        "source_ids": ["cdc_shingles_clinical_overview", "cdc_sti_herpes_guideline"],
        "keywords": ["acyclovir", "valacyclovir", "famciclovir"],
        "claim_type": "disease_strategy",
        "status": "indication_verified_dose_missing",
        "patient_group": "adult",
        "missing": ["source-backed dose", "frequency", "duration"],
    },
    {
        "source_ids": ["cdc_shingles_clinical_overview"],
        "keywords": ["72 hours", "symptom onset"],
        "claim_type": "timing_window",
        "status": "usable_with_warning",
        "patient_group": "adult",
        "missing": ["dose", "duration"],
    },
    {
        "source_ids": ["who_aware_antibiotic_book", "nice_sore_throat_antimicrobial"],
        "keywords": ["antibiotic", "viral"],
        "claim_type": "no_antibiotic_criteria",
        "status": "usable_with_warning",
        "patient_group": "both",
        "missing": ["disease-specific local criteria"],
    },
    {
        "source_ids": ["who_eml_emlc_lists"],
        "keywords": ["essential medicines"],
        "claim_type": "product_label_composition",
        "status": "label_verified_only",
        "patient_group": "both",
        "missing": ["disease-specific dose"],
    },
]


def main() -> int:
    accepted = read_json("data/source_refresh/source_manifest.accepted.json", {"sources": []}).get("sources", [])
    claims = []
    rejected = []
    for source in accepted:
        text_ref = source.get("local_file_reference") or ""
        text = ""
        if text_ref:
            path = ROOT / "data/source_refresh" / text_ref
            if path.exists():
                text = path.read_text(encoding="utf-8", errors="ignore")
        if not text:
            rejected.append({"source_id": source.get("source_id"), "rejected_reason": "no source text"})
            continue
        for rule in KEYWORD_CLAIMS:
            if source.get("source_id") not in rule["source_ids"]:
                continue
            snippet = text_window(text, rule["keywords"])
            if not snippet:
                continue
            claim_id = stable_id("claim", source.get("source_id"), rule["claim_type"], snippet[:120])
            claims.append(
                {
                    "claim_id": claim_id,
                    "source_id": source.get("source_id"),
                    "source_title": source.get("source_title"),
                    "organization": source.get("organization"),
                    "source_url": source.get("source_url"),
                    "local_file": source.get("local_file_reference"),
                    "page_or_section": "text search snippet",
                    "short_snippet": snippet[:700],
                    "claim_type": rule["claim_type"],
                    "disease_key": "",
                    "generic_name": "",
                    "product_id": "",
                    "regimen_id": "",
                    "patient_group": rule["patient_group"],
                    "dose_struct": {},
                    "confidence_score": 0.62 if rule["status"] != "label_verified_only" else 0.58,
                    "evidence_confidence": "medium" if rule["status"] != "label_verified_only" else "low",
                    "extraction_method": "keyword_snippet",
                    "missing_required_fields": rule["missing"],
                    "status": rule["status"],
                }
            )
    write_json("data/source_refresh/evidence_claims.json", {"claims": claims})
    write_json("data/source_refresh/evidence_claims_rejected.json", {"claims": rejected})
    write_report(
        "reports/source_refresh/evidence_claim_extraction_report.md",
        "Evidence Claim Extraction Report",
        [
            f"- Accepted sources inspected: {len(accepted)}",
            f"- Snippet-backed claims created: {len(claims)}",
            f"- Rejected source/claim attempts: {len(rejected)}",
            f"- Auto-ready dose claims: 0",
            "- Conservative rule: no dose, duration, max dose, pediatric dose, or antibiotic use criterion is verified without exact snippet support.",
        ],
    )
    print(f"medical_evidence_extract: claims={len(claims)} rejected={len(rejected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
