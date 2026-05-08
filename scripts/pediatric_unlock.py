#!/usr/bin/env python3
"""Classify all pediatric rows into explicit unlock statuses."""

from __future__ import annotations

from medical_refresh_common import read_json, write_json, write_report


def main() -> int:
    parsed = read_json("data/source_refresh/pediatric_dose_parse.json", {"items": []}).get("items", [])
    out = []
    verified = 0
    for item in parsed:
        status = "ready_source_verified" if item.get("dose_parse_status") == "complete" else "blocked_peds_missing_required_fields"
        if status == "ready_source_verified":
            verified += 1
        out.append({**item, "pediatric_verified": status == "ready_source_verified", "final_status": status, "exact_next_action": "safe to calculate dose" if status == "ready_source_verified" else "add accepted pediatric source, concentration, age/BW, dose basis, and max dose"})
    write_json("data/source_refresh/pediatric_unlock_status.json", {"items": out})
    write_report("reports/source_refresh/pediatric_unlock_report.md", "Pediatric Unlock Report", [f"- Pediatric rows processed: {len(out)}", f"- Pediatric verified rows: {verified}", f"- Pediatric blocked rows: {len(out)-verified}"])
    print(f"pediatric_unlock: processed={len(out)} verified={verified}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
