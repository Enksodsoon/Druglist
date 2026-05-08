#!/usr/bin/env python3
"""Create a source-refresh workbook copy with citation/readiness columns."""

from __future__ import annotations

import csv
from pathlib import Path

from export_refresh_workbook import SHEETS, union_columns, write_xlsx
from medical_refresh_common import EXPORT_DIR, read_csv_sheet, read_json, write_csv, write_report

OUT_CSV = EXPORT_DIR / "source_refresh_csv"
REFRESHED = EXPORT_DIR / "Druglist_Data_Refresh_Master_SOURCE_REFRESHED.xlsx"

REFRESH_COLUMNS = [
    "source_ids",
    "source_titles",
    "source_urls",
    "source_organizations",
    "source_years",
    "source_sections",
    "source_snippets_short",
    "evidence_claim_ids",
    "disease_strategy_verified",
    "drug_class_verified",
    "generic_verified",
    "product_label_verified",
    "product_match_verified",
    "dose_verified",
    "pediatric_verified",
    "antibiotic_criteria_verified",
    "no_antibiotic_verified",
    "red_flag_verified",
    "clinical_readiness_refreshed",
    "refresh_action",
    "refresh_reason",
    "remaining_source_gap",
    "next_action",
]


def refresh_row(row: dict[str, str]) -> dict[str, str]:
    out = dict(row)
    readiness = row.get("clinical_readiness") or row.get("dose_output_status") or ""
    source_status = row.get("source_status") or ""
    fast_allowed = str(row.get("fast_mode_allowed", "")).lower() == "true"
    has_source = source_status == "source_verified"
    for col in REFRESH_COLUMNS:
        out.setdefault(col, "")
    out["source_ids"] = ""
    out["clinical_readiness_refreshed"] = readiness if readiness else "manual_review_required"
    if not has_source:
        if fast_allowed:
            out["clinical_readiness_refreshed"] = "usable_with_warning"
            out["refresh_action"] = "keep_warning_source_gap"
        else:
            out["clinical_readiness_refreshed"] = "manual_review_required" if readiness != "blocked" else "blocked"
            out["refresh_action"] = "keep_blocked_or_manual_review"
        out["remaining_source_gap"] = "true"
        out["refresh_reason"] = row.get("blocked_reason") or row.get("missing_requirements") or "accepted source-backed evidence not available"
        out["next_action"] = row.get("next_action") or "add accepted source citation with snippet"
    return out


def main() -> int:
    claims = read_json("data/source_refresh/evidence_claims.json", {"claims": []}).get("claims", [])
    sheet_data = {}
    for sheet in SHEETS:
        rows = read_csv_sheet(sheet)
        refreshed = [refresh_row(row) if sheet in {"2_Regimen_Master_Export", "6_Pediatric_Dosing", "7_Antibiotic_Rows"} else dict(row) for row in rows]
        columns = union_columns(refreshed, list(rows[0].keys()) if rows else [])
        if sheet in {"2_Regimen_Master_Export", "6_Pediatric_Dosing", "7_Antibiotic_Rows"}:
            columns = union_columns(refreshed, columns + REFRESH_COLUMNS)
        sheet_data[sheet] = (refreshed, columns)
        write_csv(OUT_CSV / f"{sheet}.csv", refreshed, columns)
    old_workbook = EXPORT_DIR / "Druglist_Data_Refresh_Master.xlsx"
    original_bytes = old_workbook.read_bytes() if old_workbook.exists() else None
    write_xlsx(sheet_data)
    old_workbook.replace(REFRESHED)
    if original_bytes is not None:
        old_workbook.write_bytes(original_bytes)
    regimen_rows = sheet_data["2_Regimen_Master_Export"][0]
    ready_rows = sum(1 for row in regimen_rows if row.get("clinical_readiness_refreshed") == "ready")
    blocked_rows = sum(1 for row in regimen_rows if row.get("clinical_readiness_refreshed") in {"blocked", "manual_review_required"})
    write_report(
        "reports/source_refresh/workbook_source_refresh_report.md",
        "Workbook Source Refresh Report",
        [
            f"- Evidence claims available: {len(claims)}",
            f"- Ready rows after refresh: {ready_rows}",
            f"- Blocked/manual rows after refresh: {blocked_rows}",
            f"- Refreshed workbook: `{REFRESHED.relative_to(EXPORT_DIR.parent)}`",
            "- No clinical values were overwritten; source/refreshed columns were added conservatively.",
        ],
    )
    write_report(
        "reports/source_refresh/workbook_source_refresh_diff.md",
        "Workbook Source Refresh Diff",
        [
            "- Added source/citation/readiness refresh columns to regimen, pediatric, and antibiotic sheets.",
            "- No source-backed complete dose claims were available, so no row was promoted to ready.",
            "- Unsupported rows remain source_gap, manual_review_required, blocked, or usable_with_warning.",
        ],
    )
    print(f"refresh_workbook_with_evidence: refreshed={REFRESHED.relative_to(EXPORT_DIR.parent)} ready={ready_rows} blocked_manual={blocked_rows}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
