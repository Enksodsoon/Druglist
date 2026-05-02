#!/usr/bin/env python3
"""Export and import source-gap review worklists without fabricating evidence."""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

from engine_common import ROOT, ensure_dirs, now_iso, read_json, write_json, write_report

SOURCE_COLUMNS = [
    "source_id",
    "title",
    "organization",
    "country",
    "year",
    "version",
    "url",
    "file_reference",
    "access_date",
    "source_type",
    "authority_level",
    "thai_source_flag",
    "patient_group",
    "disease_area",
    "drug_group",
    "applies_to",
    "status",
    "notes",
]

GAP_COLUMNS = [
    "gap_id",
    "disease_key",
    "generic_name",
    "drug_class",
    "missing_item",
    "source_ids",
    "resolution_status",
    "reviewer_note",
]

ALLOWED_SOURCE_STATUS = {"verified", "pending_access", "missing", "manual_review"}
ALLOWED_GAP_STATUS = {"linked", "unresolved", "pending_access", "not_applicable", "manual_review"}
REVIEWED_SOURCE_STORE = "data/sources/reviewed_source_registry.json"
REVIEWED_GAP_STORE = "data/sources/source_gap_review_links.json"


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [{k: clean(v) for k, v in row.items()} for row in csv.DictReader(handle)]


def write_csv(path: str | Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    target = ROOT / path if isinstance(path, str) else path
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in columns})


def source_gap_rows() -> list[dict[str, str]]:
    gaps = read_json("data/guidelines/source_gap_list.json", {"items": []}).get("items", [])
    rows: list[dict[str, str]] = []
    for gap in gaps:
        entity_type = clean(gap.get("entity_type"))
        entity_id = clean(gap.get("entity_id"))
        rows.append(
            {
                "gap_id": clean(gap.get("gap_id")),
                "disease_key": entity_id if entity_type == "disease" else "",
                "generic_name": "",
                "drug_class": entity_id if entity_type == "drug_role_tag" else "",
                "missing_item": entity_type or "source",
                "source_ids": ", ".join(gap.get("source_ids") or []),
                "resolution_status": clean(gap.get("resolution_status") or gap.get("status") or "unresolved"),
                "reviewer_note": clean(gap.get("reviewer_note") or gap.get("notes")),
            }
        )
    return rows


def export_gaps(_: argparse.Namespace) -> int:
    write_csv("reports/source_gap_worklist.csv", source_gap_rows(), GAP_COLUMNS)
    print("exported source gaps: reports/source_gap_worklist.csv")
    return 0


def export_template(_: argparse.Namespace) -> int:
    write_csv("reports/source_registry_template.csv", [], SOURCE_COLUMNS)
    print("exported source registry template: reports/source_registry_template.csv")
    return 0


def validate_source_row(row: dict[str, str], row_num: int) -> str | None:
    status = clean(row.get("status"))
    if status not in ALLOWED_SOURCE_STATUS:
        return f"row {row_num}: invalid status {status!r}"
    if status == "verified":
        missing = [col for col in ["source_id", "title", "organization"] if not clean(row.get(col))]
        if missing:
            return f"row {row_num}: verified source missing {', '.join(missing)}"
        if not clean(row.get("url")) and not clean(row.get("file_reference")):
            return f"row {row_num}: verified source requires url or file_reference"
    return None


def normalize_source(row: dict[str, str]) -> dict[str, Any]:
    status = clean(row.get("status")) or "manual_review"
    source_id = clean(row.get("source_id"))
    return {
        **{col: clean(row.get(col)) for col in SOURCE_COLUMNS},
        "source_id": source_id,
        "access_status": "available" if status == "verified" else status,
        "extraction_status": "extracted" if status == "verified" else "not_extracted",
        "manual_review": status != "verified",
        "imported_at": now_iso(),
    }


def import_sources(args: argparse.Namespace) -> int:
    path = ROOT / args.csv_path
    rows = read_csv_rows(path)
    errors = [err for idx, row in enumerate(rows, start=2) if (err := validate_source_row(row, idx))]
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 2
    reviewed = [normalize_source(row) for row in rows if clean(row.get("source_id"))]
    ensure_dirs("data/sources", "data/guidelines")
    write_json(REVIEWED_SOURCE_STORE, {"meta": {"generated_at": now_iso(), "count": len(reviewed)}, "sources": reviewed})
    merge_reviewed_sources()
    print(f"imported reviewed sources: {len(reviewed)}")
    return 0


def valid_source_ids() -> set[str]:
    registry = read_json("data/guidelines/source_registry.json", {"sources": []}).get("sources", [])
    reviewed = read_json(REVIEWED_SOURCE_STORE, {"sources": []}).get("sources", [])
    return {clean(row.get("source_id")) for row in [*registry, *reviewed] if clean(row.get("source_id"))}


def parse_ids(value: str) -> list[str]:
    return [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]


