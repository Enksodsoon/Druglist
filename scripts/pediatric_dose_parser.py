#!/usr/bin/env python3
"""Parse pediatric row completeness without calculating unsupported doses."""

from __future__ import annotations

from medical_refresh_common import read_csv_sheet, write_json, write_report


def main() -> int:
    rows = read_csv_sheet("6_Pediatric_Dosing")
    parsed = []
    for row in rows:
        concentration = row.get("concentration", "")
        missing = []
        if not row.get("source_ids"):
            missing.append("accepted pediatric source")
        if not row.get("age_bw_rule"):
            missing.append("age/BW rule")
        if not row.get("dose_basis"):
            missing.append("dose basis")
        if not row.get("max_dose"):
            missing.append("max dose")
        if "manual_review" in concentration or "requires_review" in concentration or not concentration:
            missing.append("verified concentration")
        parsed.append(
            {
                "product_id": row.get("product_id"),
                "display_name": row.get("display_name"),
                "route": row.get("route"),
                "form": row.get("form"),
                "concentration_status": "needs_review" if "manual_review" in concentration or "requires_review" in concentration else "present" if concentration else "missing",
                "missing_fields": missing,
                "dose_parse_status": "complete" if not missing else "blocked_incomplete",
                "final_status": "ready_source_verified" if not missing else "blocked_peds_missing_required_fields",
            }
        )
    write_json("data/source_refresh/pediatric_dose_parse.json", {"items": parsed})
    write_report("reports/source_refresh/pediatric_dose_parser_report.md", "Pediatric Dose Parser Report", [f"- Pediatric rows parsed: {len(parsed)}", f"- Complete rows: {sum(1 for p in parsed if p['dose_parse_status'] == 'complete')}", f"- Blocked incomplete rows: {sum(1 for p in parsed if p['dose_parse_status'] != 'complete')}"])
    print(f"pediatric_dose_parser: rows={len(parsed)} complete={sum(1 for p in parsed if p['dose_parse_status'] == 'complete')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
