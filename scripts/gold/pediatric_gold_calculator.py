#!/usr/bin/env python3
"""Exact pediatric dose calculator for sourced Gold formula templates.

The calculator can compute exact mg and mL from a formula template and a known
concentration. A row is still not Gold pediatric RX-ready unless the Gold
validator has an accepted source for both the formula and product concentration.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def _round_ml(value: float) -> float:
    return round(value + 1e-9, 1)


def calculate(generic_name: str, age_months: float, weight_kg: float, concentration_mg_per_ml: float | None = None) -> dict[str, Any]:
    generic = generic_name.lower()
    if weight_kg <= 0:
        raise ValueError("weight_kg must be positive")
    if "paracetamol" in generic or "acetaminophen" in generic:
        mg_per_kg = 10 if age_months < 1 else 15
        max_mg_per_kg_day = 40 if age_months < 1 else 60
        dose_mg = mg_per_kg * weight_kg
        result: dict[str, Any] = {
            "generic_name": generic_name,
            "age_months": age_months,
            "weight_kg": weight_kg,
            "dose_mg_per_dose": round(dose_mg, 2),
            "frequency": "3 to 4 times daily",
            "max_mg_per_day": round(max_mg_per_kg_day * weight_kg, 2),
            "source_ids": ["msf_paracetamol_oral_peds_2024"],
            "gold_ready_warning": "formula sourced; product-specific concentration source still required before pediatric RX use",
        }
        if concentration_mg_per_ml:
            result["dose_ml_per_dose"] = _round_ml(dose_mg / concentration_mg_per_ml)
        return result
    if "ibuprofen" in generic:
        if age_months < 3:
            raise ValueError("ibuprofen source gate blocks children under 3 months")
        min_mg = 5 * weight_kg
        max_mg = 10 * weight_kg
        result = {
            "generic_name": generic_name,
            "age_months": age_months,
            "weight_kg": weight_kg,
            "dose_min_mg_per_dose": round(min_mg, 2),
            "dose_max_mg_per_dose": round(max_mg, 2),
            "frequency": "3 to 4 times daily",
            "max_mg_per_day": round(30 * weight_kg, 2),
            "source_ids": ["msf_ibuprofen_oral_peds_2024"],
            "gold_ready_warning": "formula sourced; product-specific concentration source still required before pediatric RX use",
        }
        if concentration_mg_per_ml:
            result["dose_min_ml_per_dose"] = _round_ml(min_mg / concentration_mg_per_ml)
            result["dose_max_ml_per_dose"] = _round_ml(max_mg / concentration_mg_per_ml)
        return result
    if "oral rehydration" in generic or generic.strip() == "ors":
        plan_a = "50-100 mL after each loose stool" if age_months < 24 else ("100-200 mL after each loose stool" if age_months < 120 else "200-400 mL after each loose stool")
        total = 75 * weight_kg
        return {
            "generic_name": generic_name,
            "age_months": age_months,
            "weight_kg": weight_kg,
            "plan_a_after_each_loose_stool": plan_a,
            "plan_b_total_ml_over_4_hours": round(total, 2),
            "plan_b_ml_per_hour": round(total / 4, 2),
            "source_ids": ["msf_ors_peds_2024"],
            "gold_ready_warning": "formula sourced; exact ORS product sachet/dilution source still required before pediatric RX use",
        }
    raise ValueError(f"unsupported pediatric formula: {generic_name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generic", required=True)
    parser.add_argument("--age-months", type=float, required=True)
    parser.add_argument("--weight-kg", type=float, required=True)
    parser.add_argument("--concentration-mg-per-ml", type=float)
    args = parser.parse_args()
    print(json.dumps(calculate(args.generic, args.age_months, args.weight_kg, args.concentration_mg_per_ml), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
