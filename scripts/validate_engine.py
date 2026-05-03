#!/usr/bin/env python3
"""Validate generated Drug Assistant runtime files."""
from __future__ import annotations

import json
import os
from pathlib import Path

from engine_common import ROOT, now_iso, write_json, write_report

REQUIRED_JSON = [
    "data/core/drug_master_rebuilt.json",
    "data/core/drug_short_lookup.json",
    "data/core/generic_cluster_map.json",
    "data/core/complaint_index.json",
    "data/core/disease_master.json",
    "data/core/fast_regimen_master.json",
    "data/core/opd_fast_index.json",
    "data/core/app_seed_runtime.json",
    "data/guidelines/source_registry.json",
    "data/guidelines/disease_guideline_map.json",
    "data/guidelines/drug_indication_guideline_map.json",
    "data/guidelines/dose_rules_adult_source_linked.json",
    "data/guidelines/dose_rules_peds_source_linked.json",
    "data/guidelines/rdu_source_linked_rules.json",
    "data/guidelines/antibiotic_guideline_rules.json",
    "data/guidelines/safety_guideline_rules.json",
    "data/guidelines/evidence_conflict_log.json",
    "data/guidelines/source_gap_list.json",
    "data/pediatric/product_concentration_map.json",
    "data/pediatric/peds_dose_rules_verified.json",
    "data/pediatric/peds_age_gate_library.json",
    "data/pediatric/peds_product_dose_output.json",
    "data/safety/validation_rules.json",
    "data/safety/rdu_rules.json",
    "data/safety/antibiotic_stewardship.json",
    "data/safety/red_flags.json",
    "data/meta/manual_review_queue.json",
    "data/meta/build_manifest.json",
    "data/evidence/source_search_tasks.json",
    "data/evidence/source_cache_manifest.json",
    "data/evidence/evidence_candidates.json",
    "data/evidence/evidence_claims.json",
    "data/evidence/evidence_scores.json",
    "data/evidence/auto_verified_claims.json",
    "data/evidence/unresolved_low_confidence_gaps.json",
    "data/evidence/auto_resolved_source_gaps.json",
    "data/evidence/evidence_runtime_summary.json",
]

REQUIRED_SECTIONS = ["main", "peds", "catalog", "compare", "validation", "inventory", "admin", "rules"]


def report_time() -> str:
    manifest = ROOT / "data/meta/build_manifest.json"
    if manifest.exists():
        try:
            return json.loads(manifest.read_text(encoding="utf-8")).get("generated_at") or now_iso()
        except json.JSONDecodeError:
            return now_iso()
    return now_iso()


