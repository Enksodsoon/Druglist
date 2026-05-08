#!/usr/bin/env python3
"""Validate source-refreshed workbook CSV outputs before import."""

from __future__ import annotations

import csv
from pathlib import Path

from medical_refresh_common import EXPORT_DIR, write_report

CSV_DIR = EXPORT_DIR / "source_refresh_csv"


def rows(name: str) -> list[dict[str, str]]:
    path = CSV_DIR / f"{name}.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    errors: list[str] = []
    regimen = rows("2_Regimen_Master_Export")
    pediatric = rows("6_Pediatric_Dosing")
    antibiotic = rows("7_Antibiotic_Rows")
    if not regimen:
        errors.append("missing_refreshed_regimen_rows")
    for row in regimen:
        refreshed = row.get("clinical_readiness_refreshed") or row.get("clinical_readiness")
        has_source = bool(row.get("source_ids") or row.get("evidence_claim_ids"))
        if refreshed == "ready" and not has_source:
            errors.append(f"ready_row_without_source:{row.get('regimen_id')}:{row.get('product_id')}")
        if refreshed in {"blocked", "manual_review_required"} and str(row.get("fast_mode_allowed")).lower() == "true":
            errors.append(f"blocked_row_fast_mode_allowed:{row.get('regimen_id')}:{row.get('product_id')}")
        if row.get("source_status") == "source_gap" and refreshed == "ready":
            errors.append(f"source_gap_ready:{row.get('regimen_id')}:{row.get('product_id')}")
    for row in pediatric:
        if row.get("clinical_readiness_refreshed") == "ready":
            missing = [k for k in ["source_ids", "concentration", "age_bw_rule", "max_dose"] if not row.get(k)]
            if missing:
                errors.append(f"pediatric_ready_missing:{row.get('product_id')}:{','.join(missing)}")
    for row in antibiotic:
        if row.get("clinical_readiness_refreshed") == "ready" and not row.get("antibiotic_criteria_verified"):
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
