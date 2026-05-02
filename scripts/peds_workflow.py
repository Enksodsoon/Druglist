#!/usr/bin/env python3
"""Pediatric dose review export/import workflow."""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

from engine_common import ROOT, ensure_dirs, now_iso, read_json, stable_id, write_json

PEDS_COLUMNS = [
    "peds_dose_rule_id",
    "generic_name",
    "disease_key",
    "indication_text",
    "age_min_value",
    "age_min_unit",
    "age_max_value",
    "age_max_unit",
    "weight_min_kg",
    "weight_max_kg",
    "dose_basis",
    "dose_mg_per_kg_per_dose",
    "dose_mg_per_kg_per_day",
    "fixed_dose",
    "fixed_dose_unit",
    "frequency",
    "max_per_dose",
    "max_per_day",
    "duration",
    "route",
    "source_ids",
    "reviewer_status",
    "reviewer_note",
]

ALLOWED_STATUS = {"verified", "pending_source", "do_not_use", "label_reference_only", "manual_review"}
REVIEWED_PEDS_STORE = "data/pediatric/reviewed_peds_dose_rules.json"


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def parse_ids(value: str) -> list[str]:
    return [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [{k: clean(v) for k, v in row.items()} for row in csv.DictReader(handle)]


def write_csv(path: str, rows: list[dict[str, Any]], columns: list[str]) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in columns})


def export_review(_: argparse.Namespace) -> int:
    items = read_json("data/pediatric/peds_product_dose_output.json", {"items": []}).get("items", [])
    rows = []
    for item in items:
        rows.append(
            {
                "peds_dose_rule_id": stable_id("PEDS_RULE", item.get("product_id")),
                "generic_name": item.get("generic_key", ""),
                "disease_key": "",
                "indication_text": "",
                "age_min_value": "",
                "age_min_unit": "",
                "age_max_value": "",
                "age_max_unit": "",
                "weight_min_kg": "",
                "weight_max_kg": "",
                "dose_basis": "",
                "dose_mg_per_kg_per_dose": "",
                "dose_mg_per_kg_per_day": "",
                "fixed_dose": "",
                "fixed_dose_unit": "",
                "frequency": "",
                "max_per_dose": "",
                "max_per_day": "",
                "duration": "",
                "route": item.get("route", ""),
                "source_ids": "",
                "reviewer_status": "manual_review",
                "reviewer_note": "; ".join(item.get("review_reasons") or []),
            }
        )
    write_csv("reports/peds_dose_review_worklist.csv", rows, PEDS_COLUMNS)
    print("exported pediatric review worklist: reports/peds_dose_review_worklist.csv")
    return 0


def has_dose(row: dict[str, str]) -> bool:
    return any(clean(row.get(col)) for col in ["dose_mg_per_kg_per_dose", "dose_mg_per_kg_per_day", "fixed_dose"])


def validate_row(row: dict[str, str], row_num: int) -> str | None:
    status = clean(row.get("reviewer_status"))
    if status not in ALLOWED_STATUS:
        return f"row {row_num}: invalid reviewer_status {status!r}"
    source_ids = parse_ids(clean(row.get("source_ids")))
    if status == "verified":
        if not source_ids:
            return f"row {row_num}: verified pediatric row requires source_ids"
        missing = [col for col in ["generic_name", "disease_key", "indication_text", "frequency", "duration", "route"] if not clean(row.get(col))]
        if missing:
            return f"row {row_num}: verified pediatric row missing {', '.join(missing)}"
        if not has_dose(row):
            return f"row {row_num}: verified pediatric row requires a dose basis"
    return None


def normalize(row: dict[str, str]) -> dict[str, Any]:
    status = clean(row.get("reviewer_status")) or "manual_review"
    source_ids = parse_ids(clean(row.get("source_ids")))
    auto_calculable = status == "verified" and bool(source_ids) and clean(row.get("dose_basis")) in {"mg_per_kg_per_dose", "mg_per_kg_per_day", "fixed_dose"}
    return {
        **{col: clean(row.get(col)) for col in PEDS_COLUMNS},
        "source_ids": source_ids,
        "reviewer_status": status,
        "auto_calculable": auto_calculable,
        "fast_mode_allowed": status == "verified" and auto_calculable,
        "manual_review": status != "verified",
        "reviewed_at": now_iso(),
    }


def import_reviewed(args: argparse.Namespace) -> int:
    path = ROOT / args.csv_path
    rows = read_csv_rows(path)
    errors = [err for idx, row in enumerate(rows, start=2) if (err := validate_row(row, idx))]
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 2
    reviewed = [normalize(row) for row in rows if clean(row.get("peds_dose_rule_id"))]
    ensure_dirs("data/pediatric")
    write_json(REVIEWED_PEDS_STORE, {"meta": {"generated_at": now_iso(), "count": len(reviewed)}, "rules": reviewed})
    print(f"imported reviewed pediatric rows: {len(reviewed)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("export-review").set_defaults(func=export_review)
    import_parser = sub.add_parser("import-reviewed")
    import_parser.add_argument("csv_path")
    import_parser.set_defaults(func=import_reviewed)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
