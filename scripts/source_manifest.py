#!/usr/bin/env python3
"""Validate and summarize manually reviewed evidence source intake."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from typing import Any

from engine_common import clean, now_iso, read_json, write_json
from evidence_common import (
    REPORT_DIR,
    ensure_evidence_dirs,
    load_source_manifest,
    source_manifest_sources,
    validate_source_manifest,
)


def source_domains(sources: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    domains: dict[str, Counter[str]] = defaultdict(Counter)
    for source in sources:
        domain = clean(source.get("clinical_domain")) or "unspecified"
        domains[domain][clean(source.get("review_status")) or "pending"] += 1
    return {domain: dict(counts) for domain, counts in sorted(domains.items())}


def missing_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        source
        for source in sources
        if clean(source.get("access_status") or "missing") == "missing" or not clean(source.get("url_or_file"))
    ]


def pending_gaps() -> list[dict[str, Any]]:
    gaps = read_json("data/guidelines/source_gap_list.json", {"items": []}).get("items", [])
    return [
        {
            "gap_id": clean(gap.get("gap_id")),
            "entity_type": clean(gap.get("entity_type")),
            "entity_id": clean(gap.get("entity_id")),
            "missing_item": clean(gap.get("missing_item") or gap.get("gap_type") or "source"),
            "status": "pending_source_collection",
            "review_note": "Attach accepted source_manifest row, then extract traceable claim evidence.",
        }
        for gap in gaps
    ]


def build_summary() -> dict[str, Any]:
    ensure_evidence_dirs()
    manifest = load_source_manifest()
    sources = source_manifest_sources()
    errors = validate_source_manifest(manifest)
    counts = Counter(clean(source.get("review_status")) or "pending" for source in sources)
    access_counts = Counter(clean(source.get("access_status")) or "missing" for source in sources)
    gap_queue = pending_gaps()
    summary = {
        "generated_at": now_iso(),
        "source_count": len(sources),
        "accepted_source_count": counts.get("accepted", 0),
        "reviewed_source_count": counts.get("reviewed", 0),
        "pending_source_count": counts.get("pending", 0),
        "rejected_source_count": counts.get("rejected", 0),
        "missing_source_count": len(missing_sources(sources)),
        "pending_gap_count": len(gap_queue),
        "validation_error_count": len(errors),
        "review_status_counts": dict(counts),
        "access_status_counts": dict(access_counts),
        "coverage_by_clinical_domain": source_domains(sources),
    }
    write_json("data/evidence/manual_review_queue.json", {"meta": summary, "items": gap_queue})
    lines = [
        f"- Manifest sources: {summary['source_count']}",
        f"- Accepted sources: {summary['accepted_source_count']}",
        f"- Pending sources: {summary['pending_source_count']}",
        f"- Missing URLs/files: {summary['missing_source_count']}",
        f"- Pending source gaps: {summary['pending_gap_count']}",
        f"- Validation errors: {summary['validation_error_count']}",
        "",
        "## Clinical Domain Coverage",
    ]
    if summary["coverage_by_clinical_domain"]:
        for domain, domain_counts in summary["coverage_by_clinical_domain"].items():
            counts_text = ", ".join(f"{key}: {value}" for key, value in sorted(domain_counts.items()))
            lines.append(f"- {domain}: {counts_text}")
    else:
        lines.append("- No manifest sources registered yet.")
    lines.extend(
        [
            "",
            "## Safety Rule",
            "Claims cannot become verified until the source manifest row is accepted and the extracted claim has traceable source location.",
        ]
    )
    if errors:
        lines.extend(["", "## Manifest Validation Errors", *[f"- {error}" for error in errors]])
    (REPORT_DIR / "source_intake_summary.md").write_text(
        "\n".join(["# Source Intake Summary", "", f"Generated: {summary['generated_at']}", "", *lines]).rstrip() + "\n",
        encoding="utf-8",
    )
    return summary


def print_rows(rows: list[dict[str, Any]], fields: list[str]) -> None:
    if not rows:
        print("none")
        return
    print(",".join(fields))
    for row in rows:
        print(",".join(clean(row.get(field)).replace(",", " ") for field in fields))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        nargs="?",
        default="summary",
        choices=["validate", "summary", "pending-gaps", "missing-sources", "accepted-sources"],
    )
    args = parser.parse_args()
    summary = build_summary()
    sources = source_manifest_sources()
    if args.command == "validate":
        errors = validate_source_manifest()
        if errors:
            print("\n".join(errors))
            return 1
        print("source_manifest: PASS")
        return 0
    if args.command == "pending-gaps":
        print_rows(pending_gaps(), ["gap_id", "entity_type", "entity_id", "missing_item", "status"])
    elif args.command == "missing-sources":
        print_rows(missing_sources(sources), ["source_id", "title", "access_status", "url_or_file", "clinical_domain"])
    elif args.command == "accepted-sources":
        print_rows(
            [source for source in sources if clean(source.get("review_status")) == "accepted"],
            ["source_id", "title", "organization", "year", "version", "url_or_file", "clinical_domain"],
        )
    else:
        print(
            "source_manifest summary: "
            + ", ".join(
                f"{key}={summary[key]}"
                for key in ["source_count", "accepted_source_count", "pending_gap_count", "missing_source_count"]
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
