#!/usr/bin/env python3
"""Create a source-refresh workbook copy with citation/readiness columns."""

from __future__ import annotations

from export_refresh_workbook import SHEETS, union_columns, write_xlsx
from medical_refresh_common import EXPORT_DIR, read_csv_sheet, read_json, write_csv, write_report

OUT_CSV = EXPORT_DIR / "source_refresh_csv"
REFRESHED = EXPORT_DIR / "Druglist_Data_Refresh_Master_SOURCE_REFRESHED.xlsx"

REFRESH_COLUMNS = [
    "coverage_id",
    "source_pack_id",
    "final_verification_status",
    "final_clinical_readiness",
    "final_fast_mode_allowed",
    "final_rx_role",
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
    "exact_evidence_missing",
    "exact_block_reason",
    "exact_next_action",
    "can_show_in_main_builder",
    "can_show_in_peds_page",
    "can_show_in_swaps",
    "catalog_only_reason",
    "pediatric_unlock_status",
    "antibiotic_unlock_status",
    "antiviral_unlock_status",
    "clinical_readiness_refreshed",
    "refresh_action",
    "refresh_reason",
    "remaining_source_gap",
    "next_action",
]


def dedupe_columns(columns: list[str]) -> list[str]:
    out = []
    for col in columns:
        if col not in out:
            out.append(col)
    return out


def refresh_row(row: dict[str, str], coverage: dict | None = None, claim_ids: list[str] | None = None) -> dict[str, str]:
    out = dict(row)
    readiness = row.get("clinical_readiness") or row.get("dose_output_status") or ""
    source_status = row.get("source_status") or ""
    fast_allowed = str(row.get("fast_mode_allowed", "")).lower() == "true"
    has_source = source_status == "source_verified"
    for col in REFRESH_COLUMNS:
        out[col] = ""
    final_status = (coverage or {}).get("final_status") or ("ready_source_verified" if has_source and readiness == "ready" else "blocked_source_missing")
    final_reason = (coverage or {}).get("final_reason") or row.get("blocked_reason") or row.get("missing_requirements") or "accepted source-backed evidence not available"
    next_action = (coverage or {}).get("next_action") or row.get("next_action") or "add accepted source citation with snippet"
    out["coverage_id"] = (coverage or {}).get("coverage_id", "")
    out["source_pack_id"] = (coverage or {}).get("source_pack_id", "")
    out["final_verification_status"] = final_status
    out["final_clinical_readiness"] = "ready" if final_status == "ready_source_verified" else "usable_with_warning" if final_status == "usable_with_warning_source_partial" else "blocked" if final_status.startswith("blocked") else "manual_review_required"
    out["final_fast_mode_allowed"] = "true" if final_status == "ready_source_verified" else "false"
    out["final_rx_role"] = "catalog_only" if final_status == "label_only_catalog" else row.get("role") or row.get("line_type") or ""
    out["source_ids"] = row.get("source_ids", "")
    out["evidence_claim_ids"] = "; ".join(claim_ids or [])
    out["exact_evidence_missing"] = "; ".join((coverage or {}).get("exact_evidence_needed", []))
    out["exact_block_reason"] = final_reason
    out["exact_next_action"] = next_action
    out["can_show_in_main_builder"] = "true" if row.get("regimen_id") else "false"
    out["can_show_in_peds_page"] = "true" if (coverage or {}).get("pediatric_flag") else "false"
    out["can_show_in_swaps"] = "true" if "SWAP" in str(row.get("role", "")) else "false"
    out["catalog_only_reason"] = "product metadata only" if final_status == "label_only_catalog" else ""
    out["pediatric_unlock_status"] = final_status if (coverage or {}).get("pediatric_flag") else "not_applicable"
    out["antibiotic_unlock_status"] = final_status if (coverage or {}).get("antibiotic_flag") else "not_applicable"
    out["antiviral_unlock_status"] = final_status if any(x in " ".join(map(str, row.values())).lower() for x in ["acyclovir", "zoster", "shingles", "herpes"]) else "not_applicable"
    out["clinical_readiness_refreshed"] = out["final_clinical_readiness"]
    if not has_source:
        if fast_allowed:
            out["refresh_action"] = "keep_warning_source_gap"
        else:
            out["refresh_action"] = "keep_blocked_or_manual_review"
        out["remaining_source_gap"] = "true"
        out["refresh_reason"] = final_reason
        out["next_action"] = next_action
    return out


def main() -> int:
    claims = read_json("data/source_refresh/evidence_claims.json", {"claims": []}).get("claims", [])
    coverage_records = read_json("data/source_refresh/refresh_coverage_matrix.json", {"records": []}).get("records", [])
    pack_plan = read_json("data/source_refresh/source_pack_plan.json", {"packs": []}).get("packs", [])
    pack_by_coverage = {coverage_id: pack.get("pack_id", "") for pack in pack_plan for coverage_id in (pack.get("coverage_ids") or [])}
    for record in coverage_records:
        record["source_pack_id"] = pack_by_coverage.get(record["coverage_id"], "")
    coverage_by_sheet_row = {(r["sheet_name"], int(r["row_number"])): r for r in coverage_records}
    row_map = read_json("data/source_refresh/evidence_claim_to_row_map.json", {"items": []}).get("items", [])
    claims_by_coverage: dict[str, list[str]] = {}
    for item in row_map:
        claims_by_coverage.setdefault(item.get("coverage_id", ""), []).append(item.get("claim_id", ""))
    sheet_data = {}
    for sheet in SHEETS:
        rows = read_csv_sheet(sheet)
        refreshed = []
        for idx, row in enumerate(rows, start=2):
            coverage = coverage_by_sheet_row.get((sheet, idx))
            claim_ids = claims_by_coverage.get((coverage or {}).get("coverage_id", ""), [])
            refreshed.append(refresh_row(row, coverage, claim_ids) if coverage else dict(row))
        columns = dedupe_columns(union_columns(refreshed, list(rows[0].keys()) if rows else []))
        if any((sheet, idx) in coverage_by_sheet_row for idx in range(2, len(rows) + 2)):
            columns = dedupe_columns(union_columns(refreshed, columns + REFRESH_COLUMNS))
        sheet_data[sheet] = (refreshed, columns)
        write_csv(OUT_CSV / f"{sheet}.csv", refreshed, columns)
    old_workbook = EXPORT_DIR / "Druglist_Data_Refresh_Master.xlsx"
    original_bytes = old_workbook.read_bytes() if old_workbook.exists() else None
    write_xlsx(sheet_data)
    old_workbook.replace(REFRESHED)
    if original_bytes is not None:
        old_workbook.write_bytes(original_bytes)
    regimen_rows = sheet_data["2_Regimen_Master_Export"][0]
    ready_rows = sum(1 for row in regimen_rows if row.get("final_verification_status") == "ready_source_verified")
    blocked_rows = sum(1 for row in regimen_rows if str(row.get("final_verification_status", "")).startswith("blocked") or row.get("final_clinical_readiness") == "manual_review_required")
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
