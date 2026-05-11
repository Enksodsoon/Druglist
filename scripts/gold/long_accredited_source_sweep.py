#!/usr/bin/env python3
"""Build a long accredited-source acquisition plan for every Gold row.

This script is deliberately a queue/coverage builder, not a verifier. It
expands every product, regimen, pediatric shortcut, and antibiotic row into the
specific accredited evidence tasks needed to unlock it later. Existing Gold
validators still decide whether any row can become RX-ready.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/gold"))

from gold_common import (  # noqa: E402
    DATA_GOLD,
    REPORT_GOLD,
    export_sheet,
    read_json,
    stable_id,
    write_csv,
    write_json,
    write_report,
)


PRODUCT_TARGETS = [
    ("thai_fda_smpc_pil", "Thai FDA / Ref. SmPC / Ref. PIL", "Thai product registration, strength, form, route, label cautions"),
    ("thai_ndi_nlem", "Thai NDI / NLEM", "Thailand formulary or national-list status and local medicine context"),
    ("official_label", "DailyMed/FDA/eMC/EMA/TGA/Medsafe/Health Canada", "composition, strength, form, route, contraindications, precautions, side effects, interactions, pregnancy/lactation, renal/hepatic cautions"),
]

REGIMEN_TARGETS = [
    ("thai_rdu_moph", "Thai RDU / MOPH / DMS guideline", "Thailand outpatient disease strategy, line of treatment, antibiotic/no-antibiotic criteria, red flags"),
    ("disease_guideline", "NICE / CDC / IDSA / WHO / MSF / EAU / AAO guideline", "disease indication, line of treatment, dose, frequency, duration, red flags/referral criteria"),
    ("formulary", "WHO / MSF / BNF/BNFc formulary", "dose, route, frequency, max dose, contraindications, cautions, interactions"),
]

PEDIATRIC_TARGETS = [
    ("thai_pediatric", "Thai Pediatric Society / Thai MOPH pediatric source", "age range, weight rule, dose formula, max dose, contraindicated age, pediatric safety"),
    ("pediatric_formulary", "WHO EMLc / MSF / BNFc / official pediatric formulary", "age/BW formula, max dose, frequency, duration, rounding basis"),
    ("pediatric_product_label", "Thai FDA/SmPC/product label", "product concentration, formulation, route, age gate, pediatric cautions"),
]

ANTIBIOTIC_TARGETS = [
    ("thai_rdu_antibiotic", "Thai RDU / MOPH antibiotic guidance", "bacterial criteria, no-antibiotic rules, first-line/alternative logic, duration"),
    ("aware_stewardship", "WHO AWaRe / WHO antibiotic book", "AWaRe group, stewardship cautions, disease-specific antibiotic criteria"),
    ("infectious_guideline", "NICE / IDSA / CDC / EAU disease guideline", "disease-specific criteria, drug choice, dose, duration, allergy alternatives"),
]


def _query(*parts: str) -> str:
    return " ".join(str(part or "").strip() for part in parts if str(part or "").strip())


def _missing_for_regimen(row: dict[str, str]) -> list[str]:
    fields = []
    if row.get("final_verification_status") != "ready_source_verified":
        fields.extend(["indication", "line_of_treatment", "dose", "route", "frequency", "duration", "safety"])
    if row.get("antibiotic_criteria_verified") != "true":
        blob = (row.get("composition", "") + " " + row.get("drug_name", "") + " " + row.get("disease_key", "")).lower()
        if any(token in blob for token in ["amoxicillin", "azithro", "clav", "cef", "floxacin", "antibiotic"]):
            fields.append("antibiotic_criteria")
    return sorted(set(fields))


def build_long_queue() -> dict[str, int]:
    products = export_sheet("1_Product_Master_Export")
    regimens = export_sheet("2_Regimen_Master_Export", source_refreshed=True)
    peds = export_sheet("6_Pediatric_Dosing", source_refreshed=True)
    antibiotics = export_sheet("7_Antibiotic_Rows", source_refreshed=True)
    current_products = {row.get("product_id"): row for row in read_json(DATA_GOLD / "product_master_gold.json", {"items": []}).get("items", [])}
    current_regimens = read_json(DATA_GOLD / "disease_regimen_gold.json", {"items": []}).get("items", [])
    ready_pairs = {(row.get("product_id"), row.get("disease_key")) for row in current_regimens if str(row.get("final_rx_status", "")).startswith("gold_ready")}

    queue: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []

    for row in products:
        pid = row.get("product_id", "")
        generic = row.get("generic_name") or row.get("composition") or row.get("brand_name") or ""
        gold = current_products.get(pid, {})
        already_linked = bool(gold.get("product_metadata_source_ids"))
        missing = [] if already_linked else ["product_label_or_thai_registration", "contraindications", "side_effects", "interactions", "pregnancy_lactation", "renal_hepatic_cautions"]
        gaps.append(
            {
                "row_type": "product",
                "row_id": pid,
                "product_id": pid,
                "generic_name": generic,
                "disease_key": "",
                "current_status": "metadata_source_linked" if already_linked else "source_missing_hide_from_rx",
                "missing_fields": "; ".join(missing),
                "next_action": "review existing label source" if already_linked else "acquire Thai FDA/NDI or official label source and extract product safety metadata",
            }
        )
        if already_linked:
            continue
        for target_id, target_name, expected in PRODUCT_TARGETS:
            queue.append(
                {
                    "task_id": stable_id("longsrc", "product", pid, target_id),
                    "row_type": "product",
                    "priority": "A" if row.get("pediatric_flag") == "True" or row.get("antibiotic_flag") == "True" else "B",
                    "product_id": pid,
                    "regimen_id": "",
                    "disease_key": "",
                    "generic_name": generic,
                    "brand_name": row.get("brand_name", ""),
                    "source_target_id": target_id,
                    "source_target": target_name,
                    "expected_fields": expected,
                    "thai_query": _query(generic, row.get("brand_name", ""), "Thai FDA NDI NLEM SmPC"),
                    "english_query": _query(generic, row.get("strength", ""), row.get("dosage_form", ""), "official label contraindications adverse reactions interactions"),
                    "required_to_unlock": "product metadata/safety; not enough alone for disease regimen",
                    "status": "queued",
                }
            )

    for idx, row in enumerate(regimens):
        pid = row.get("product_id", "")
        disease = row.get("disease_key", "")
        generic = row.get("composition") or row.get("drug_name") or ""
        missing = _missing_for_regimen(row)
        status = "ready_source_verified" if (pid, disease) in ready_pairs else "source_missing_hide_from_rx"
        gaps.append(
            {
                "row_type": "regimen",
                "row_id": row.get("regimen_id") or f"regimen_row_{idx}",
                "product_id": pid,
                "generic_name": generic,
                "disease_key": disease,
                "current_status": status,
                "missing_fields": "; ".join(missing),
                "next_action": "already Gold-ready; periodic source review" if status == "ready_source_verified" else "acquire disease guideline/formulary evidence for indication, dose, duration, line of treatment, and safety",
            }
        )
        if status == "ready_source_verified":
            continue
        for target_id, target_name, expected in REGIMEN_TARGETS:
            queue.append(
                {
                    "task_id": stable_id("longsrc", "regimen", idx, pid, disease, target_id),
                    "row_type": "regimen",
                    "priority": "A" if row.get("role") == "RX NOW" else "B",
                    "product_id": pid,
                    "regimen_id": row.get("regimen_id", ""),
                    "disease_key": disease,
                    "generic_name": generic,
                    "brand_name": row.get("drug_name", ""),
                    "source_target_id": target_id,
                    "source_target": target_name,
                    "expected_fields": expected,
                    "thai_query": _query(disease, generic, "Thai RDU MOPH guideline dose duration"),
                    "english_query": _query(disease, generic, "guideline dose duration line of therapy contraindications interactions"),
                    "required_to_unlock": "exact disease-specific indication, dose, frequency, duration, safety and line-of-treatment snippets",
                    "status": "queued",
                }
            )

    for idx, row in enumerate(peds):
        generic = row.get("generic_key") or row.get("display_name") or ""
        gaps.append(
            {
                "row_type": "pediatric",
                "row_id": row.get("product_id") or f"peds_row_{idx}",
                "product_id": row.get("product_id", ""),
                "generic_name": generic,
                "disease_key": "",
                "current_status": "source_missing_hide_from_rx",
                "missing_fields": "pediatric formula; age/BW rule; max dose; product concentration; rounding rule; pediatric safety",
                "next_action": "acquire pediatric formulary/guideline plus product concentration label before calculation-ready RX",
            }
        )
        for target_id, target_name, expected in PEDIATRIC_TARGETS:
            queue.append(
                {
                    "task_id": stable_id("longsrc", "peds", idx, row.get("product_id"), target_id),
                    "row_type": "pediatric",
                    "priority": "A",
                    "product_id": row.get("product_id", ""),
                    "regimen_id": "",
                    "disease_key": "",
                    "generic_name": generic,
                    "brand_name": row.get("display_name", ""),
                    "source_target_id": target_id,
                    "source_target": target_name,
                    "expected_fields": expected,
                    "thai_query": _query(generic, "เด็ก ขนาดยา mg/kg Thai Pediatric MOPH"),
                    "english_query": _query(generic, "pediatric dose mg/kg max dose concentration BNFc MSF WHO EMLc"),
                    "required_to_unlock": "complete pediatric formula plus accredited product concentration/formulation source",
                    "status": "queued",
                }
            )

    for idx, row in enumerate(antibiotics):
        generic = row.get("composition") or row.get("drug_name") or ""
        disease = row.get("disease_key") or row.get("disease_name") or ""
        gaps.append(
            {
                "row_type": "antibiotic",
                "row_id": row.get("regimen_id") or f"abx_row_{idx}",
                "product_id": row.get("product_id", ""),
                "generic_name": generic,
                "disease_key": disease,
                "current_status": "source_missing_hide_from_rx",
                "missing_fields": "bacterial criteria; no-antibiotic rule if relevant; drug choice; dose; duration; allergy alternative; stewardship cautions",
                "next_action": "acquire RDU/AWaRe/NICE/IDSA/CDC/Thai guideline evidence before antibiotic gate can unlock",
            }
        )
        for target_id, target_name, expected in ANTIBIOTIC_TARGETS:
            queue.append(
                {
                    "task_id": stable_id("longsrc", "abx", idx, row.get("product_id"), disease, target_id),
                    "row_type": "antibiotic",
                    "priority": "A",
                    "product_id": row.get("product_id", ""),
                    "regimen_id": row.get("regimen_id", ""),
                    "disease_key": disease,
                    "generic_name": generic,
                    "brand_name": row.get("drug_name", ""),
                    "source_target_id": target_id,
                    "source_target": target_name,
                    "expected_fields": expected,
                    "thai_query": _query(disease, generic, "Thai RDU antibiotic criteria duration"),
                    "english_query": _query(disease, generic, "antibiotic guideline criteria dose duration AWaRe"),
                    "required_to_unlock": "disease-specific bacterial criteria, dose, duration, safety, and gate logic",
                    "status": "queued",
                }
            )

    REPORT_GOLD.mkdir(parents=True, exist_ok=True)
    write_csv(REPORT_GOLD / "long_accredited_source_acquisition_queue.csv", queue)
    write_csv(REPORT_GOLD / "long_accredited_source_gap_matrix.csv", gaps)
    write_json(DATA_GOLD / "long_accredited_source_acquisition_queue.json", {"items": queue})
    write_json(DATA_GOLD / "long_accredited_source_gap_matrix.json", {"items": gaps})

    by_type = Counter(row["row_type"] for row in queue)
    by_target = Counter(row["source_target_id"] for row in queue)
    summary = {
        "products_processed": len(products),
        "regimens_processed": len(regimens),
        "pediatric_rows_processed": len(peds),
        "antibiotic_rows_processed": len(antibiotics),
        "long_source_tasks": len(queue),
        "gap_rows": len(gaps),
        "product_tasks": by_type.get("product", 0),
        "regimen_tasks": by_type.get("regimen", 0),
        "pediatric_tasks": by_type.get("pediatric", 0),
        "antibiotic_tasks": by_type.get("antibiotic", 0),
    }
    write_report(
        REPORT_GOLD / "long_accredited_source_sweep_summary.md",
        "Long Accredited Source Sweep Summary",
        [
            "This report is an acquisition plan, not clinical verification. Rows remain hidden unless exact source-backed field-level evidence passes Gold validation.",
            *[f"- {key}: {value}" for key, value in summary.items()],
            "- Source target counts:",
            *[f"  - {key}: {value}" for key, value in sorted(by_target.items())],
        ],
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-gold-pipeline", action="store_true", help="Run the Gold pipeline after building the long queue.")
    parser.add_argument("--max-dailymed-groups", type=int, default=25, help="Bounded DailyMed generic groups to fetch if --run-gold-pipeline is used.")
    args = parser.parse_args()
    summary = build_long_queue()
    if args.run_gold_pipeline:
        env = os.environ.copy()
        env["GOLD_FULL_SWEEP_MAX_GROUPS"] = str(args.max_dailymed_groups)
        subprocess.run([sys.executable, "scripts/gold/run_gold_pipeline.py"], cwd=ROOT, env=env, check=True)
        subprocess.run([sys.executable, "scripts/gold/09_validate_gold_readiness.py"], cwd=ROOT, check=True)
    print(
        "long_accredited_source_sweep: "
        f"tasks={summary['long_source_tasks']} "
        f"products={summary['products_processed']} "
        f"regimens={summary['regimens_processed']} "
        f"peds={summary['pediatric_rows_processed']} "
        f"antibiotics={summary['antibiotic_rows_processed']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