def load(path: str, errors: list[str]) -> dict:
    target = ROOT / path
    if not target.exists():
        errors.append(f"missing_json:{path}")
        return {}
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"invalid_json:{path}:{exc}")
        return {}


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    payloads = {path: load(path, errors) for path in REQUIRED_JSON}

    products = payloads["data/core/drug_master_rebuilt.json"].get("products", [])
    product_ids = {p.get("id") for p in products}
    products_by_id = {p.get("id"): p for p in products}
    if len(product_ids) != len(products):
        errors.append("duplicate_product_ids")

    sources = payloads["data/guidelines/source_registry.json"].get("sources", [])
    verified_sources = [s for s in sources if s.get("access_status") == "available" and s.get("extraction_status") == "extracted"]
    source_coverage = len(verified_sources) / max(1, len(sources))
    if source_coverage == 0:
        warnings.append("source_coverage_zero_pending_manual_source_extraction")

    peds_outputs = payloads["data/pediatric/peds_product_dose_output.json"].get("items", [])
    unsafe_peds = [item.get("product_id") for item in peds_outputs if item.get("auto_dose_enabled") and not item.get("source_ids")]
    if unsafe_peds:
        errors.append(f"peds_auto_dose_without_source:{len(unsafe_peds)}")
    if not payloads["data/pediatric/peds_age_gate_library.json"].get("gates"):
        errors.append("missing_peds_age_gate_framework")

    abx_rules = payloads["data/safety/antibiotic_stewardship.json"].get("rules", [])
    if not any("antibiotic" in rule.get("category", "") for rule in abx_rules):
        errors.append("missing_antibiotic_stewardship_rules")
    if not any("indication" in rule.get("message", "").lower() for rule in abx_rules):
        errors.append("missing_antibiotic_indication_gate")

    diseases = {d.get("disease_id") for d in payloads["data/core/disease_master.json"].get("diseases", [])}
    broken_complaints = [c for c in payloads["data/core/complaint_index.json"].get("items", []) if c.get("disease_id") not in diseases]
    if broken_complaints:
        errors.append(f"complaint_links_missing_disease:{len(broken_complaints)}")
    regimens = payloads["data/core/fast_regimen_master.json"].get("regimens", [])
    broken_regimens = [r for r in regimens if r.get("disease_id") not in diseases]
    if broken_regimens:
        errors.append(f"regimen_links_missing_disease:{len(broken_regimens)}")
    broken_meds = [
        line.get("product_id")
        for regimen in regimens
        for line in regimen.get("lines", [])
        if line.get("product_id") and line.get("product_id") not in product_ids
    ]
    if broken_meds:
        warnings.append(f"legacy_regimen_product_links_missing_product:{len(broken_meds)}")
    allowed_source_status = {"source_verified", "source_gap", "pending_manual_review", "local_rule_only", "not_applicable"}
    allowed_readiness = {"ready", "usable_with_warning", "manual_review_required", "blocked"}
    runtime_lines = [line for regimen in regimens for line in regimen.get("lines", [])]
    missing_readiness = [
        line.get("line_id")
        for line in runtime_lines
        if line.get("source_status") not in allowed_source_status
        or line.get("clinical_readiness") not in allowed_readiness
        or not isinstance(line.get("missing_requirements"), list)
        or not isinstance(line.get("fast_mode_allowed"), bool)
    ]
    if missing_readiness:
        errors.append(f"runtime_lines_missing_readiness:{len(missing_readiness)}")
    source_verified_without_source = [
        line.get("line_id")
        for line in runtime_lines
        if line.get("source_status") == "source_verified" and not line.get("source_ids")
    ]
    if source_verified_without_source:
        errors.append(f"source_verified_without_source_ids:{len(source_verified_without_source)}")
    unsafe_antibiotics = [
        line.get("line_id")
        for line in runtime_lines
        for product in [products_by_id.get(line.get("product_id")) or {}]
        if line.get("fast_mode_allowed")
        and (
            product.get("category") == "antibiotic"
            or "antibiotic" in " ".join([str(line.get("display_name", "")), str(product.get("generic", ""))]).lower()
        )
        and line.get("source_status") != "source_verified"
    ]
    if unsafe_antibiotics:
        errors.append(f"antibiotic_fast_mode_without_verified_gate:{len(unsafe_antibiotics)}")

    evidence_scores = payloads["data/evidence/evidence_scores.json"].get("claims", [])
    evidence_verified_without_source = [
        claim.get("claim_id")
        for claim in evidence_scores
        if claim.get("evidence_status") == "auto_verified"
        and (not claim.get("source_id") or not (claim.get("source_location") or claim.get("file_reference") or claim.get("url") or claim.get("snippet")))
    ]
    if evidence_verified_without_source:
        errors.append(f"evidence_auto_verified_without_source:{len(evidence_verified_without_source)}")
    unsafe_peds_evidence = [
        claim.get("claim_id")
        for claim in evidence_scores
        if claim.get("evidence_status") == "auto_verified"
        and claim.get("claim_type") == "peds dose"
        and claim.get("evidence_required_fields_missing")
    ]
    if unsafe_peds_evidence:
        errors.append(f"peds_evidence_verified_missing_required_fields:{len(unsafe_peds_evidence)}")
    unsafe_antibiotic_evidence = [
        claim.get("claim_id")
        for claim in evidence_scores
        if claim.get("evidence_status") == "auto_verified"
        and claim.get("claim_type") == "antibiotic criteria"
        and claim.get("evidence_required_fields_missing")
    ]
    if unsafe_antibiotic_evidence:
        errors.append(f"antibiotic_evidence_verified_missing_required_fields:{len(unsafe_antibiotic_evidence)}")

    index_text = (ROOT / "index.html").read_text(encoding="utf-8")
    for section in REQUIRED_SECTIONS:
        if f'id="section-{section}"' not in index_text:
            errors.append(f"missing_frontend_section:{section}")
    if 'data-tab="rules"' not in index_text:
        errors.append("rules_tab_not_visible")
    if "loadRuntimeSeed" not in index_text or "app_seed_runtime.json" not in index_text:
        errors.append("frontend_runtime_loader_missing")

    generated_at = report_time()
    os.environ["DRUGLIST_BUILD_TIME"] = generated_at
    report = {
        "generated_at": generated_at,
        "pass": not errors,
        "errors": errors,
        "warnings": warnings,
        "counts": {
            "products": len(products),
            "sources": len(sources),
            "verified_sources": len(verified_sources),
            "source_coverage": round(source_coverage, 4),
            "pediatric_outputs": len(peds_outputs),
            "regimens": len(regimens),
            "evidence_claims": len(evidence_scores),
            "evidence_auto_verified": sum(1 for claim in evidence_scores if claim.get("evidence_status") == "auto_verified"),
        },
    }
    write_json("reports/validation_report.json", report)
    write_report(
        "reports/validation_report.md",
        "Validation Report",
        [
            ("Status", "PASS" if report["pass"] else "FAIL"),
            ("Errors", "\n".join(f"- {err}" for err in errors) or "None"),
            ("Warnings", "\n".join(f"- {warn}" for warn in warnings) or "None"),
            ("Counts", "\n".join(f"- {k}: {v}" for k, v in report["counts"].items())),
        ],
    )
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
