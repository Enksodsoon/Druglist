#!/usr/bin/env python3
"""Audit OPD regimens for unsupported or unsafe clinical readiness."""
from __future__ import annotations

from clinical_audit_common import (
    NO_ABX_DISEASE_TERMS,
    RED_FLAG_TERMS,
    contains_any,
    is_antibiotic,
    is_antiviral,
    make_issue,
    needs_concentration,
    product_map,
    regimens,
    stable_issue,
    text_for,
    write_issue_artifacts,
)


def audit() -> list[dict[str, object]]:
    products = product_map()
    issues: list[dict[str, object]] = []
    seen_roles: set[tuple[str, str, str]] = set()
    for regimen in regimens():
        disease_id = str(regimen.get("disease_id") or "")
        disease_text = text_for(disease_id, regimen.get("display_name"), regimen.get("workflow_label"))
        if contains_any(disease_text, RED_FLAG_TERMS):
            issues.append(
                make_issue(
                    issue_id=stable_issue("CLIN", regimen.get("regimen_id"), "red_flag"),
                    severity="blocker",
                    disease_key=disease_id,
                    regimen_id=str(regimen.get("regimen_id") or ""),
                    issue_type="red_flag_should_override_prescribing",
                    why_suspect="Disease key includes red-flag language; routine prescribing must be blocked until source-backed triage rules exist.",
                    source_status=str(regimen.get("source_status") or ""),
                    recommended_action="require_red_flag_override",
                )
            )
        for line in regimen.get("lines") or []:
            product = products.get(str(line.get("product_id") or "")) or {}
            source_status = str(line.get("source_status") or "")
            readiness = str(line.get("clinical_readiness") or "")
            fast_allowed = bool(line.get("fast_mode_allowed"))
            generic = str(product.get("generic") or "")
            issue_base = {
                "disease_key": disease_id,
                "regimen_id": str(regimen.get("regimen_id") or ""),
                "product_id": str(line.get("product_id") or ""),
                "generic_name": generic,
                "current_sig": str(line.get("order_text") or ""),
                "current_duration": str(line.get("duration_label") or ""),
                "source_status": source_status,
                "evidence_status": str(line.get("evidence_status") or "pending_source_collection"),
            }
            if source_status != "source_verified" and fast_allowed:
                issues.append(
                    make_issue(
                        **issue_base,
                        issue_id=stable_issue("CLIN", regimen.get("regimen_id"), line.get("line_id"), "fast_source_gap"),
                        severity="high",
                        issue_type="regimen_listed_usable_despite_evidence_missing",
                        why_suspect="Line is allowed in FAST MODE without verified source evidence.",
                        recommended_action="manual_review_required",
                    )
                )
            if is_antiviral(product, line, disease_id):
                issues.append(
                    make_issue(
                        **issue_base,
                        issue_id=stable_issue("CLIN", regimen.get("regimen_id"), line.get("line_id"), "antiviral"),
                        severity="blocker" if "zoster" in disease_text or "shingles" in disease_text else "high",
                        issue_type="unsupported_antiviral_regimen",
                        why_suspect="Antiviral disease-specific dose/frequency/duration requires accepted guideline evidence; product availability is not enough.",
                        recommended_action="block_until_source_verified",
                    )
                )
            if is_antibiotic(product, line, disease_id):
                action = "remove_from_RX_NOW" if contains_any(disease_text, NO_ABX_DISEASE_TERMS) else "require_antibiotic_criteria"
                issues.append(
                    make_issue(
                        **issue_base,
                        issue_id=stable_issue("CLIN", regimen.get("regimen_id"), line.get("line_id"), "antibiotic"),
                        severity="blocker" if action == "remove_from_RX_NOW" else "high",
                        issue_type="antibiotic_source_or_criteria_missing",
                        why_suspect="Antibiotic use requires bacterial diagnosis/criteria plus source-backed dose and duration.",
                        recommended_action=action,
                    )
                )
            if needs_concentration(product):
                issues.append(
                    make_issue(
                        **issue_base,
                        issue_id=stable_issue("CLIN", product.get("id"), "missing_concentration"),
                        severity="medium",
                        issue_type="product_concentration_missing",
                        why_suspect="Liquid/drop/suspension product needs concentration before dose conversion can be trusted.",
                        recommended_action="source_gap",
                    )
                )
            role_key = (str(regimen.get("regimen_id") or ""), str(product.get("generic_key") or generic).lower(), str(line.get("line_type") or ""))
            if role_key in seen_roles:
                issues.append(
                    make_issue(
                        **issue_base,
                        issue_id=stable_issue("CLIN", regimen.get("regimen_id"), line.get("line_id"), "duplicate"),
                        severity="medium",
                        issue_type="duplicate_therapeutic_role_or_ingredient",
                        why_suspect="Same generic/role appears more than once in the regimen.",
                        recommended_action="manual_review_required",
                        source_gap_needed=False,
                    )
                )
            seen_roles.add(role_key)
            if readiness == "ready" and source_status != "source_verified":
                issues.append(
                    make_issue(
                        **issue_base,
                        issue_id=stable_issue("CLIN", regimen.get("regimen_id"), line.get("line_id"), "false_ready"),
                        severity="blocker",
                        issue_type="local_rule_only_shown_as_ready",
                        why_suspect="Ready status is not allowed without verified source evidence.",
                        recommended_action="block_until_source_verified",
                    )
                )
    return issues


def main() -> int:
    issues = audit()
    write_issue_artifacts(
        "data/meta/clinical_regimen_quality_issues.json",
        "reports/clinical_regimen_audit_report.md",
        "Clinical Regimen Audit Report",
        issues,
    )
    print(f"clinical_regimen_audit: issues={len(issues)} blockers={sum(1 for i in issues if i['severity']=='blocker')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
