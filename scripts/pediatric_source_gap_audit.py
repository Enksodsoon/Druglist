#!/usr/bin/env python3
"""Prioritize pediatric source gaps without enabling unverified dose calculation."""
from __future__ import annotations

from engine_common import clean, now_iso, write_json
from clinical_audit_common import peds_items, stable_issue

TIER1 = ["paracetamol", "ibuprofen", "ors", "racecadotril", "probiotic", "cetirizine", "loratadine", "desloratadine", "saline", "lubricant", "clotrimazole", "ketoconazole"]
TIER2 = ["amoxicillin", "clavulan", "antibiotic", "ondansetron", "domperidone", "cough", "cold", "chlorpheniramine", "bromhexine", "dextromethorphan"]


def tier_for(text: str) -> int:
    low = text.lower()
    if any(term in low for term in TIER1):
        return 1
    if any(term in low for term in TIER2):
        return 2
    return 3


def audit() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in peds_items():
        text = " ".join(clean(item.get(k)) for k in ["display_name", "generic_key", "form", "route"]).lower()
        missing = []
        if not item.get("source_ids"):
            missing.append("pediatric source")
        if not clean(item.get("concentration")):
            missing.append("concentration")
        if not clean(item.get("age_bw_rule")):
            missing.append("age/BW rule")
        if not clean(item.get("max_dose")):
            missing.append("max dose when relevant")
        if not clean(item.get("dose_basis")):
            missing.append("dose basis")
        status = "blocked" if missing else "manual_review_required"
        rows.append(
            {
                "priority_id": stable_issue("PEDS_GAP", item.get("product_id"), item.get("generic_key")),
                "tier": tier_for(text),
                "product_id": item.get("product_id"),
                "display_name": item.get("display_name"),
                "generic_key": item.get("generic_key"),
                "route": item.get("route"),
                "form": item.get("form"),
                "concentration_present": bool(clean(item.get("concentration"))),
                "source_ids_present": bool(item.get("source_ids")),
                "missing_requirements": sorted(set(missing)),
                "pediatric_gate_status": status,
                "recommended_action": "needs_peds_source" if "pediatric source" in missing else "manual_review_required",
                "can_show_catalog": True,
                "can_calculate_dose": False,
            }
        )
    return sorted(rows, key=lambda row: (row["tier"], row["product_id"] or ""))


def main() -> int:
    rows = audit()
    write_json(
        "data/pediatric/pediatric_source_gap_priority.json",
        {"meta": {"generated_at": now_iso(), "item_count": len(rows), "tier1_count": sum(1 for r in rows if r["tier"] == 1)}, "items": rows},
    )
    lines = [
        "# Pediatric Source Gap Audit Report",
        "",
        f"Generated: {now_iso()}",
        "",
        f"- Pediatric candidates: {len(rows)}",
        f"- Tier 1 source priorities: {sum(1 for r in rows if r['tier'] == 1)}",
        f"- Dose calculations enabled by this audit: 0",
        "",
        "Pediatric products remain visible as catalog/review items, but calculated dosing stays blocked until source, concentration, age/BW rule, dose basis, frequency, and max dose requirements are satisfied.",
    ]
    for row in rows[:20]:
        lines.append(f"- Tier {row['tier']} `{row['product_id']}` {row['display_name']}: {', '.join(row['missing_requirements'])}")
    open("reports/pediatric_source_gap_audit_report.md", "w", encoding="utf-8").write("\n".join(lines).rstrip() + "\n")
    print(f"pediatric_source_gap_audit: items={len(rows)} tier1={sum(1 for r in rows if r['tier']==1)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
