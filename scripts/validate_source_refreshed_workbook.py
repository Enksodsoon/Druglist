#!/usr/bin/env python3
"""Validate source-refreshed workbook CSV outputs before import."""

from __future__ import annotations

import csv

from medical_refresh_common import EXPORT_DIR, write_report

CSV_DIR = EXPORT_DIR / "source_refresh_csv"


def rows(name: str) -> list[dict[str, str]]:
    path = CSV_DIR / f"{name}.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def header_errors(name: str) -> list[str]:
    path = CSV_DIR / f"{name}.csv"
    if not path.exists():
        return [f"missing_csv:{name}"]
    with path.open(encoding="utf-8-sig", newline="") as handle:
        header = next(csv.reader(handle), [])
    duplicates = sorted({col for col in header if header.count(col) > 1})
    return [f"duplicate_refresh_columns:{name}:{col}" for col in duplicates]


def main() -> int:
    errors: list[str] = []
    for sheet in ["2_Regimen_Master_Export", "6_Pediatric_Dosing", "7_Antibiotic_Rows"]:
        errors.extend(header_errors(sheet))
    regimen = rows("2_Regimen_Master_Export")
    pediatric = rows("6_Pediatric_Dosing")
    antibiotic = rows("7_Antibiotic_Rows")
    if not regimen:
        errors.append("missing_refreshed_regimen_rows")
    valid_statuses = {
        "ready_source_verified",
        "usable_with_warning_source_partial",
        "label_only_catalog",
        "manual_review_required_with_exact_reason",
        "blocked_source_missing",
        "blocked_vague_source",
        "blocked_conflict",
        "blocked_peds_missing_required_fields",
        "blocked_antibiotic_missing_criteria",
        "blocked_safety_red_flag",
    }
    for row in regimen:
        refreshed = row.get("final_clinical_readiness") or row.get("clinical_readiness_refreshed") or row.get("clinical_readiness")
        final_status = row.get("final_verification_status", "")
        if final_status not in valid_statuses:
            errors.append(f"missing_or_invalid_final_status:{row.get('regimen_id')}:{row.get('product_id')}:{final_status}")
        if "pending" in final_status:
            errors.append(f"vague_pending_final_status:{row.get('regimen_id')}:{row.get('product_id')}")
        has_source = bool(row.get("source_ids") or row.get("evidence_claim_ids"))
        if final_status == "ready_source_verified" and not has_source:
            errors.append(f"ready_row_without_source:{row.get('regimen_id')}:{row.get('product_id')}")
        if final_status.startswith("blocked") and str(row.get("final_fast_mode_allowed")).lower() == "true":
            errors.append(f"blocked_row_fast_mode_allowed:{row.get('regimen_id')}:{row.get('product_id')}")
        if row.get("source_status") == "source_gap" and final_status == "ready_source_verified":
            errors.append(f"source_gap_ready:{row.get('regimen_id')}:{row.get('product_id')}")
        if final_status == "ready_source_verified" and not row.get("coverage_id"):
            errors.append(f"ready_without_coverage_id:{row.get('regimen_id')}:{row.get('product_id')}")
    for row in pediatric:
        if row.get("final_verification_status") == "ready_source_verified":
            missing = [k for k in ["source_ids", "concentration", "age_bw_rule", "max_dose"] if not row.get(k)]
            if missing:
                errors.append(f"pediatric_ready_missing:{row.get('product_id')}:{','.join(missing)}")
    for row in antibiotic:
        if row.get("final_verification_status") == "ready_source_verified" and not row.get("antibiotic_criteria_verified"):
            errors.append(f"antibiotic_ready_without_criteria:{row.get('regimen_id')}:{row.get('product_id')}")
    write_report(
        "reports/source_refresh/import_source_refreshed_report.md",
        "Import Source Refreshed Validation Report",
        [
            f"- Regimen rows checked: {len(regimen)}",
            f"- Pediatric rows checked: {len(pediatric)}",
            f"- Antibiotic rows checked: {len(antibiotic)}",
            f"- Errors: {len(errors)}",
            *(f"- {error}" for error in errors[:100]),
        ],
    )
    print(f"validate_source_refreshed_workbook: errors={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