def validate_gap_row(row: dict[str, str], row_num: int, known_source_ids: set[str]) -> str | None:
    status = clean(row.get("resolution_status"))
    if status not in ALLOWED_GAP_STATUS:
        return f"row {row_num}: invalid resolution_status {status!r}"
    source_ids = parse_ids(clean(row.get("source_ids")))
    if status == "linked":
        if not source_ids:
            return f"row {row_num}: linked gap requires source_ids"
        unknown = [source_id for source_id in source_ids if source_id not in known_source_ids]
        if unknown:
            return f"row {row_num}: linked gap references unknown source_ids {', '.join(unknown)}"
    return None


def normalize_gap(row: dict[str, str]) -> dict[str, Any]:
    status = clean(row.get("resolution_status")) or "manual_review"
    source_ids = parse_ids(clean(row.get("source_ids")))
    return {
        **{col: clean(row.get(col)) for col in GAP_COLUMNS},
        "source_ids": source_ids,
        "resolution_status": status,
        "manual_review": status != "linked",
        "reviewed_at": now_iso(),
    }


def apply_links(args: argparse.Namespace) -> int:
    path = ROOT / args.csv_path
    rows = read_csv_rows(path)
    known = valid_source_ids()
    errors = [err for idx, row in enumerate(rows, start=2) if (err := validate_gap_row(row, idx, known))]
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 2
    reviewed = [normalize_gap(row) for row in rows if clean(row.get("gap_id"))]
    ensure_dirs("data/sources", "data/guidelines")
    write_json(REVIEWED_GAP_STORE, {"meta": {"generated_at": now_iso(), "count": len(reviewed)}, "items": reviewed})
    merge_reviewed_gaps()
    print(f"applied source gap review links: {len(reviewed)}")
    return 0


def merge_reviewed_sources() -> None:
    registry = read_json("data/guidelines/source_registry.json", {"meta": {}, "sources": []})
    reviewed = read_json(REVIEWED_SOURCE_STORE, {"sources": []}).get("sources", [])
    by_id = {clean(row.get("source_id")): dict(row) for row in registry.get("sources", []) if clean(row.get("source_id"))}
    for row in reviewed:
        source_id = clean(row.get("source_id"))
        if source_id:
            by_id[source_id] = {**by_id.get(source_id, {}), **row}
    registry["sources"] = sorted(by_id.values(), key=lambda row: clean(row.get("source_id")))
    registry.setdefault("meta", {})["reviewed_source_count"] = len(reviewed)
    write_json("data/guidelines/source_registry.json", registry)


def merge_reviewed_gaps() -> None:
    gaps = read_json("data/guidelines/source_gap_list.json", {"meta": {}, "items": []})
    reviewed = read_json(REVIEWED_GAP_STORE, {"items": []}).get("items", [])
    by_gap = {clean(row.get("gap_id")): row for row in reviewed if clean(row.get("gap_id"))}
    updated = []
    for gap in gaps.get("items", []):
        gap_id = clean(gap.get("gap_id"))
        review = by_gap.get(gap_id)
        if not review:
            updated.append(gap)
            continue
        status = clean(review.get("resolution_status"))
        source_ids = review.get("source_ids") or []
        updated.append(
            {
                **gap,
                "source_ids": source_ids,
                "resolution_status": status,
                "status": "linked" if status == "linked" else clean(gap.get("status") or "pending_access"),
                "manual_review": status != "linked",
                "reviewer_note": clean(review.get("reviewer_note")),
            }
        )
    gaps["items"] = updated
    gaps.setdefault("meta", {})["reviewed_gap_count"] = len(reviewed)
    gaps["meta"]["unresolved_gap_count"] = sum(1 for gap in updated if gap.get("manual_review", True))
    write_json("data/guidelines/source_gap_list.json", gaps)


def summary(_: argparse.Namespace) -> int:
    registry = read_json("data/guidelines/source_registry.json", {"sources": []}).get("sources", [])
    gaps = read_json("data/guidelines/source_gap_list.json", {"items": []}).get("items", [])
    verified = [row for row in registry if clean(row.get("status")) == "verified" or row.get("access_status") == "available"]
    linked = [gap for gap in gaps if clean(gap.get("resolution_status") or gap.get("status")) == "linked"]
    unresolved = [gap for gap in gaps if gap.get("manual_review", True)]
    write_report(
        "reports/source_workflow_summary.md",
        "Source Workflow Summary",
        [
            ("Registry", f"Registered sources: {len(registry)}\n\nVerified sources: {len(verified)}"),
            ("Gaps", f"Total gaps: {len(gaps)}\n\nLinked gaps: {len(linked)}\n\nUnresolved/manual-review gaps: {len(unresolved)}"),
            ("Policy", "A source is verified only when title, organization, and a URL or local source file reference are present. Missing or inaccessible sources remain pending_access/manual_review."),
        ],
    )
    print("wrote source workflow summary: reports/source_workflow_summary.md")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("export-gaps").set_defaults(func=export_gaps)
    sub.add_parser("export-template").set_defaults(func=export_template)
    import_parser = sub.add_parser("import-sources")
    import_parser.add_argument("csv_path")
    import_parser.set_defaults(func=import_sources)
    links_parser = sub.add_parser("apply-links")
    links_parser.add_argument("csv_path")
    links_parser.set_defaults(func=apply_links)
    sub.add_parser("summary").set_defaults(func=summary)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
