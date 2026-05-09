#!/usr/bin/env python3
"""Fetch text-check-ready acquisition candidates and update accepted sources."""

from __future__ import annotations

import re

from medical_refresh_common import TEXT_DIR, access_date, fetch_url, html_to_text, read_json, write_json, write_report


def safe_name(source_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", source_id).strip("_") + ".txt"


def main() -> int:
    candidates = read_json("data/source_refresh/source_acquisition_candidates.json", {"candidates": []}).get("candidates", [])
    accepted_manifest = read_json("data/source_refresh/source_manifest.accepted.json", {"sources": []})
    accepted_by_id = {source.get("source_id"): source for source in accepted_manifest.get("sources", [])}
    manifests = []
    for candidate in candidates:
        if candidate.get("candidate_status") != "text_check_ready":
            manifests.append({**candidate, "text_extracted": False, "extract_status": "skipped_not_text_ready"})
            continue
        url = candidate["url_or_file"]
        ctype, raw, err = fetch_url(url, timeout=20)
        if not raw or "text/html" not in ctype.lower():
            manifests.append({**candidate, "text_extracted": False, "extract_status": "fetch_failed", "error": err})
            continue
        text = html_to_text(raw)
        path = TEXT_DIR / safe_name(candidate["source_id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        source_row = {
            "source_id": candidate["source_id"],
            "source_title": candidate["source_title"],
            "organization": candidate["organization"],
            "source_url": candidate["url_or_file"],
            "local_file_reference": f"source_text/{path.name}",
            "source_type": candidate["source_type"],
            "clinical_domain": candidate["source_pack_id"],
            "disease_keys": [],
            "related_generics": [],
            "related_regimens": [],
            "year": candidate.get("year_version") or "source_version_unknown",
            "access_date": access_date(),
            "text_extracted": True,
            "review_status": "accepted",
            "notes": "Accepted by source acquisition v1 after official URL fetch and snippet extraction eligibility; row claims still require exact matching.",
        }
        accepted_by_id[source_row["source_id"]] = source_row
        manifests.append({**candidate, "text_extracted": True, "extract_status": "extracted", "local_text_file": source_row["local_file_reference"], "text_chars": len(text)})
    accepted_sources = sorted(accepted_by_id.values(), key=lambda source: source.get("source_id", ""))
    write_json("data/source_refresh/source_manifest.accepted.json", {"sources": accepted_sources})
    write_json("data/source_refresh/source_acquisition_text_manifest.json", {"sources": manifests})
    extracted = sum(1 for item in manifests if item.get("text_extracted"))
    write_report(
        "reports/source_refresh/source_acquisition_collection_report.md",
        "Source Acquisition Collection Report",
        [
            f"- Text sources extracted: {extracted}",
            f"- Accepted source manifest count: {len(accepted_sources)}",
            "- Raw/full source text is cached under data/source_refresh/source_text and must not be copied to dist.",
        ],
    )
    print(f"source_acquisition_collect_extract: extracted={extracted} accepted={len(accepted_sources)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
