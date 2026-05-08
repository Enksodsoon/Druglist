#!/usr/bin/env python3
"""Extract conservative evidence candidates from cached source text."""
from __future__ import annotations

import re
from typing import Any

from engine_common import clean, norm_key, now_iso, read_json, stable_id, write_json
from evidence_common import CLAIM_TYPES, EVIDENCE_DIR, REPORT_DIR, ensure_evidence_dirs

KEYWORD_TO_CLAIM_TYPE = [
    ("contraindicat", "contraindication"),
    ("caution", "caution"),
    ("warning", "caution"),
    ("red flag", "red flags"),
    ("refer", "referral"),
    ("antibiotic", "antibiotic criteria"),
    ("bacterial", "antibiotic criteria"),
    ("viral", "no-antibiotic criteria"),
    ("dose", "adult dose"),
    ("mg/kg", "peds dose"),
    ("maximum", "max dose"),
    ("duration", "duration"),
    ("frequency", "frequency"),
    ("indication", "indication"),
]


def sentence_snippets(text: str) -> list[str]:
    pieces = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [clean(piece) for piece in pieces if len(clean(piece)) >= 40]


def claim_type_for(snippet: str) -> str:
    low = snippet.lower()
    for key, claim_type in KEYWORD_TO_CLAIM_TYPE:
        if key in low:
            return claim_type
    return "indication"


def terms_for_gap(gap: dict[str, Any]) -> list[str]:
    values = [gap.get("entity_id"), gap.get("generic_name"), gap.get("drug_class"), gap.get("disease_key")]
    terms = [norm_key(value) for value in values if clean(value)]
    return [term for term in terms if len(term) >= 3]


def build_claim(source: dict[str, Any], gap: dict[str, Any], snippet: str, idx: int) -> dict[str, Any]:
    claim_type = claim_type_for(snippet)
    source_id = clean(source.get("source_group_id") or source.get("source_id"))
    text_path = clean(source.get("text_cache_path"))
    return {
        "claim_id": stable_id("EVIDENCE_CLAIM", f"{source_id}_{gap.get('gap_id')}_{idx}"),
        "gap_id": clean(gap.get("gap_id")),
        "claim_type": claim_type if claim_type in CLAIM_TYPES else "indication",
        "claim_text": snippet,
        "source_id": source_id,
        "source_location": text_path,
        "file_reference": text_path,
        "section": "",
        "page": "",
        "snippet": snippet[:600],
        "generic_name": clean(gap.get("generic_name")),
        "disease_key": clean(gap.get("disease_key") or gap.get("entity_id")),
        "patient_group": "pediatric" if "peds" in norm_key(gap.get("entity_id")) or "child" in norm_key(gap.get("entity_id")) else "",
        "extraction_quality": "keyword_candidate",
        "structured_fields": {},
    }


def extract() -> dict[str, Any]:
    ensure_evidence_dirs()
    gaps = read_json("data/guidelines/source_gap_list.json", {"items": []}).get("items", [])
    manifest = read_json("data/evidence/source_cache_manifest.json", {"sources": []})
    sources = [source for source in manifest.get("sources", []) if clean(source.get("text_cache_path"))]
    claims: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for gap in gaps:
        terms = terms_for_gap(gap)
        matched = 0
        for source in sources:
            text_path = EVIDENCE_DIR / clean(source.get("text_cache_path"))
            if not text_path.exists():
                continue
            snippets = sentence_snippets(text_path.read_text(encoding="utf-8", errors="ignore"))
            for snippet in snippets:
                normalized = norm_key(snippet)
                if terms and not any(term in normalized for term in terms):
                    continue
                claims.append(build_claim(source, gap, snippet, matched))
                matched += 1
                if matched >= 5:
                    break
            if matched >= 5:
                break
        candidates.append(
            {
                "candidate_id": stable_id("EVIDENCE_CANDIDATE", gap.get("gap_id")),
                "gap_id": clean(gap.get("gap_id")),
                "entity_type": clean(gap.get("entity_type")),
                "entity_id": clean(gap.get("entity_id")),
                "candidate_claim_count": matched,
                "status": "pending_extraction" if matched == 0 else "candidate_extracted",
            }
        )
    summary = {
        "generated_at": now_iso(),
        "gap_count": len(gaps),
        "text_source_count": len(sources),
        "candidate_count": len(candidates),
        "claim_count": len(claims),
        "pending_extraction_count": sum(1 for c in candidates if c["status"] == "pending_extraction"),
    }
    write_json("data/evidence/evidence_candidates.json", {"meta": summary, "candidates": candidates})
    write_json("data/evidence/evidence_claims.json", {"meta": summary, "claims": claims})
    (REPORT_DIR / "evidence_extraction_report.md").write_text(
        "\n".join(
            [
                "# Evidence Extraction Report",
                "",
                f"Generated: {summary['generated_at']}",
                "",
                f"- Text sources: {summary['text_source_count']}",
                f"- Evidence claims: {summary['claim_count']}",
                f"- Pending extraction gaps: {summary['pending_extraction_count']}",
                "",
                "No source text means no verified claims.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    summary = extract()
    print(f"evidence_extract: claims={summary['claim_count']} pending_extraction={summary['pending_extraction_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
