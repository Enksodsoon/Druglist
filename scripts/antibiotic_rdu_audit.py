#!/usr/bin/env python3
"""Audit antibiotic/RDU safety gates for OPD regimens."""
from __future__ import annotations

from engine_common import now_iso, write_json
from clinical_audit_common import NO_ABX_DISEASE_TERMS, contains_any, is_antibiotic, make_issue, product_map, products, regimens, stable_issue, text_for, write_issue_artifacts


def audit() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    product_by_id = product_map()
    issues: list[dict[str, object]] = []
    gaps: list[dict[str, object]] = []
    for product in products():
        if is_antibiotic(product):
            gaps.append(
                {
                    "gap_id": stable_issue("ABX_GAP", product.get("id"), "product_rule"),
                    "product_id": product.get("id"),
                    "generic_name": product.get("generic"),
                    "evidence_needed": ["disease-specific indication", "dose", "duration", "bacterial criteria", "allergy alternative"],
                    "status": "pending_source_collection",
                    "priority": 2,
                }
            )
    for regimen in regimens():
        disease_id = str(regimen.get("disease_id") or "")
        disease_text = text_for(disease_id, regimen.get("display_name"), regimen.get("workflow_label"))
        for line in regimen.get("lines") or []:
            product = product_by_id.get(str(line.get("product_id") or "")) or {}
            if not is_antibiotic(product, line, disease_id):
                continue
            no_use = contains_any(disease_text, NO_ABX_DISEASE_TERMS)
            source_missing = line.get("source_status") != "source_verified"
            issues.append(
                make_issue(
                    issue_id=stable_issue("ABX", regimen.get("regimen_id"), line.get("line_id"), product.get("id")),
                    severity="blocker" if no_use or str(line.get("line_type")).upper() == "RX NOW" else "high",
                    disease_key=disease_id,
                    regimen_id=str(regimen.get("regimen_id") or ""),
                    product_id=str(product.get("id") or line.get("product_id") or ""),
                    generic_name=str(product.get("generic") or ""),
                    current_sig=str(line.get("order_text") or ""),
                    current_duration=str(line.get("duration_label") or ""),
                    issue_type="inappropriate_antibiotic_default" if no_use else "antibiotic_source_gate_missing",
                    why_suspect="Antibiotic RX NOW requires source-backed bacterial diagnosis/criteria, dose, and duration.",
                    source_status=str(line.get("source_status") or ""),
                    evidence_status=str(line.get("evidence_status") or "pending_source_collection"),
                    recommended_action="remove_from_RX_NOW" if no_use else "require_antibiotic_criteria",
                    source_gap_needed=source_missing,
                )
            )
    return issues, gaps


def main() -> int:
    issues, gaps = audit()
    write_issue_artifacts(
        "data/meta/antibiotic_rdu_quality_issues.json",
        "reports/antibiotic_rdu_audit_report.md",
        "Antibiotic RDU Audit Report",
        issues,
        [f"- Antibiotic source gaps: {len(gaps)}"],
    )
    write_json("data/guidelines/antibiotic_source_gap_priority.json", {"meta": {"generated_at": now_iso(), "gap_count": len(gaps)}, "items": gaps})
    print(f"antibiotic_rdu_audit: issues={len(issues)} gaps={len(gaps)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
