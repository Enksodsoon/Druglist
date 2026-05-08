#!/usr/bin/env python3
"""Collect accessible public source text for proposed medical sources."""

from __future__ import annotations

import re
from pathlib import Path

from medical_refresh_common import (
    CACHE_DIR,
    TEXT_DIR,
    access_date,
    fetch_url,
    html_to_text,
    read_json,
    stable_id,
    text_window,
    write_json,
    write_report,
)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:80] or "source"


def main() -> int:
    candidates = read_json("data/source_refresh/source_url_candidates.json", {"candidates": []}).get("candidates", [])
    proposed = []
    accepted = []
    text_manifest = []
    collected = 0
    for candidate in candidates:
        if candidate.get("status") not in {"candidate_official", "candidate_needs_text_check", "candidate_product_label_only"}:
            continue
        url = candidate.get("candidate_url") or ""
        source_id = candidate.get("source_id_suggestion") or stable_id("source", url)
        ctype, body, error = fetch_url(url)
        cache_name = slug(source_id)
        raw_path = CACHE_DIR / f"{cache_name}.bin"
        text_path = TEXT_DIR / f"{cache_name}.txt"
        text = ""
        access_status = "source_unreachable"
        notes = error
        text_extracted = False
        if body:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            TEXT_DIR.mkdir(parents=True, exist_ok=True)
            raw_path.write_bytes(body)
            if "pdf" in ctype.lower() or url.lower().endswith(".pdf"):
                text = ""
                access_status = "needs_pdf_text_extraction"
                notes = "PDF downloaded but no PDF parser is bundled in this repo workflow; needs OCR/text extraction before claims."
            else:
                text = html_to_text(body)
                text_path.write_text(text, encoding="utf-8")
                text_extracted = len(text) > 200
                access_status = "extracted" if text_extracted else "needs_text_review"
                notes = "" if text_extracted else "HTML text too short or not relevant."
        row = {
            "source_id": source_id,
            "source_title": candidate.get("candidate_title") or "",
            "organization": candidate.get("organization") or "",
            "source_url": url,
            "local_file_reference": str(text_path.relative_to(TEXT_DIR.parent)) if text_extracted else "",
            "source_type": candidate.get("source_type") or "",
            "clinical_domain": candidate.get("clinical_domain") or candidate.get("clinical_question") or "",
            "disease_keys": [candidate.get("disease_key")] if candidate.get("disease_key") else [],
            "related_generics": [candidate.get("generic_name")] if candidate.get("generic_name") else [],
            "related_regimens": [candidate.get("regimen_id")] if candidate.get("regimen_id") else [],
            "year": candidate.get("year") or "source_version_unknown",
            "access_date": access_date(),
            "text_extracted": text_extracted,
            "review_status": "accepted" if text_extracted and text_window(text, ["acyclovir", "antiviral", "antibiotic", "essential medicines", "sore throat"]) else "proposed",
            "notes": notes,
        }
        proposed.append(row)
        if row["review_status"] == "accepted":
            accepted.append(row)
        text_manifest.append(
            {
                "source_id": source_id,
                "url": url,
                "content_type": ctype,
                "raw_cache_file": str(raw_path.relative_to(CACHE_DIR.parent)) if body else "",
                "text_file": str(text_path.relative_to(TEXT_DIR.parent)) if text_extracted else "",
                "text_extracted": text_extracted,
                "access_status": access_status,
                "notes": notes,
            }
        )
        if body:
            collected += 1
    write_json("data/source_refresh/source_manifest.proposed.json", {"sources": proposed})
    write_json("data/source_refresh/source_manifest.accepted.json", {"sources": accepted})
    write_json("data/source_refresh/source_text_manifest.json", {"sources": text_manifest})
    write_report(
        "reports/source_refresh/source_collection_report.md",
        "Source Collection Report",
        [
            f"- Candidate sources inspected: {len(candidates)}",
            f"- Sources downloaded/reached: {collected}",
            f"- Proposed sources: {len(proposed)}",
            f"- Accepted text-backed sources: {len(accepted)}",
            f"- PDF/unreadable sources needing OCR/parser: {sum(1 for x in text_manifest if x['access_status'] == 'needs_pdf_text_extraction')}",
            "- Raw source cache is ignored by git and not copied to dist.",
        ],
    )
    print(f"medical_source_collect: proposed={len(proposed)} accepted={len(accepted)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
