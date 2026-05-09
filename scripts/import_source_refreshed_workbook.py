#!/usr/bin/env python3
"""Prepare a safe import diff from the source-refreshed workbook.

This pass is deliberately non-destructive: with no complete source-backed ready
claims, it writes an import report and does not modify runtime clinical data.
"""

from __future__ import annotations

import csv

from medical_refresh_common import EXPORT_DIR, write_json, write_report


def read_rows(name: str) -> list[dict[str, str]]:
    path = EXPORT_DIR / "source_refresh_csv" / f"{name}.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    regimen = read_rows("2_Regimen_Master_Export")
    importable = [
        row
        for row in regimen
        if row.get("clinical_readiness_refreshed") == "ready"
        and row.get("source_ids")
        and row.get("evidence_claim_ids")
        and row.get("final_verification_status") == "ready_source_verified"
    ]
    blocked_visible = [
        row
        for row in regimen
        if row.get("clinical_readiness_refreshed") in {"blocked", "manual_review_required", "usable_with_warning"}
    ]
    diff = {
        "import_mode": "dry_run_no_clinical_change",
        "importable_ready_rows": len(importable),
        "blocked_or_warning_rows_preserved": len(blocked_visible),
        "first_unlock_status_rows": sum(1 for row in regimen if row.get("final_verification_status")),
        "changes": [],
    }
    write_json("data/source_refresh/import_source_refreshed_diff.json", diff)
    write_report(
        "reports/source_refresh/import_source_refreshed_diff.md",
        "Import Source Refreshed Diff",
        [
            "- Import mode: dry-run / no runtime clinical data changed.",
            f"- Source-backed ready rows importable: {len(importable)}",
            f"- Blocked/warning/manual rows preserved: {len(blocked_visible)}",
            "- Import keeps blocked/manual/source-gap rows visible and imports status/citation metadata only in this pass.",
        ],
    )
    print(f"import_source_refreshed_workbook: importable_ready_rows={len(importable)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
