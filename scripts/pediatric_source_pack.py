#!/usr/bin/env python3
"""Build pediatric-specific source pack rows from the coverage matrix."""

from __future__ import annotations

from export_refresh_workbook import write_xlsx, union_columns
from medical_refresh_common import EXPORT_DIR, read_json, write_csv, write_json, write_report


def main() -> int:
    records = read_json("data/source_refresh/refresh_coverage_matrix.json", {"records": []}).get("records", [])
    peds = [r for r in records if r.get("sheet_name") == "6_Pediatric_Dosing" or r.get("pediatric_flag")]
    rows = [
        {
            "coverage_id": r["coverage_id"],
            "product_id": r.get("product_id", ""),
            "generic_name": r.get("generic_name", ""),
            "drug_name": r.get("drug_name", ""),
            "evidence_needed": r.get("exact_evidence_needed", []),
            "source_targets": ["Thai Pediatric Society", "Thai MOPH", "WHO EMLc", "CDC/AAP/NICE if accessible", "user-provided textbook"],
            "final_status": r.get("final_status"),
            "next_action": r.get("next_action"),
        }
        for r in peds
    ]
    columns = union_columns(rows)
    write_json("data/source_refresh/pediatric_source_pack.json", {"items": rows})
    write_csv(EXPORT_DIR / "Pediatric_Source_Pack.csv", rows, columns)
    original = (EXPORT_DIR / "Druglist_Data_Refresh_Master.xlsx").read_bytes()
    write_xlsx({"Pediatric_Source_Pack": (rows, columns)})
    (EXPORT_DIR / "Druglist_Data_Refresh_Master.xlsx").replace(EXPORT_DIR / "Pediatric_Verification_Matrix.xlsx")
    (EXPORT_DIR / "Druglist_Data_Refresh_Master.xlsx").write_bytes(original)
    write_report("reports/source_refresh/pediatric_source_pack_report.md", "Pediatric Source Pack Report", [f"- Pediatric rows processed: {len(rows)}", "- No pediatric row is considered verified without full source/concentration/age-BW/max-dose gates."])
    print(f"pediatric_source_pack: rows={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
