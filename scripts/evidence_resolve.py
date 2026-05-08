#!/usr/bin/env python3
"""Resolve source gaps only from auto-verified evidence claims."""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from engine_common import clean, now_iso, read_json, write_json
from evidence_common import REPORT_DIR, source_is_accepted, source_location


def resolve() -> dict[str, Any]:
    verified = read_json("data/evidence/auto_verified_claims.json", {"claims": []}).get("claims", [])
    low = read_json("data/evidence/unresolved_low_confidence_gaps.json", {"claims": []}).get("claims", [])
    candidates = read_json("data/evidence/evidence_candidates.json", {"candidates": []}).get("candidates", [])
    by_gap: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for claim in verified:
        if not source_is_accepted(clean(claim.get("source_id"))):
            continue
        if not (clean(claim.get("section")) or clean(claim.get("page")) or source_location(claim)):
            continue
        by_gap[clean(claim.get("gap_id"))].append(claim)
    resolved = []
    for gap_id, claims in by_gap.items():
        source_ids = sorted({clean(claim.get("source_id")) for claim in claims if clean(claim.get("source_id"))})
        if not source_ids:
            continue
        resolved.append(
            {
                "gap_id": gap_id,
                "resolution_status": "auto_resolved",
                "source_ids": source_ids,
                "claim_ids": [claim["claim_id"] for claim in claims],
                "notes": "Resolved only from auto-verified evidence claims.",
            }
        )
    pending_collection = [c for c in candidates if c.get("status") == "pending_extraction"]
    status_counts = Counter(claim.get("evidence_status") for claim in verified + low)
    summary = {
        "generated_at": now_iso(),
        "auto_resolved_gap_count": len(resolved),
        "pending_source_collection_count": len(pending_collection),
        "blocked_low_confidence_count": status_counts.get("blocked_low_confidence", 0),
        "blocked_missing_required_safety_field_count": status_counts.get("blocked_missing_required_safety_field", 0),
        "blocked_conflict_count": 0,
        "auto_verified_claim_count": len(verified),
        "peds_auto_verified_count": sum(1 for claim in verified if claim.get("claim_type") == "peds dose"),
        "antibiotic_auto_verified_count": sum(1 for claim in verified if claim.get("claim_type") == "antibiotic criteria"),
        "evidence_status": "pending_source_collection" if not verified else "auto_resolved",
    }
    write_json("data/evidence/auto_resolved_source_gaps.json", {"meta": summary, "items": resolved})
    write_json("data/evidence/evidence_runtime_summary.json", summary)
    (REPORT_DIR / "auto_resolution_report.md").write_text(
        "\n".join(
            [
                "# Auto Resolution Report",
                "",
                f"Generated: {summary['generated_at']}",
                "",
                f"- Auto-resolved source gaps: {summary['auto_resolved_gap_count']}",
                f"- Pending source collection/extraction: {summary['pending_source_collection_count']}",
                f"- Blocked low confidence: {summary['blocked_low_confidence_count']}",
                f"- Blocked conflicts: {summary['blocked_conflict_count']}",
                f"- Pediatric auto-verified claims: {summary['peds_auto_verified_count']}",
                f"- Antibiotic auto-verified claims: {summary['antibiotic_auto_verified_count']}",
                "",
                "No guideline map is updated unless a claim is auto-verified with source identity and source location.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    summary = resolve()
    print(f"evidence_resolve: auto_resolved={summary['auto_resolved_gap_count']} pending={summary['pending_source_collection_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
