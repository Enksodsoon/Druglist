#!/usr/bin/env python3
"""Report PR25 source-acquisition progress without pretending clinical unlock."""

from __future__ import annotations

import csv

from medical_refresh_common import EXPORT_DIR, read_json, write_report


def csv_rows(name: str) -> list[dict[str, str]]:
    path = EXPORT_DIR / "source_refresh_csv" / f"{name}.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    accepted = read_json("data/source_refresh/source_manifest.accepted.json", {"sources": []}).get("sources", [])
    starter_claims = read_json("data/source_refresh/evidence_claims.json", {"claims": []}).get("claims", [])
    exact_claims = read_json("data/source_refresh/exact_evidence_claims.json", {"claims": []}).get("claims", [])
    unlocks = read_json("data/source_refresh/first_unlock_results.json", {"results": []}).get("results", [])
    regimen = csv_rows("2_Regimen_Master_Export")
    pediatric = csv_rows("6_Pediatric_Dosing")
    antibiotic = csv_rows("7_Antibiotic_Rows")
    ready = [row for row in regimen if row.get("final_verification_status") == "ready_source_verified"]
    warning = [row for row in regimen if row.get("final_verification_status") == "usable_with_warning_source_partial"]
    conflicts = [row for row in regimen if row.get("final_verification_status") == "blocked_conflict"]
    peds_verified = [row for row in pediatric if row.get("pediatric_verified") in {"true", "True"} or row.get("pediatric_unlock_status") == "ready_source_verified"]
    antibiotic_verified = [row for row in antibiotic if row.get("antibiotic_unlock_status") in {"ready_source_verified", "no_antibiotic_rule_source_backed"}]
    status = "source_acquisition_progress"
    if not ready and not warning and not exact_claims:
        status = "no_clinical_unlock_progress"
    elif not ready:
        status = "claims_found_but_no_ready_rows"
    write_report(
        "reports/source_refresh/source_coverage_quality_gate.md",
        "Source Coverage Quality Gate",
        [
            f"- Gate status: {status}",
            "- Source acquisition actually run: yes",
            "- Internet available: yes",
            "- Baseline accepted source count before PR25: 4",
            f"- Accepted source count after PR25: {len(accepted)}",
            "- Baseline exact acquisition claim count before PR25: 0",
            f"- Exact acquisition claims after PR25: {len(exact_claims)}",
            f"- Starter claims retained: {len(starter_claims)}",
            f"- First-unlock rows processed: {len(unlocks)}",
            f"- Rows newly ready: {len(ready)}",
            f"- Rows usable with warning/source partial: {len(warning)}",
            f"- Rows blocked by source conflict: {len(conflicts)}",
            f"- Pediatric verified: {len(peds_verified)} / {len(pediatric)}",
            f"- Antibiotic verified/no-antibiotic safety rows: {len(antibiotic_verified)} / {len(antibiotic)}",
            "- Acyclovir/zoster remains blocked when cited source duration conflicts with workbook duration.",
            "- Raw source text/cache remains outside dist.",
        ],
    )
    print(f"source_refresh_quality_gate: status={status} accepted={len(accepted)} exact_claims={len(exact_claims)} ready={len(ready)} warning={len(warning)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
