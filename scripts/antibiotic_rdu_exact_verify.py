#!/usr/bin/env python3
"""Exact antibiotic/RDU verification matrix."""

from __future__ import annotations

from export_refresh_workbook import write_xlsx, union_columns
from medical_refresh_common import EXPORT_DIR, lower_blob, read_csv_sheet, write_csv, write_json, write_report


def main() -> int:
    rows = []
    source_rows = read_csv_sheet("7_Antibiotic_Rows")
    for row in source_rows:
        blob = lower_blob(row)
        no_antibiotic_context = any(token in blob for token in ["viral", "simple diarrhea", "allergic rhinitis", "dry eye", "allergic conjunctivitis", "acute bronchitis"])
        status = "blocked_antibiotic_missing_criteria"
        rows.append(
            {
                "regimen_id": row.get("regimen_id"),
                "disease_key": row.get("disease_key"),
                "product_id": row.get("product_id"),
                "drug_name": row.get("drug_name"),
                "issue_type": row.get("issue_type", ""),
                "no_antibiotic_rule_candidate": no_antibiotic_context,
                "final_status": status,
                "exact_evidence_missing": ["bacterial criteria/no-antibiotic rule", "drug choice", "dose", "frequency", "duration", "allergy alternative if used"],
                "exact_next_action": "map accepted RDU/AWaRe/disease guideline snippet to this row before RX NOW",
            }
        )
    columns = union_columns(rows)
    write_json("data/source_refresh/antibiotic_exact_verification.json", {"items": rows})
    write_csv(EXPORT_DIR / "Antibiotic_Verification_Matrix.csv", rows, columns)
    original = (EXPORT_DIR / "Druglist_Data_Refresh_Master.xlsx").read_bytes()
    write_xlsx({"Antibiotic_Verification": (rows, columns)})
    (EXPORT_DIR / "Druglist_Data_Refresh_Master.xlsx").replace(EXPORT_DIR / "Antibiotic_Verification_Matrix.xlsx")
    (EXPORT_DIR / "Druglist_Data_Refresh_Master.xlsx").write_bytes(original)
    write_report("reports/source_refresh/antibiotic_exact_verification_report.md", "Antibiotic Exact Verification Report", [f"- Antibiotic rows/issues processed: {len(rows)}", "- Antibiotic RX NOW remains blocked unless disease criteria, dose, and duration are source-backed."])
    print(f"antibiotic_rdu_exact_verify: rows={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
