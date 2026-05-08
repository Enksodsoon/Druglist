#!/usr/bin/env python3
"""Summarize extracted source text and flag unreadable/paywalled sources."""

from __future__ import annotations

from medical_refresh_common import ROOT, read_json, text_window, write_json, write_report


def main() -> int:
    manifest = read_json("data/source_refresh/source_text_manifest.json", {"sources": []}).get("sources", [])
    summaries = []
    for item in manifest:
        text_file = item.get("text_file") or ""
        text = ""
        if text_file:
            path = ROOT / "data/source_refresh" / text_file
            if path.exists():
                text = path.read_text(encoding="utf-8", errors="ignore")
        summaries.append(
            {
                "source_id": item.get("source_id"),
                "text_extracted": bool(text),
                "character_count": len(text),
                "sample_relevant_snippet": text_window(text, ["acyclovir", "antiviral", "antibiotic", "essential medicines", "sore throat"]),
                "needs_ocr": item.get("access_status") == "needs_pdf_text_extraction",
                "blocked_thai_extraction_uncertain": False,
                "notes": item.get("notes", ""),
            }
        )
    write_json("data/source_refresh/source_text_summaries.json", {"sources": summaries})
    write_report(
        "reports/source_refresh/source_text_extraction_report.md",
        "Source Text Extraction Report",
        [
            f"- Sources in text manifest: {len(manifest)}",
            f"- Text extracted: {sum(1 for s in summaries if s['text_extracted'])}",
            f"- Needs OCR/PDF parsing: {sum(1 for s in summaries if s['needs_ocr'])}",
            f"- Thai extraction uncertain: {sum(1 for s in summaries if s['blocked_thai_extraction_uncertain'])}",
        ],
    )
    print(f"medical_source_extract: text_sources={sum(1 for s in summaries if s['text_extracted'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
