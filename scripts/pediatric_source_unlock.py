#!/usr/bin/env python3
"""Report pediatric rows that can/cannot be unlocked from current sources."""

from __future__ import annotations

from medical_refresh_common import read_csv_sheet, write_json, write_report


def main() -> int:
    rows = read_csv_sheet("6_Pediatric_Dosing")
    tasks = []
    verified = 0
    for row in rows:
        missing = []
        if not row.get("source_ids"):
            missing.append("accepted pediatric source")
        if not row.get("age_bw_rule"):
            missing.append("age/BW rule")
        if not row.get("dose_basis"):
            missing.append("dose basis")
        if not row.get("max_dose"):
            missing.append("max dose when relevant")
        if "requires_review" in row.get("concentration", "") or "manual_review" in row.get("concentration", ""):
            missing.append("verified product concentration")
        if missing:
            tasks.append(
                {
                    "product_id": row.get("product_id"),
                    "display_name": row.get("display_name"),
                    "missing_requirements": missing,
                    "next_action": "add accepted pediatric source and product concentration before calculation",
                }
            )
        else:
            verified += 1
    write_json("data/source_refresh/pediatric_missing_source_tasks.json", {"items": tasks})
    write_report(
        "reports/source_refresh/pediatric_source_unlock_report.md",
        "Pediatric Source Unlock Report",
        [
            f"- Pediatric rows checked: {len(rows)}",
            f"- Pediatric verified rows: {verified}",
            f"- Pediatric rows still missing source/gates: {len(tasks)}",
            "- Pediatric page behavior should show products and missing requirements, not calculate unsupported doses.",
        ],
    )
    print(f"pediatric_source_unlock: verified={verified} missing={len(tasks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
