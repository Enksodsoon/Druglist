#!/usr/bin/env python3
"""Build OPD runtime indexes from generated layers and legacy app seed."""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from engine_common import clean, display_name, ensure_dirs, load_embedded_seed, norm_key, now_iso, read_json, stable_id, write_json, write_report

COMMON_OPD_PATTERNS = [
    "allergic rhinitis",
    "URI wet cough",
    "URI dry cough",
    "cough sore throat sputum nasal discharge",
    "sore throat",
    "fever myalgia",
    "diarrhea adult",
    "diarrhea child",
    "nausea vomiting",
    "dyspepsia",
    "GERD",
    "constipation",
    "dry eye",
    "red eye",
    "bacterial conjunctivitis",
    "allergic conjunctivitis",
    "eyelid bump",
    "pterygium",
    "tinea",
    "dermatitis",
    "herpes labialis",
    "aphthous ulcer",
    "urticaria",
    "dysuria",
    "urinary frequency",
    "dysmenorrhea",
    "migraine headache",
    "vertigo",
    "MSK pain",
    "minor wound",
    "animal bite",
]

RUNTIME_PRIORITY = [
    "OPD_Fast_Index",
    "Top_50_Defaults",
    "Clinic_Defaults",
    "Complaint_Index",
    "Fast_Regimen_Master",
    "Drug_Short_Lookup",
    "Generic_Cluster_Map",
    "Pediatric_Layer",
    "Antibiotic_Stewardship",
    "Validation_Rules",
]


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def source_status_for(disease_id: str, disease_sources: dict[str, Any]) -> dict[str, object]:
    entry = disease_sources.get(disease_id) or {}
    return {
        "source_ids": entry.get("source_ids") or [],
        "source_status": entry.get("source_status") or "missing_verified_source",
        "manual_review": True,
    }


def normalize_legacy_med(med: dict[str, Any], short_lookup: dict[str, Any]) -> dict[str, object]:
    product_id = clean(med.get("i"))
    product = short_lookup.get(product_id) or {}
    return {
        "line_id": clean(med.get("s")) or stable_id("LINE", f"{product_id}_{med.get('n')}"),
        "line_type": clean(med.get("t")),
        "product_id": product_id,
        "display_name": clean(med.get("n")) or product.get("display_name", ""),
        "order_text": clean(med.get("o")),
        "duration_label": clean(med.get("u")),
        "pack_label": clean(med.get("p")),
        "source_status": "legacy_unverified",
        "manual_review": True,
    }


