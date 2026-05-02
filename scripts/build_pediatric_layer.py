#!/usr/bin/env python3
"""Build pediatric concentration and review-gated dose outputs."""
from __future__ import annotations

import re
from collections import Counter

from engine_common import clean, ensure_dirs, norm_key, now_iso, read_json, stable_id, write_json, write_report


def parse_concentration(composition: str) -> dict[str, object]:
    text = clean(composition).replace("μg", "mcg")
    low = text.lower()
    patterns = [
        (r"(\d+(?:\.\d+)?)\s*mg\.?\s*/\s*(\d+(?:\.\d+)?)\s*ml", "mg_per_ml", 1.0),
        (r"(\d+(?:\.\d+)?)\s*g\.?\s*/\s*(\d+(?:\.\d+)?)\s*ml", "mg_per_ml", 1000.0),
        (r"(\d+(?:\.\d+)?)\s*mcg\.?\s*/\s*(\d+(?:\.\d+)?)\s*ml", "mcg_per_ml", 1.0),
        (r"(\d+(?:\.\d+)?)\s*unit\.?\s*/\s*(\d+(?:\.\d+)?)\s*ml", "unit_per_ml", 1.0),
    ]
    for pattern, unit, factor in patterns:
        match = re.search(pattern, low, re.I)
        if match:
            numerator = float(match.group(1)) * factor
            denominator = float(match.group(2))
            if denominator > 0:
                return {
                    "parse_status": "parsed",
                    "value": round(numerator / denominator, 6),
                    "unit": unit,
                    "matched_text": match.group(0),
                    "manual_review": False,
                }
    percent = re.search(r"(\d+(?:\.\d+)?)\s*%", low)
    if percent:
        return {
            "parse_status": "parsed_percent",
            "value": float(percent.group(1)),
            "unit": "percent",
            "matched_text": percent.group(0),
            "manual_review": True,
            "review_reason": "percent_strength_requires_route_specific_interpretation",
        }
    strength = re.search(r"(\d+(?:\.\d+)?)\s*(mg|g|mcg|unit)\b", low, re.I)
    if strength:
        value = float(strength.group(1))
        unit = strength.group(2).lower()
        if unit == "g":
            value *= 1000
            unit = "mg"
        return {
            "parse_status": "unit_strength_only",
            "value": value,
            "unit": unit,
            "matched_text": strength.group(0),
            "manual_review": True,
            "review_reason": "not_a_liquid_concentration",
        }
    return {"parse_status": "missing", "value": None, "unit": "", "matched_text": "", "manual_review": True}


def peds_candidate(product: dict[str, object]) -> bool:
    tags = set(product.get("role_tags") or [])
    form = str(product.get("form") or "")
    return "pediatric_candidate" in tags or form in {"syrup", "suspension", "drops", "powder"}


def build() -> dict[str, object]:
    ensure_dirs("data/pediatric", "reports")
    products = read_json("data/core/drug_master_rebuilt.json", {"products": []}).get("products", [])
    peds_source_rules = read_json("data/guidelines/dose_rules_peds_source_linked.json", {"rules": []}).get("rules", [])
    verified_rules = [rule for rule in peds_source_rules if rule.get("active") and rule.get("source_ids")]
    generated_at = now_iso()

    concentration_map = []
    product_outputs = []
    reasons = Counter()
    for product in products:
        concentration = parse_concentration(str(product.get("composition") or ""))
        concentration_map.append(
            {
                "product_id": product["id"],
                "display_name": product["display_name"],
                "form": product.get("form", ""),
                "route": product.get("route", ""),
                "composition": product.get("composition", ""),
                "concentration": concentration,
                "source": product.get("source", {}),
            }
        )
        if not peds_candidate(product):
            continue
        review_reasons = ["missing_verified_pediatric_dose_source", "missing_age_bw_rule", "missing_max_dose"]
        if concentration.get("manual_review"):
            review_reasons.append("concentration_missing_or_requires_review")
        if product.get("flags", {}).get("antibiotic"):
            review_reasons.extend(["antibiotic_requires_disease_specific_indication", "antibiotic_requires_duration_source"])
        for reason in review_reasons:
            reasons[reason] += 1
        product_outputs.append(
            {
                "product_id": product["id"],
                "display_name": product["display_name"],
                "generic_key": product.get("generic_key", ""),
                "form": product.get("form", ""),
                "route": product.get("route", ""),
                "concentration": concentration,
                "dose_output_status": "manual_review",
                "auto_dose_enabled": False,
                "age_bw_rule": "",
                "dose_basis": "",
                "max_dose": "",
                "source_ids": [],
                "review_reasons": review_reasons,
            }
        )

    age_gate_library = {
        "meta": {
            "generated_at": generated_at,
            "status": "framework_pending_verified_pediatric_sources",
            "manual_review": True,
        },
        "gates": [
            {
                "gate_id": "PEDS_GATE_FRAMEWORK",
                "description": "Age and body-weight gates must be configured from verified pediatric sources before dose automation.",
                "source_ids": [],
                "active": False,
                "manual_review": True,
            }
        ],
    }

    dose_rules_verified = {
        "meta": {
            "generated_at": generated_at,
            "verified_rule_count": len(verified_rules),
            "status": "empty_until_source_linked_rules_exist" if not verified_rules else "source_linked",
        },
        "rules": verified_rules,
    }
    meta = {
        "generated_at": generated_at,
        "product_count": len(products),
        "concentration_records": len(concentration_map),
        "pediatric_candidate_count": len(product_outputs),
        "auto_dose_enabled_count": 0,
        "manual_review_count": len(product_outputs),
    }
    write_json("data/pediatric/product_concentration_map.json", {"meta": meta, "items": concentration_map})
    write_json("data/pediatric/peds_dose_rules_verified.json", dose_rules_verified)
    write_json("data/pediatric/peds_age_gate_library.json", age_gate_library)
    write_json("data/pediatric/peds_product_dose_output.json", {"meta": meta, "items": product_outputs})

    parse_counts = Counter(item["concentration"]["parse_status"] for item in concentration_map)
    write_report(
        "reports/peds_dosing_audit_report.md",
        "Pediatric Dosing Audit",
        [
            ("Summary", f"Pediatric candidate products: {len(product_outputs)}\n\nAuto-dose enabled: 0\n\nManual-review pediatric outputs: {len(product_outputs)}"),
            ("Concentration Parse Status", "\n".join(f"- {k}: {v}" for k, v in sorted(parse_counts.items()))),
            ("Review Reasons", "\n".join(f"- {k}: {v}" for k, v in sorted(reasons.items())) or "No pediatric candidates found."),
            ("Clinical Data Policy", "No pediatric dosing was automated because verified source, age/body-weight rule, max dose, and indication/duration requirements were not satisfied."),
        ],
    )
    return meta


def main() -> int:
    meta = build()
    print(f"built pediatric layer: candidates={meta['pediatric_candidate_count']} auto_dose=0 manual_review={meta['manual_review_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
