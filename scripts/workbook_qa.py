#!/usr/bin/env python3
"""QA source workbook-derived product layer without guessing corrections."""
from __future__ import annotations

from collections import Counter

from engine_common import clean, now_iso, write_json
from clinical_audit_common import needs_concentration, products, stable_issue


def audit() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    ids = Counter(clean(product.get("id")) for product in products())
    bds = Counter(clean(product.get("bds_code")) for product in products() if clean(product.get("bds_code")))
    for product in products():
        pid = clean(product.get("id"))
        issues = []
        if ids[pid] > 1:
            issues.append("duplicate product id")
        if clean(product.get("bds_code")) and bds[clean(product.get("bds_code"))] > 1:
            issues.append("duplicate BDS/product code")
        if not clean(product.get("composition")):
            issues.append("missing composition")
        if not clean(product.get("generic")):
            issues.append("missing generic")
        if not clean(product.get("form")):
            issues.append("missing route/form")
        if needs_concentration(product):
            issues.append("missing concentration for liquid/drop/suspension")
        if "+" in clean(product.get("composition")) and not product.get("role_tags"):
            issues.append("combo product needs ingredient/role review")
        if issues:
            rows.append(
                {
                    "issue_id": stable_issue("WBQA", pid, ",".join(issues)),
                    "product_id": pid,
                    "display_name": product.get("display_name"),
                    "generic_name": product.get("generic"),
                    "severity": "high" if any("missing generic" in item or "missing route" in item for item in issues) else "medium",
                    "issues": sorted(set(issues)),
                    "recommended_action": "manual_review_required",
                }
            )
    return rows


def main() -> int:
    rows = audit()
    write_json("data/meta/workbook_quality_issues.json", {"meta": {"generated_at": now_iso(), "issue_count": len(rows)}, "issues": rows})
    lines = ["# Workbook QA Report", "", f"Generated: {now_iso()}", "", f"- Product issues: {len(rows)}"]
    for row in rows[:30]:
        lines.append(f"- `{row['product_id']}` {row['display_name']}: {', '.join(row['issues'])}")
    open("reports/workbook_qa_report.md", "w", encoding="utf-8").write("\n".join(lines).rstrip() + "\n")
    print(f"workbook_qa: issues={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
