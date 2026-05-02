#!/usr/bin/env python3
"""Antibiotic stewardship review export/import workflow."""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

from engine_common import ROOT, clean, ensure_dirs, now_iso, read_json, stable_id, write_json

ANTIBIOTIC_COLUMNS = [
    "antibiotic_rule_id",
    "disease_key",
    "generic_name",
    "product_links",
    "bacterial_criteria",
    "no_antibiotic_criteria",
    "first_line_flag",
    "alternative_flag",
    "allergy_alternative",
    "adult_dose_rule_id",
    "peds_dose_rule_id",
    "duration",
    "red_flags",
    "referral_criteria",
    "source_ids",
    "reviewer_status",
    "reviewer_note",
]

ALLOWED_STATUS = {"verified", "pending_source", "local_rule_only", "do_not_use", "manual_review"}
NO_ROUTINE_DISEASES = [
    ("viral_uri", "No routine antibiotic for viral URI unless a verified bacterial complication rule is documented."),
    ("acute_bronchitis", "No routine antibiotic unless a verified criteria-dependent bacterial rule is documented."),
    ("simple_diarrhea", "No routine antibiotic for simple non-bloody diarrhea."),
    ("allergic_rhinitis", "No antibiotic for allergic rhinitis."),
    ("dry_eye", "No antibiotic for dry eye."),
    ("allergic_conjunctivitis", "No antibiotic for allergic conjunctivitis."),
]
REVIEWED_ANTIBIOTIC_STORE = "data/safety/reviewed_antibiotic_rules.json"


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


def known_source_ids() -> set[str]:
    registry = read_json("data/guidelines/source_registry.json", {"sources": []}).get("sources", [])
    reviewed = read_json("data/sources/reviewed_source_registry.json", {"sources": []}).get("sources", [])
    return {clean(row.get("source_id")) for row in [*registry, *reviewed] if clean(row.get("source_id"))}


def export_review(_: argparse.Namespace) -> int:
    products = read_json("data/core/drug_master_rebuilt.json", {"products": []}).get("products", [])
    antibiotic_products = [p for p in products if p.get("category") == "antibiotic" or "antibiotic" in (p.get("role_tags") or [])]
    rows: list[dict[str, str]] = []
    for disease_key, note in NO_ROUTINE_DISEASES:
        rows.append(
            {
                "antibiotic_rule_id": stable_id("ABX_NO_ROUTINE", disease_key),
                "disease_key": disease_key,
                "generic_name": "",
                "product_links": "",
                "bacterial_criteria": "",
                "no_antibiotic_criteria": note,
                "first_line_flag": "false",
                "alternative_flag": "false",
                "allergy_alternative": "",
                "adult_dose_rule_id": "",
                "peds_dose_rule_id": "",
                "duration": "",
                "red_flags": "",
                "referral_criteria": "",
                "source_ids": "",
                "reviewer_status": "pending_source",
                "reviewer_note": "Framework row only; add verified local guideline source before using as authority.",
            }
        )
    for product in antibiotic_products:
        rows.append(
            {
                "antibiotic_rule_id": stable_id("ABX_PRODUCT", product.get("id")),
                "disease_key": "",
                "generic_name": product.get("generic_key") or product.get("generic") or "",
                "product_links": product.get("id", ""),
                "bacterial_criteria": "",
                "no_antibiotic_criteria": "",
                "first_line_flag": "false",
                "alternative_flag": "false",
                "allergy_alternative": "beta_lactam_review" if is_beta_lactam(product) else "",
                "adult_dose_rule_id": "",
                "peds_dose_rule_id": "",
                "duration": "",
                "red_flags": "",
                "referral_criteria": "",
                "source_ids": "",
                "reviewer_status": "manual_review",
                "reviewer_note": "Antibiotic product requires disease-specific indication, dose, duration, and source before FAST MODE.",
            }
        )
    write_csv("reports/antibiotic_review_worklist.csv", rows, ANTIBIOTIC_COLUMNS)
    print("exported antibiotic review worklist: reports/antibiotic_review_worklist.csv")
    return 0


def is_beta_lactam(product: dict[str, Any]) -> bool:
    text = " ".join(clean(product.get(key)) for key in ["generic", "generic_key", "composition", "display_name"]).lower()
    return any(key in text for key in ["amoxicillin", "clavulan", "cephalexin", "cef", "penicillin", "dicloxacillin"])


def truthy(value: str) -> bool:
    return clean(value).lower() in {"1", "true", "yes", "y"}


def validate_row(row: dict[str, str], row_num: int, known_sources: set[str]) -> str | None:
    status = clean(row.get("reviewer_status"))
    if status not in ALLOWED_STATUS:
        return f"row {row_num}: invalid reviewer_status {status!r}"
    source_ids = parse_ids(clean(row.get("source_ids")))
    unknown = [source_id for source_id in source_ids if source_id not in known_sources]
    if source_ids and unknown:
        return f"row {row_num}: unknown source_ids {', '.join(unknown)}"
    if status == "verified":
        if not source_ids:
            return f"row {row_num}: verified antibiotic rule requires source_ids"
        missing = [col for col in ["antibiotic_rule_id", "disease_key", "generic_name", "bacterial_criteria", "duration"] if not clean(row.get(col))]
        if missing:
            return f"row {row_num}: verified antibiotic rule missing {', '.join(missing)}"
        if not clean(row.get("adult_dose_rule_id")) and not clean(row.get("peds_dose_rule_id")):
            return f"row {row_num}: verified antibiotic rule requires adult_dose_rule_id or peds_dose_rule_id"
        if clean(row.get("peds_dose_rule_id")) and not clean(row.get("source_ids")):
            return f"row {row_num}: pediatric antibiotic rule requires pediatric source and dose rule"
    return None


def normalize(row: dict[str, str]) -> dict[str, Any]:
    status = clean(row.get("reviewer_status")) or "manual_review"
    source_ids = parse_ids(clean(row.get("source_ids")))
    product_links = parse_ids(clean(row.get("product_links")))
    source_verified = status == "verified" and bool(source_ids)
    return {
        **{col: clean(row.get(col)) for col in ANTIBIOTIC_COLUMNS},
        "product_links": product_links,
        "source_ids": source_ids,
        "first_line_flag": truthy(clean(row.get("first_line_flag"))),
        "alternative_flag": truthy(clean(row.get("alternative_flag"))),
        "source_verified": source_verified,
        "criteria_dependent": bool(clean(row.get("bacterial_criteria")) or clean(row.get("no_antibiotic_criteria"))),
        "manual_review": status != "verified",
        "reviewed_at": now_iso(),
    }


def import_reviewed(args: argparse.Namespace) -> int:
    path = ROOT / args.csv_path
    rows = read_csv_rows(path)
    known = known_source_ids()
    errors = [err for idx, row in enumerate(rows, start=2) if (err := validate_row(row, idx, known))]
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 2
    reviewed = [normalize(row) for row in rows if clean(row.get("antibiotic_rule_id"))]
    ensure_dirs("data/safety")
    write_json(REVIEWED_ANTIBIOTIC_STORE, {"meta": {"generated_at": now_iso(), "count": len(reviewed)}, "rules": reviewed})
    print(f"imported reviewed antibiotic rows: {len(reviewed)}")
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