def build() -> dict[str, int]:
    ensure_dirs("data/core", "reports")
    generated_at = now_iso()
    seed = load_embedded_seed()
    short_lookup = read_json("data/core/drug_short_lookup.json", {"lookup": {}}).get("lookup", {})
    disease_guidelines = read_json("data/guidelines/disease_guideline_map.json", {"diseases": []}).get("diseases", [])
    disease_source_by_id = {item["disease_id"]: item for item in disease_guidelines}
    safety = read_json("data/safety/validation_rules.json", {"rules": []})
    antibiotic = read_json("data/safety/antibiotic_stewardship.json", {"rules": []})
    peds_output = read_json("data/pediatric/peds_product_dose_output.json", {"items": []})

    legacy_complaints = seed.get("cp") or []
    complaint_index: list[dict[str, object]] = []
    disease_master: dict[str, dict[str, object]] = {}
    fast_regimens: dict[str, dict[str, object]] = {}

    for pattern in COMMON_OPD_PATTERNS:
        disease_id = slug(pattern)
        disease_master[disease_id] = {
            "disease_id": disease_id,
            "display_name": pattern,
            "aliases": [pattern],
            "category": "",
            "runtime_priority": RUNTIME_PRIORITY,
            **source_status_for(disease_id, disease_source_by_id),
        }
        complaint_index.append(
            {
                "complaint_id": stable_id("CMP", pattern),
                "complaint": pattern,
                "disease_id": disease_id,
                "match_type": "required_pattern",
                "priority": 1,
                "source_status": "missing_verified_source",
                "manual_review": True,
            }
        )

    for complaint in legacy_complaints:
        c_text = clean(complaint.get("c"))
        disease_id = slug(clean(complaint.get("d")) or c_text)
        if disease_id and disease_id not in disease_master:
            disease_master[disease_id] = {
                "disease_id": disease_id,
                "display_name": clean(complaint.get("d")) or c_text,
                "aliases": [],
                "category": clean(complaint.get("g")),
                "runtime_priority": RUNTIME_PRIORITY,
                "source_ids": [],
                "source_status": "legacy_unverified",
                "manual_review": True,
            }
        if c_text:
            disease_master[disease_id]["aliases"] = sorted(set(disease_master[disease_id].get("aliases", []) + [c_text]))
            complaint_index.append(
                {
                    "complaint_id": clean(complaint.get("i")) or stable_id("CMP", c_text),
                    "complaint": c_text,
                    "disease_id": disease_id,
                    "match_type": clean(complaint.get("mt")) or "legacy",
                    "priority": int(float(complaint.get("p") or 5)),
                    "source_status": "legacy_unverified",
                    "manual_review": True,
                }
            )
        for regimen in complaint.get("r") or []:
            regimen_id = clean(regimen.get("i")) or stable_id("FRM", f"{disease_id}_{regimen.get('d')}")
            if regimen_id in fast_regimens:
                continue
            fast_regimens[regimen_id] = {
                "regimen_id": regimen_id,
                "disease_id": disease_id,
                "display_name": clean(regimen.get("d")),
                "workflow_label": clean(regimen.get("w")),
                "is_default": bool(regimen.get("y")),
                "lines": [normalize_legacy_med(med, short_lookup) for med in regimen.get("m") or []],
                "source_status": "legacy_unverified",
                "source_ids": [],
                "manual_review": True,
            }

    disease_list = sorted(disease_master.values(), key=lambda d: str(d["disease_id"]))
    fast_regimen_list = sorted(fast_regimens.values(), key=lambda r: str(r["regimen_id"]))
    opd_fast_index = {
        "meta": {
            "generated_at": generated_at,
            "runtime_priority": RUNTIME_PRIORITY,
            "source_status": "legacy_unverified_plus_framework",
        },
        "index": [
            {
                "disease_id": disease["disease_id"],
                "display_name": disease["display_name"],
                "complaints": [c for c in complaint_index if c["disease_id"] == disease["disease_id"]],
                "regimen_ids": [r["regimen_id"] for r in fast_regimen_list if r["disease_id"] == disease["disease_id"]],
                "manual_review": True,
            }
            for disease in disease_list
        ],
        "layer_links": {
            "drug_short_lookup": "data/core/drug_short_lookup.json",
            "generic_cluster_map": "data/core/generic_cluster_map.json",
            "pediatric_layer": "data/pediatric/peds_product_dose_output.json",
            "antibiotic_stewardship": "data/safety/antibiotic_stewardship.json",
            "validation_rules": "data/safety/validation_rules.json",
        },
    }

    meta = {
        "generated_at": generated_at,
        "complaint_count": len(complaint_index),
        "disease_count": len(disease_list),
        "regimen_count": len(fast_regimen_list),
        "manual_review": True,
        "safety_rule_count": len(safety.get("rules", [])),
        "antibiotic_rule_count": len(antibiotic.get("rules", [])),
        "pediatric_output_count": len(peds_output.get("items", [])),
    }
    write_json("data/core/complaint_index.json", {"meta": meta, "items": complaint_index})
    write_json("data/core/disease_master.json", {"meta": meta, "diseases": disease_list})
    write_json("data/core/fast_regimen_master.json", {"meta": meta, "regimens": fast_regimen_list})
    write_json("data/core/opd_fast_index.json", opd_fast_index)
    write_report(
        "reports/runtime_engine_report.md",
        "Runtime OPD Engine Report",
        [
            ("Summary", f"Complaints: {len(complaint_index)}\n\nDiseases: {len(disease_list)}\n\nFast regimens: {len(fast_regimen_list)}"),
            ("Priority", "\n".join(f"{idx}. {name}" for idx, name in enumerate(RUNTIME_PRIORITY, start=1))),
            ("Clinical Data Policy", "Legacy regimen rows are preserved as current-system references and marked `legacy_unverified` with manual review. New required OPD patterns have no invented treatment lines."),
        ],
    )
    return meta


def main() -> int:
    meta = build()
    print(f"built runtime engine: complaints={meta['complaint_count']} diseases={meta['disease_count']} regimens={meta['regimen_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
