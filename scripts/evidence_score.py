#!/usr/bin/env python3
"""Score extracted evidence claims with strict source and safety gates."""
from __future__ import annotations

from typing import Any

from engine_common import clean, now_iso, read_json, write_json
from evidence_common import (
    ANTIBIOTIC_REQUIRED_FIELDS,
    PEDS_REQUIRED_FIELDS,
    REPORT_DIR,
    has_source_location,
    source_authority_map,
    source_is_accepted,
)


def required_missing(claim: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    claim_type = clean(claim.get("claim_type"))
    structured = claim.get("structured_fields") or {}
    if not clean(claim.get("source_id")):
        missing.append("source_id")
    if not has_source_location(claim):
        missing.append("source_location")
    if clean(claim.get("source_id")) and not source_is_accepted(clean(claim.get("source_id"))):
        missing.append("accepted_source_review")
    if claim_type == "peds dose":
        for field in PEDS_REQUIRED_FIELDS - {"source_id", "source_location"}:
            if not structured.get(field):
                missing.append(field)
    if claim_type == "antibiotic criteria":
        for field in ANTIBIOTIC_REQUIRED_FIELDS - {"source_id", "source_location"}:
            if not structured.get(field) and not clean(claim.get(field)):
                missing.append(field)
    return sorted(set(missing))


def score_claim(claim: dict[str, Any]) -> dict[str, Any]:
    authority = source_authority_map().get(clean(claim.get("source_id")), 9)
    missing = required_missing(claim)
    base = max(0.25, 1.0 - (authority * 0.07))
    if clean(claim.get("generic_name")):
        base += 0.05
    if clean(claim.get("disease_key")):
        base += 0.05
    if clean(claim.get("extraction_quality")) == "keyword_candidate":
        base -= 0.18
    if missing:
        base -= min(0.35, len(missing) * 0.07)
    score = round(max(0.0, min(1.0, base)), 3)
    if missing and any(field in missing for field in ["source_id", "source_location", "accepted_source_review"]):
        status = "blocked_missing_required_safety_field"
    elif clean(claim.get("claim_type")) in {"peds dose", "antibiotic criteria"} and missing:
        status = "blocked_missing_required_safety_field"
    elif score >= 0.85:
        status = "auto_verified"
    elif score >= 0.60:
        status = "human_review_optional"
    else:
        status = "blocked_low_confidence"
    return {
        **claim,
        "evidence_score": score,
        "evidence_confidence": "high" if score >= 0.85 else "medium" if score >= 0.60 else "low",
        "evidence_status": status,
        "evidence_required_fields_missing": missing,
        "auto_resolution_status": status,
    }


def score() -> dict[str, Any]:
    claims = read_json("data/evidence/evidence_claims.json", {"claims": []}).get("claims", [])
    scored = [score_claim(claim) for claim in claims]
    auto_verified = [claim for claim in scored if claim["evidence_status"] == "auto_verified"]
    low_confidence = [claim for claim in scored if claim["evidence_status"] in {"blocked_low_confidence", "blocked_missing_required_safety_field"}]
    summary = {
        "generated_at": now_iso(),
        "claim_count": len(scored),
        "auto_verified_count": len(auto_verified),
        "human_review_optional_count": sum(1 for claim in scored if claim["evidence_status"] == "human_review_optional"),
        "blocked_low_confidence_count": sum(1 for claim in scored if claim["evidence_status"] == "blocked_low_confidence"),
        "blocked_missing_required_safety_field_count": sum(1 for claim in scored if claim["evidence_status"] == "blocked_missing_required_safety_field"),
        "conflict_count": 0,
    }
    write_json("data/evidence/evidence_scores.json", {"meta": summary, "claims": scored})
    write_json("data/evidence/auto_verified_claims.json", {"meta": summary, "claims": auto_verified})
    write_json("data/evidence/unresolved_low_confidence_gaps.json", {"meta": summary, "claims": low_confidence})
    (REPORT_DIR / "evidence_score_report.md").write_text(
        "\n".join(
            [
                "# Evidence Score Report",
                "",
                f"Generated: {summary['generated_at']}",
                "",
                f"- Claims scored: {summary['claim_count']}",
                f"- Auto-verified claims: {summary['auto_verified_count']}",
                f"- Human-review optional claims: {summary['human_review_optional_count']}",
                f"- Blocked low confidence: {summary['blocked_low_confidence_count']}",
                f"- Blocked missing required safety field: {summary['blocked_missing_required_safety_field_count']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    summary = score()
    print(f"evidence_score: auto_verified={summary['auto_verified_count']} blocked_low_confidence={summary['blocked_low_confidence_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
