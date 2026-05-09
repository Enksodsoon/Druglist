#!/usr/bin/env python3
"""Extract exact, snippet-backed claims from acquired official sources."""

from __future__ import annotations

import re
from pathlib import Path

from medical_refresh_common import ROOT, access_date, read_csv_sheet, read_json, stable_id, text_window, write_json, write_report

CLAIMS_JSON = "data/source_refresh/exact_evidence_claims.json"
REJECTED_JSON = "data/source_refresh/exact_evidence_claims_rejected.json"


def source_text(local_ref: str) -> str:
    if not local_ref:
        return ""
    path = ROOT / "data/source_refresh" / local_ref
    return path.read_text(encoding="utf-8") if path.exists() else ""


def zoster_rows() -> list[dict[str, str]]:
    rows = read_csv_sheet("2_Regimen_Master_Export")
    return [
        row for row in rows
        if "zoster" in (row.get("disease_key", "") + " " + row.get("disease_name", "")).lower()
        and "acyclovir" in (row.get("composition", "") + " " + row.get("drug_name", "")).lower()
    ]


def uri_rows() -> list[dict[str, str]]:
    rows = read_csv_sheet("2_Regimen_Master_Export")
    return [
        row for row in rows
        if any(token in (row.get("disease_key", "") + " " + row.get("disease_name", "")).lower() for token in ["uri", "cough", "cold"])
    ]


def add_claim(claims: list[dict[str, object]], source: dict[str, object], claim_type: str, disease_key: str, generic: str, snippet: str, rows: list[dict[str, str]], dose_struct: dict[str, object] | None = None, confidence: float = 0.9, used_for_ready: bool = False, missing_fields: list[str] | None = None) -> None:
    claims.append(
        {
            "claim_id": stable_id("claim", source.get("source_id"), claim_type, disease_key, generic, snippet[:120]),
            "source_need_id": "",
            "source_id": source.get("source_id", ""),
            "source_title": source.get("source_title", ""),
            "organization": source.get("organization", ""),
            "url_or_file": source.get("source_url") or source.get("local_file_reference") or "",
            "year_version": source.get("year", ""),
            "access_date": source.get("access_date") or access_date(),
            "page_or_section": "HTML text",
            "short_snippet": re.sub(r"\s+", " ", snippet).strip()[:700],
            "disease_key": disease_key,
            "generic_name": generic,
            "product_id": "; ".join(sorted({row.get("product_id", "") for row in rows if row.get("product_id")})),
            "regimen_id": "; ".join(sorted({row.get("regimen_id", "") for row in rows if row.get("regimen_id")})),
            "claim_type": claim_type,
            "dose_struct": dose_struct or {},
            "confidence_score": confidence,
            "rows_matched": [f"{row.get('regimen_id')}:{row.get('product_id')}" for row in rows],
            "missing_fields": missing_fields or [],
            "used_for_ready_candidate": "yes" if used_for_ready else "no",
            "status": "auto_verified" if used_for_ready and not (missing_fields or []) else "usable_with_warning",
        }
    )


def main() -> int:
    accepted = read_json("data/source_refresh/source_manifest.accepted.json", {"sources": []}).get("sources", [])
    accepted_by_id = {source["source_id"]: source for source in accepted}
    claims: list[dict[str, object]] = []
    rejected: list[dict[str, object]] = []

    br = accepted_by_id.get("br_moh_herpes_treatment")
    if br:
        text = source_text(str(br.get("local_file_reference", "")))
        rows = zoster_rows()
        if re.search(r"800\s*mg.*via oral.*5 vezes ao dia.*7 dias", text, flags=re.I | re.S):
            snippet = text_window(text, ["Adultos sem comprometimento imunológico", "800mg"], width=620)
            add_claim(
                claims,
                br,
                "adult_dose",
                "herpes_zoster_adult",
                "acyclovir",
                snippet,
                rows,
                {
                    "dose_value": "800",
                    "dose_unit": "mg",
                    "route": "oral",
                    "frequency": "5 times daily",
                    "duration": "7 days",
                    "patient_group": "adult immunocompetent",
                    "max_per_dose": "",
                    "max_per_day": "",
                },
                confidence=0.92,
                used_for_ready=False,
            )
        else:
            rejected.append({"source_id": br["source_id"], "claim_type": "adult_dose", "rejected_reason": "exact zoster dose pattern not found"})

    cdc_cold = accepted_by_id.get("cdc_common_cold_treatment")
    if cdc_cold:
        text = source_text(str(cdc_cold.get("local_file_reference", "")))
        if "antibiotics" in text.lower() and "viruses" in text.lower():
            snippet = text_window(text, ["Antibiotics", "viruses"], width=620)
            add_claim(claims, cdc_cold, "no_antibiotic_criteria", "uri_wet_cough_adult", "", snippet, uri_rows(), confidence=0.86)
        else:
            rejected.append({"source_id": cdc_cold["source_id"], "claim_type": "no_antibiotic_criteria", "rejected_reason": "no snippet for antibiotics/viral URI found"})

    nice = accepted_by_id.get("nice_acute_cough_antimicrobial_ng120")
    if nice:
        text = source_text(str(nice.get("local_file_reference", "")))
        if "Do not offer an antibiotic" in text and "upper respiratory tract infection" in text:
            snippet = text_window(text, ["Do not offer an antibiotic", "upper respiratory tract infection"], width=700)
            add_claim(claims, nice, "no_antibiotic_criteria", "uri_wet_cough_adult", "", snippet, uri_rows(), confidence=0.9)
        else:
            rejected.append({"source_id": nice["source_id"], "claim_type": "no_antibiotic_criteria", "rejected_reason": "no exact no-antibiotic URI snippet found"})

    cdc_conj = accepted_by_id.get("cdc_conjunctivitis_treatment")
    if cdc_conj:
        text = source_text(str(cdc_conj.get("local_file_reference", "")))
        if "Mild bacterial pink eye may get better without antibiotic treatment" in text:
            rows = [row for row in read_csv_sheet("2_Regimen_Master_Export") if "conjunctivitis" in row.get("disease_key", "")]
            snippet = text_window(text, ["Mild bacterial pink eye", "antibiotic treatment"], width=620)
            add_claim(claims, cdc_conj, "disease_strategy", "bacterial_conjunctivitis_adult", "", snippet, rows, confidence=0.78, missing_fields=["exact topical antibiotic dose", "duration"])
        else:
            rejected.append({"source_id": cdc_conj["source_id"], "claim_type": "disease_strategy", "rejected_reason": "no bacterial conjunctivitis strategy snippet found"})

    write_json(CLAIMS_JSON, {"claims": claims})
    write_json(REJECTED_JSON, {"rejected_claims": rejected})
    used = sum(1 for claim in claims if claim.get("used_for_ready_candidate") == "yes")
    write_report(
        "reports/source_refresh/exact_claim_extraction_report.md",
        "Exact Claim Extraction Report",
        [
            f"- Exact/source-backed claims: {len(claims)}",
            f"- Used-for-ready candidate claims: {used}",
            f"- Rejected claim attempts: {len(rejected)}",
            "- Acyclovir/zoster exact dose evidence was extracted, but promotion is resolved separately against the workbook row duration.",
        ],
    )
    print(f"exact_claim_extractor: claims={len(claims)} rejected={len(rejected)} used_for_ready_candidates={used}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
