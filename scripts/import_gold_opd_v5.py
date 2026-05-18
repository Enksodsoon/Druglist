#!/usr/bin/env python3
"""Import Gold OPD Engine v5 CSV handoff files into app-ready JSON artifacts.

This script is intentionally non-destructive. It reads CSV files from
imports/gold_opd_v5/ and writes JSON into data/gold_opd_v5/ so the current
legacy runtime can keep working until the v5 engine is explicitly wired.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
IMPORT_DIR = ROOT / "imports" / "gold_opd_v5"
OUT_DIR = ROOT / "data" / "gold_opd_v5"
REPORT_DIR = ROOT / "reports"

CSV_FILES = {
    "opd_fast_index": "opd_fast_index_v5.csv",
    "drug_short_lookup": "drug_short_lookup_v5.csv",
    "final_rx_now": "final_rx_now_v5.csv",
    "final_swaps_tiered": "final_swaps_tiered_v5.csv",
    "peds_runtime_rules": "peds_runtime_rules_v5.csv",
    "antibiotic_runtime_gates": "antibiotic_runtime_gates_v5.csv",
    "safety_runtime_gates": "safety_runtime_gates_v5.csv",
    "clinical_test_cases": "clinical_test_cases_v5.csv",
    "clinical_expected_outputs": "clinical_expected_outputs_v5.csv",
    "clinical_gap_report": "clinical_gap_report_v5.csv",
    "runtime_patch": "runtime_patch_v5.csv",
    "app_integration_map": "app_integration_map_v5.csv",
    "validation_report": "validation_v5_report.csv",
    "change_log": "change_log_v5.csv",
}


def read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required v5 CSV: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def first_present(row: dict[str, Any], names: list[str]) -> str:
    for name in names:
        value = str(row.get(name) or "").strip()
        if value:
            return value
    return ""


def build_runtime_bundle(tables: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    disease_index: dict[str, dict[str, Any]] = {}
    for row in tables["opd_fast_index"]:
        disease_key = first_present(row, ["Disease_Key", "disease_key", "disease_id", "Disease", "diagnosis_key"])
        complaint = first_present(row, ["Complaint", "complaint", "Alias", "alias", "input_phrase"])
        if not disease_key:
            continue
        item = disease_index.setdefault(disease_key, {"disease_key": disease_key, "aliases": []})
        if complaint and complaint not in item["aliases"]:
            item["aliases"].append(complaint)

    rx_by_disease: dict[str, list[dict[str, Any]]] = {}
    for row in tables["final_rx_now"]:
        disease_key = first_present(row, ["Disease_Key", "disease_key", "disease_id", "Diagnosis_Key"])
        if disease_key:
            rx_by_disease.setdefault(disease_key, []).append(row)

    swaps_by_disease: dict[str, list[dict[str, Any]]] = {}
    for row in tables["final_swaps_tiered"]:
        disease_key = first_present(row, ["Disease_Key", "disease_key", "disease_id", "Diagnosis_Key"])
        if disease_key:
            swaps_by_disease.setdefault(disease_key, []).append(row)

    product_lookup: dict[str, dict[str, Any]] = {}
    for row in tables["drug_short_lookup"]:
        product_id = first_present(row, ["Product_ID", "product_id", "BDS", "bds", "id"])
        if product_id:
            product_lookup[product_id] = row

    bundle = {
        "schema_version": "gold-opd-v5-runtime-import-v1",
        "status": "production_candidate_non_destructive",
        "disease_index": sorted(disease_index.values(), key=lambda x: x["disease_key"]),
        "rx_by_disease": rx_by_disease,
        "swaps_by_disease": swaps_by_disease,
        "product_lookup": product_lookup,
        "peds_runtime_rules": tables["peds_runtime_rules"],
        "antibiotic_runtime_gates": tables["antibiotic_runtime_gates"],
        "safety_runtime_gates": tables["safety_runtime_gates"],
        "clinical_test_cases": tables["clinical_test_cases"],
        "clinical_expected_outputs": tables["clinical_expected_outputs"],
        "clinical_gap_report": tables["clinical_gap_report"],
        "runtime_patch": tables["runtime_patch"],
        "app_integration_map": tables["app_integration_map"],
        "validation_report": tables["validation_report"],
        "change_log": tables["change_log"],
        "counts": {key: len(value) for key, value in tables.items()},
    }
    return bundle


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    tables = {name: read_csv(IMPORT_DIR / filename) for name, filename in CSV_FILES.items()}

    for name, rows in tables.items():
        write_json(OUT_DIR / f"{name}.json", {"items": rows, "count": len(rows)})

    bundle = build_runtime_bundle(tables)
    write_json(OUT_DIR / "runtime_bundle.json", bundle)
    write_json(OUT_DIR / "manifest.json", {"schema_version": bundle["schema_version"], "counts": bundle["counts"]})

    lines = ["# Gold OPD v5 Import Report", ""]
    for key, count in sorted(bundle["counts"].items()):
        lines.append(f"- {key}: {count}")
    lines.append("")
    lines.append("Non-destructive import complete. Wire `data/gold_opd_v5/runtime_bundle.json` into the app only after validation passes.")
    (REPORT_DIR / "gold_opd_v5_import_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Gold OPD v5 import complete")
    print(json.dumps(bundle["counts"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
