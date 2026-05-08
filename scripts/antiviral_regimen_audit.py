#!/usr/bin/env python3
"""Audit acyclovir/antiviral products and herpes/zoster regimens."""
from __future__ import annotations

from engine_common import now_iso, write_json
from clinical_audit_common import is_antiviral, is_oral, is_topical, make_issue, product_map, products, regimens, stable_issue, text_for, write_issue_artifacts


def audit() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    product_by_id = product_map()
    antiviral_products = [product for product in products() if is_antiviral(product)]
    issues: list[dict[str, object]] = []
    gaps: list[dict[str, object]] = []
    for product in antiviral_products:
        gaps.append(
            {
                "gap_id": stable_issue("AV_GAP", product.get("id"), "product_metadata"),
                "product_id": product.get("id"),
                "generic_name": product.get("generic"),
                "clinical_domain": "antiviral",
                "evidence_needed": ["product form", "route", "concentration/strength", "label metadata"],
                "status": "pending_source_collection",
            }
        )
    for regimen in regimens():
        disease_id = str(regimen.get("disease_id") or "")
        disease_text = text_for(disease_id, regimen.get("display_name"), regimen.get("workflow_label"))
        if not any(term in disease_text for term in ["herpes", "zoster", "shingles", "varicella"]):
            continue
        gaps.append(
            {
                "gap_id": stable_issue("AV_GAP", disease_id, "disease_regimen"),
                "disease_key": disease_id,
                "regimen_id": regimen.get("regimen_id"),
                "clinical_domain": "antiviral",
                "evidence_needed": ["indication", "adult dose", "frequency", "duration", "timing window", "red flags"],
                "status": "pending_source_collection",
            }
        )
        for line in regimen.get("lines") or []:
            product = product_by_id.get(str(line.get("product_id") or "")) or {}
            if not is_antiviral(product, line, disease_id):
                continue
            issue_type = "unsupported_antiviral_regimen"
            why = "Antiviral disease-specific use needs accepted guideline evidence and traceable dose/frequency/duration."
            action = "block_until_source_verified"
            severity = "blocker"
            if ("zoster" in disease_text or "shingles" in disease_text) and is_topical(product):
                issue_type = "topical_oral_antiviral_route_mismatch"
                why = "Topical antiviral product cannot satisfy oral zoster regimen requirements."
            if "zoster" in disease_text and "400 mg" in text_for(product.get("display_name"), product.get("composition")):
                issue_type = "acyclovir_400_cannot_verify_zoster_by_availability"
                why = "Acyclovir 400 mg product availability alone cannot verify a shingles/zoster dose."
            if "labialis" in disease_text and is_oral(product):
                severity = "high"
                why = "Herpes labialis oral antiviral regimen remains source-gated until indication/dose/duration are accepted."
            issues.append(
                make_issue(
                    issue_id=stable_issue("AV", regimen.get("regimen_id"), line.get("line_id"), product.get("id")),
                    severity=severity,
                    disease_key=disease_id,
                    regimen_id=str(regimen.get("regimen_id") or ""),
                    product_id=str(product.get("id") or line.get("product_id") or ""),
                    generic_name=str(product.get("generic") or ""),
                    current_sig=str(line.get("order_text") or ""),
                    current_duration=str(line.get("duration_label") or ""),
                    issue_type=issue_type,
                    why_suspect=why,
                    source_status=str(line.get("source_status") or ""),
                    evidence_status=str(line.get("evidence_status") or "pending_source_collection"),
                    recommended_action=action,
                )
            )
    return issues, gaps


def main() -> int:
    issues, gaps = audit()
    write_issue_artifacts(
        "data/meta/antiviral_regimen_quality_issues.json",
        "reports/antiviral_regimen_audit_report.md",
        "Antiviral Regimen Audit Report",
        issues,
        [f"- Antiviral source gaps: {len(gaps)}"],
    )
    write_json("data/guidelines/antiviral_source_gaps.json", {"meta": {"generated_at": now_iso(), "gap_count": len(gaps)}, "items": gaps})
    print(f"antiviral_regimen_audit: issues={len(issues)} gaps={len(gaps)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
