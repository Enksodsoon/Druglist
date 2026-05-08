#!/usr/bin/env python3
"""Summarize the exported medical refresh workbook CSV mirrors."""

from __future__ import annotations

from collections import Counter

from medical_refresh_common import CSV_DIR, high_risk_rows, read_csv_sheet, write_report

SHEETS = [
    "1_Product_Master_Export",
    "2_Regimen_Master_Export",
    "3_Complaint_Disease_Map",
    "4_Top_50_Defaults",
    "5_Clinic_Defaults",
    "6_Pediatric_Dosing",
    "7_Antibiotic_Rows",
    "8_Source_Evidence_Queue",
    "9_Clinical_QC",
    "10_Import_Diff_Template",
    "11_OPD_Fast_Index_Template",
    "12_Drug_Short_Lookup_Template",
]


def main() -> int:
    lines: list[str] = [f"- CSV source: `{CSV_DIR}`", ""]
    high = high_risk_rows()
    for sheet in SHEETS:
        rows = read_csv_sheet(sheet)
        columns = list(rows[0].keys()) if rows else []
        id_cols = [col for col in columns if col.endswith("_id") or col in {"product_id", "regimen_id", "disease_key", "complaint_key"}]
        missing = {col: sum(1 for row in rows if not row.get(col)) for col in id_cols}
        duplicate = {
            col: sum(1 for _value, count in Counter(row.get(col) for row in rows if row.get(col)).items() if count > 1)
            for col in id_cols
        }
        no_source = sum(1 for row in rows if "source_status" in row and row.get("source_status") != "source_verified")
        blocked = sum(
            1
            for row in rows
            if row.get("clinical_readiness") in {"blocked", "manual_review_required"}
            or "manual" in str(row.get("review_status", "")).lower()
            or "source_gap" in str(row.get("source_status", "")).lower()
        )
        lines.extend(
            [
                f"## {sheet}",
                "",
                f"- Row count: {len(rows)}",
                f"- Columns: {', '.join(columns) if columns else 'none'}",
                f"- Missing IDs: {missing or {}}",
                f"- Duplicate IDs: {duplicate or {}}",
                f"- Rows without verified source: {no_source}",
                f"- Blocked/manual/source-gap rows: {blocked}",
                "",
            ]
        )
    lines.extend(
        [
            "## High-Risk Row Samples",
            "",
            "| regimen_id | disease_key | product_id | drug_name | readiness | source |",
            "|---|---|---|---|---|---|",
        ]
    )
    for row in high["high"][:20]:
        lines.append(
            f"| {row.get('regimen_id','')} | {row.get('disease_key','')} | {row.get('product_id','')} | {row.get('drug_name','')[:80]} | {row.get('clinical_readiness','')} | {row.get('source_status','')} |"
        )
    write_report("reports/medical_refresh_workbook_intake_report.md", "Medical Refresh Workbook Intake Report", lines)
    print("medical_refresh_workbook_intake: wrote reports/medical_refresh_workbook_intake_report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
