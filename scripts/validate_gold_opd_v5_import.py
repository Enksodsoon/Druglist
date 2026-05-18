#!/usr/bin/env python3
"""Validate the non-destructive Gold OPD v5 import artifacts."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "data" / "gold_opd_v5" / "runtime_bundle.json"
REPORT = ROOT / "reports" / "gold_opd_v5_validation_report.md"

REQUIRED_KEYS = [
    "disease_index",
    "rx_by_disease",
    "swaps_by_disease",
    "product_lookup",
    "peds_runtime_rules",
    "antibiotic_runtime_gates",
    "safety_runtime_gates",
    "clinical_test_cases",
    "clinical_expected_outputs",
]


def check(name: str, ok: bool, detail: str = "") -> tuple[str, bool, str]:
    return name, ok, detail


def main() -> int:
    results: list[tuple[str, bool, str]] = []
    if not BUNDLE.exists():
        results.append(check("runtime_bundle_exists", False, str(BUNDLE)))
    else:
        data = json.loads(BUNDLE.read_text(encoding="utf-8"))
        for key in REQUIRED_KEYS:
            results.append(check(f"has_{key}", key in data, ""))
        results.append(check("has_products", len(data.get("product_lookup", {})) >= 900, str(len(data.get("product_lookup", {})))))
        results.append(check("has_fast_index", len(data.get("disease_index", [])) > 0, str(len(data.get("disease_index", [])))))
        results.append(check("has_rx", sum(len(v) for v in data.get("rx_by_disease", {}).values()) > 0, ""))
        results.append(check("has_swaps", sum(len(v) for v in data.get("swaps_by_disease", {}).values()) > 0, ""))
        results.append(check("has_antibiotic_gates", len(data.get("antibiotic_runtime_gates", [])) > 0, ""))
        results.append(check("has_safety_gates", len(data.get("safety_runtime_gates", [])) > 0, ""))
        results.append(check("test_case_output_parity", len(data.get("clinical_test_cases", [])) == len(data.get("clinical_expected_outputs", [])), f"tests={len(data.get('clinical_test_cases', []))}, outputs={len(data.get('clinical_expected_outputs', []))}"))

    failed = [row for row in results if not row[1]]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Gold OPD v5 Validation Report", ""]
    for name, ok, detail in results:
        lines.append(f"- {'PASS' if ok else 'FAIL'} `{name}` {detail}".rstrip())
    lines.append("")
    lines.append("Overall: " + ("PASS" if not failed else "FAIL"))
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Gold OPD v5 validation", "PASS" if not failed else "FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
