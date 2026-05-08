#!/usr/bin/env python3
"""Export citation index for source-backed claims."""

from __future__ import annotations

from export_refresh_workbook import union_columns, write_xlsx
from medical_refresh_common import EXPORT_DIR, read_json, write_csv, write_report


def main() -> int:
    claims = read_json("data/source_refresh/evidence_claims.json", {"claims": []}).get("claims", [])
    rows = []
    for claim in claims:
        rows.append(
            {
                "source_id": claim.get("source_id", ""),
                "source_title": claim.get("source_title", ""),
                "organization": claim.get("organization", ""),
                "year_version": "",
                "source_url_local_file": claim.get("source_url") or claim.get("local_file") or "",
                "access_date": "",
                "disease_key": claim.get("disease_key", ""),
                "regimen_id": claim.get("regimen_id", ""),
                "product_id": claim.get("product_id", ""),
                "generic_name": claim.get("generic_name", ""),
                "claim_type": claim.get("claim_type", ""),
                "short_snippet": claim.get("short_snippet", ""),
                "page_or_section": claim.get("page_or_section", ""),
                "evidence_confidence": claim.get("evidence_confidence", ""),
                "row_status": claim.get("status", ""),
                "used_for_ready": "yes" if claim.get("status") == "auto_verified" and not claim.get("missing_required_fields") else "no",
            }
        )
    columns = union_columns(rows, [
        "source_id",
        "source_title",
        "organization",
        "year_version",
        "source_url_local_file",
        "access_date",
        "disease_key",
        "regimen_id",
        "product_id",
        "generic_name",
        "claim_type",
        "short_snippet",
        "page_or_section",
        "evidence_confidence",
        "row_status",
        "used_for_ready",
    ])
    write_csv(EXPORT_DIR / "source_citations.csv", rows, columns)
    # Reuse the minimal XLSX writer by temporarily emitting a one-sheet workbook.
    base = EXPORT_DIR / "Druglist_Data_Refresh_Master.xlsx"
    original = base.read_bytes() if base.exists() else None
    write_xlsx({"Source_Citations": (rows, columns)})
    base.replace(EXPORT_DIR / "Druglist_Source_Citations.xlsx")
    if original is not None:
        base.write_bytes(original)
    write_report(
        "reports/source_refresh/source_citation_report.md",
        "Source Citation Report",
        [
            f"- Citation rows: {len(rows)}",
            f"- Used for ready rows: {sum(1 for row in rows if row['used_for_ready'] == 'yes')}",
            "- Any disease/regimen without a ready citation cannot be marked ready.",
        ],
    )
    print(f"source_citation_export: citations={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
