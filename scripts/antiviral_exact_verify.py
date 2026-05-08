#!/usr/bin/env python3
"""Exact antiviral verification matrix for acyclovir/herpes/zoster rows."""

from __future__ import annotations

from export_refresh_workbook import write_xlsx, union_columns
from medical_refresh_common import EXPORT_DIR, lower_blob, read_csv_sheet, write_csv, write_json, write_report


def main() -> int:
    rows = []
    for row in read_csv_sheet("2_Regimen_Master_Export"):
        blob = lower_blob(row)
        if any(token in blob for token in ["acyclovir", "zoster", "shingles", "herpes", "varicella"]):
            exact_missing = ["disease-specific indication", "dose", "frequency", "duration", "timing window/red flags when applicable"]
            status = "blocked_source_missing"
            rows.append(
                {
                    "regimen_id": row.get("regimen_id"),
                    "disease_key": row.get("disease_key"),
                    "product_id": row.get("product_id"),
                    "drug_name": row.get("drug_name"),
                    "current_readiness": row.get("clinical_readiness"),
                    "final_status": status,
                    "exact_evidence_missing": exact_missing,
                    "exact_block_reason": "product availability or broad antiviral strategy does not verify exact disease-specific dose/frequency/duration",
                    "exact_next_action": "add accepted zoster/herpes source with exact dose, frequency, duration, timing window, route/form, and red flags",
                }
            )
    columns = union_columns(rows)
    write_json("data/source_refresh/antiviral_exact_verification.json", {"items": rows})
    write_csv(EXPORT_DIR / "Antiviral_Verification_Matrix.csv", rows, columns)
    original = (EXPORT_DIR / "Druglist_Data_Refresh_Master.xlsx").read_bytes()
    write_xlsx({"Antiviral_Verification": (rows, columns)})
    (EXPORT_DIR / "Druglist_Data_Refresh_Master.xlsx").replace(EXPORT_DIR / "Antiviral_Verification_Matrix.xlsx")
    (EXPORT_DIR / "Druglist_Data_Refresh_Master.xlsx").write_bytes(original)
    write_report("reports/source_refresh/antiviral_exact_verification_report.md", "Antiviral Exact Verification Report", [f"- Antiviral rows processed: {len(rows)}", "- Acyclovir/zoster remains blocked unless exact disease-specific dose/frequency/duration evidence is mapped."])
    print(f"antiviral_exact_verify: rows={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
