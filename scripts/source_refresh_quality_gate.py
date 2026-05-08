#!/usr/bin/env python3
"""Write PR #24 gap analysis and source coverage quality gate."""

from __future__ import annotations

from collections import Counter
import csv

from medical_refresh_common import EXPORT_DIR, read_json, write_report


def read_source_refresh_csv(sheet: str) -> list[dict[str, str]]:
    path = EXPORT_DIR / "source_refresh_csv" / f"{sheet}.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    accepted = read_json("data/source_refresh/source_manifest.accepted.json", {"sources": []}).get("sources", [])
    claims = read_json("data/source_refresh/evidence_claims.json", {"claims": []}).get("claims", [])
    coverage = read_json("data/source_refresh/refresh_coverage_matrix.json", {"records": []}).get("records", [])
    refreshed = read_source_refresh_csv("2_Regimen_Master_Export")
    final_counts = Counter(r.get("final_status") for r in coverage)
    refreshed_counts = Counter(r.get("final_verification_status") for r in refreshed)
    peds = read_json("data/source_refresh/pediatric_unlock_status.json", {"items": []}).get("items", [])
    antibiotic = read_json("data/source_refresh/antibiotic_exact_verification.json", {"items": []}).get("items", [])
    ready = refreshed_counts.get("ready_source_verified", 0)
    used_for_ready = sum(1 for c in claims if c.get("status") == "auto_verified" and not c.get("missing_required_fields"))
    gap_lines = [
        f"- Accepted source count: {len(accepted)}",
        f"- Evidence claim count: {len(claims)}",
        f"- Used-for-ready claim count: {used_for_ready}",
        f"- Rows promoted ready: {ready}",
        f"- Rows still source-gated: {sum(1 for r in refreshed if r.get('remaining_source_gap') == 'true')}",
        f"- Pediatric verified count: {sum(1 for p in peds if p.get('pediatric_verified'))}",
        f"- Antibiotic verified count: {sum(1 for a in antibiotic if a.get('final_status') == 'ready_source_verified')}",
        "",
        "## Why PR #24 did not unlock rows",
        "",
        "- Source documents were accessible, but claims were broad or partial.",
        "- No row had complete row-specific dose/frequency/duration evidence.",
        "- Pediatric rows lacked complete source + concentration + age/BW + dose basis + max-dose gates.",
        "- Antibiotic rows lacked row-specific disease criteria plus dose/duration mapping.",
        "- Acyclovir/zoster had partial antiviral/timing evidence but not exact disease-specific dosing.",
        "",
        "## Final Status Counts From Coverage Matrix",
        *[f"- {k}: {v}" for k, v in sorted(final_counts.items())],
    ]
    write_report("reports/source_refresh/pr24_gap_analysis.md", "PR24 Gap Analysis", gap_lines)
    quality = [
        f"- Accepted sources: {len(accepted)}",
        f"- Coverage records: {len(coverage)}",
        f"- Ready rows: {ready}",
        f"- Pediatric rows processed: {len(peds)}",
        f"- Pediatric verified: {sum(1 for p in peds if p.get('pediatric_verified'))}",
        f"- Antibiotic rows processed: {len(antibiotic)}",
        f"- Antibiotic verified: {sum(1 for a in antibiotic if a.get('final_status') == 'ready_source_verified')}",
        "",
        "## Gate Status",
    ]
    if len(accepted) < 8:
        quality.append("- incomplete_source_pack: accepted source count below likely minimum for full clinical unlock")
    if not any(p.get("pediatric_verified") for p in peds):
        quality.append("- peds_not_unlocked: all pediatric rows have explicit final reasons but no verified pediatric dose rows")
    if not any(a.get("final_status") == "ready_source_verified" for a in antibiotic):
        quality.append("- antibiotics_not_unlocked: all antibiotic rows have explicit final reasons but no verified antibiotic RX rows")
    if ready == 0:
        quality.append("- not_clinically_unlocked_yet: pipeline is explicit and safe, but no rows promoted ready")
    write_report("reports/source_refresh/source_coverage_quality_gate.md", "Source Coverage Quality Gate", quality)
    print(f"source_refresh_quality_gate: coverage={len(coverage)} ready={ready}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
