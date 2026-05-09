#!/usr/bin/env python3
"""Shared implementation for the Gold Drug Verification pipeline.

Phase 1 is intentionally conservative: it builds normalized gold artifacts,
source acquisition queues, field-level evidence scaffolding, validators, review
exports, and a feature-flag loader without promoting the gold overlay into the
production runtime.
"""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
import zipfile
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
EXPORTS = ROOT / "exports"
REFRESH_CSV = EXPORTS / "refresh_csv"
SOURCE_REFRESH_CSV = EXPORTS / "source_refresh_csv"
DATA_GOLD = ROOT / "data/gold"
DIST_GOLD = ROOT / "dist/gold"
REPORT_GOLD = ROOT / "reports/gold"
RAW_SOURCES = ROOT / "imports/raw_sources"
PROCESSED_SOURCES = ROOT / "imports/processed_sources"
REJECTED_SOURCES = ROOT / "imports/rejected_sources"
SOURCE_LOGS = ROOT / "imports/logs"

ALLOWED_FINAL_STATUSES = {
    "gold_ready_adult",
    "gold_ready_pediatric",
    "gold_ready_conditional",
    "conditional_use_when_criteria_met",
    "use_with_warning",
    "catalog_hidden_from_rx",
    "source_missing_hide_from_rx",
    "source_conflict_hide_from_rx",
    "not_recommended_for_this_disease",
    "absolute_block",
}

WORKBOOK_PRIORITY = [
    "drug_list_final_userfriendly_engine_ready_v7.xlsx",
    "drug_assistant_v2_ready_workbook.xlsx",
    "drug_list_final_userfriendly_engine_ready_v6.xlsx",
    "drug_list_final_userfriendly.xlsx",
    "Drug-Table-Notion.txt",
]

WORKBOOK_SEARCH_DIRS = [
    ROOT / "imports",
    ROOT / "imports/raw_packages",
    ROOT / "imports/raw_workbook",
    ROOT / "imports/gold_master",
    ROOT / "data",
    ROOT / "data/raw",
    ROOT / "data/gold",
    ROOT / "public",
    ROOT / "dist",
    ROOT,
    ROOT / "source_workbooks",
]

EXPECTED_SHEETS = [
    "Top_50_Defaults",
    "Clinic_Defaults",
    "Complaint_Index",
    "Fast_Regimen_Master",
    "Drug_Master_Lookup",
    "Peds_Dose_Shortcuts",
    "Antibiotic_Rows",
]

SHEET_TO_EXPORT = {
    "Drug_Master_Lookup": "1_Product_Master_Export",
    "Fast_Regimen_Master": "2_Regimen_Master_Export",
    "Complaint_Index": "3_Complaint_Disease_Map",
    "Top_50_Defaults": "4_Top_50_Defaults",
    "Clinic_Defaults": "5_Clinic_Defaults",
    "Peds_Dose_Shortcuts": "6_Pediatric_Dosing",
    "Antibiotic_Rows": "7_Antibiotic_Rows",
}

GOLD_JSON_FILES = [
    "product_master_gold.json",
    "disease_regimen_gold.json",
    "pediatric_dose_engine.json",
    "antibiotic_gate_map.json",
    "safety_profile_gold.json",
    "search_alias_index.json",
    "source_citations_gold.json",
    "rx_eligibility_map.json",
    "gold_runtime_config.json",
]

REVIEW_FILES = [
    "rx_now_ready_rows.csv",
    "swaps_ready_rows.csv",
    "reference_only_rows.csv",
    "blocked_rows.csv",
    "not_ready_rows.csv",
]


def ensure_dirs() -> None:
    for path in [
        DATA_GOLD,
        DATA_GOLD / "review",
        DIST_GOLD / "review",
        REPORT_GOLD,
        RAW_SOURCES,
        PROCESSED_SOURCES,
        REJECTED_SOURCES,
        SOURCE_LOGS,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def today() -> str:
    return date.today().isoformat()


def read_json(path: str | Path, default: Any) -> Any:
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(path: str | Path, payload: Any) -> None:
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_csv(path: str | Path) -> list[dict[str, str]]:
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    if not p.exists():
        return []
    with p.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: str | Path, rows: list[dict[str, Any]], columns: list[str] | None = None) -> None:
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    p.parent.mkdir(parents=True, exist_ok=True)
    if columns is None:
        columns = []
        for row in rows:
            for key in row:
                if key not in columns:
                    columns.append(key)
    with p.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: serialize(row.get(key, "")) for key in columns})


def serialize(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return "; ".join(serialize(v) for v in value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def write_report(path: str | Path, title: str, lines: list[str]) -> None:
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# " + title + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")


def slug(value: str, fallback: str = "item") -> str:
    text = re.sub(r"[^a-z0-9]+", "_", (value or "").lower()).strip("_")
    return text[:80] or fallback


def stable_id(prefix: str, *parts: Any) -> str:
    import hashlib

    raw = "|".join(str(part or "") for part in parts)
    return f"{prefix}_{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:12]}"


def export_sheet(name: str, source_refreshed: bool = False) -> list[dict[str, str]]:
    folder = SOURCE_REFRESH_CSV if source_refreshed and (SOURCE_REFRESH_CSV / f"{name}.csv").exists() else REFRESH_CSV
    return read_csv(folder / f"{name}.csv")


def discover_workbook() -> dict[str, Any]:
    candidates: list[Path] = []
    for wanted in WORKBOOK_PRIORITY:
        for base in WORKBOOK_SEARCH_DIRS:
            path = base / wanted
            if path.exists():
                candidates.append(path)
    selected = candidates[0] if candidates else None
    sheet_counts = {export_name: len(export_sheet(export_name)) for export_name in SHEET_TO_EXPORT.values()}
    report_lines = [
        f"- Selected workbook: `{selected.relative_to(ROOT) if selected else 'none_found'}`",
        "- Workbook is treated as an inventory/draft seed, not verified clinical evidence.",
        "- Candidate files found:",
        *[f"  - `{path.relative_to(ROOT)}`" for path in candidates],
        "- Expected sheet mapping uses generated export CSVs when direct workbook sheets are unavailable.",
        *[f"- {sheet}: {sheet_counts.get(export_name, 0)} rows via `{export_name}.csv`" for sheet, export_name in SHEET_TO_EXPORT.items()],
    ]
    write_report(REPORT_GOLD / "source_file_discovery_report.md", "Gold Source File Discovery Report", report_lines)
    return {"selected_workbook": str(selected.relative_to(ROOT)) if selected else "", "candidates": [str(p.relative_to(ROOT)) for p in candidates]}


def repo_mapping() -> None:
    product_rows = export_sheet("1_Product_Master_Export")
    regimen_rows = export_sheet("2_Regimen_Master_Export", source_refreshed=True)
    peds_rows = export_sheet("6_Pediatric_Dosing", source_refreshed=True)
    antibiotic_rows = export_sheet("7_Antibiotic_Rows", source_refreshed=True)
    lines = [
        "- Current active workbook/import seed: `source_workbooks/drug_list_final_userfriendly_engine_ready_v7.xlsx` if present; legacy engine also references `source_workbooks/Drug list for physician usage added -update 29022024.xlsx`.",
        "- Product/runtime data: `data/core/drug_master_rebuilt.json`, `data/core/fast_regimen_master.json`, `data/core/app_seed_runtime.json`.",
        "- Frontend entrypoint: `index.html`; deploy artifact: `dist/`.",
        "- Build scripts: `scripts/build_all.py`, `scripts/build_runtime_json.py`, `scripts/build_frontend_seed.py`, `scripts/build_dist.py`.",
        "- Validation scripts: `scripts/validate_engine.py`, `scripts/check_runtime_artifacts.py`, `scripts/validate_source_refreshed_workbook.py`.",
        "- Existing source/evidence logic: `data/evidence/`, `data/source_refresh/`, `scripts/source_acquisition_*`, `scripts/exact_claim_extractor.py`.",
        "- RX NOW/SWAPS currently render from runtime complaint/regimen lines in `data/core/app_seed_runtime.json` and frontend builder code in `index.html`.",
        "- Gold overlay connects through `data/gold/rx_eligibility_map.json` and optional copied `dist/gold/*.json`; current production runtime is not overwritten.",
        "- Must not overwrite: `source_workbooks/`, raw workbooks, `data/core/app_seed_runtime.json`, and generated production runtime unless explicit promotion is requested.",
        f"- Products found in export: {len(product_rows)}",
        f"- Draft regimen rows found in export: {len(regimen_rows)}",
        f"- Pediatric rows found in export: {len(peds_rows)}",
        f"- Antibiotic rows found in export: {len(antibiotic_rows)}",
        "- Test/build commands found: `make verify`, `python3 -m pytest -q`, `python3 scripts/validate_engine.py`, `python3 scripts/build_dist.py`.",
        "- Repo-specific risks: embedded seed in `index.html` is large; source coverage is still low; accepted claims may conflict with workbook rows; pediatric/antibiotic gates must remain conservative.",
    ]
    write_report(REPORT_GOLD / "current_repo_mapping.md", "Current Repo Mapping", lines)


def workbook_extraction_report(selected: dict[str, Any]) -> None:
    product_rows = export_sheet("1_Product_Master_Export")
    regimen_rows = export_sheet("2_Regimen_Master_Export", source_refreshed=True)
    complaint_rows = export_sheet("3_Complaint_Disease_Map")
    peds_rows = export_sheet("6_Pediatric_Dosing", source_refreshed=True)
    antibiotic_rows = export_sheet("7_Antibiotic_Rows", source_refreshed=True)
    products = {row.get("product_id") for row in product_rows if row.get("product_id")}
    regimen_missing_product = [row for row in regimen_rows if row.get("product_id") and row.get("product_id") not in products]
    peds_missing_product = [row for row in peds_rows if row.get("product_id") and row.get("product_id") not in products]
    antibiotic_missing_product = [row for row in antibiotic_rows if row.get("product_id") and row.get("product_id") not in products]
    product_names = Counter((row.get("brand_name") or "").strip().lower() for row in product_rows if row.get("brand_name"))
    duplicate_names = [name for name, count in product_names.items() if count > 1]
    lines = [
        f"- Workbook selected: `{selected.get('selected_workbook') or 'none_found'}`",
        f"- Candidate workbook files found: {len(selected.get('candidates') or [])}",
        "- Sheets found through generated export CSVs:",
        *[f"  - {sheet}: {len(export_sheet(export_name, source_refreshed=True))} rows; columns: {', '.join((export_sheet(export_name, source_refreshed=True)[:1] or [{}])[0].keys())}" for sheet, export_name in SHEET_TO_EXPORT.items()],
        f"- Expected sheets missing: {', '.join(sheet for sheet, export_name in SHEET_TO_EXPORT.items() if not export_sheet(export_name, source_refreshed=True)) or 'none'}",
        f"- Duplicate product names: {len(duplicate_names)}",
        f"- Products without regimen mapping: {max(0, len(products - {r.get('product_id') for r in regimen_rows if r.get('product_id')}))}",
        f"- Regimen rows without product match: {len(regimen_missing_product)}",
        f"- Pediatric rows without product match: {len(peds_missing_product)}",
        f"- Antibiotic rows without product match: {len(antibiotic_missing_product)}",
        "- Extraction warning: workbook rows remain draft seeds; no row is upgraded without field-level source evidence.",
        f"- Complaint/disease map rows: {len(complaint_rows)}",
    ]
    write_report(REPORT_GOLD / "workbook_extraction_report.md", "Workbook Extraction Report", lines)


def build_queries() -> list[dict[str, Any]]:
    products = export_sheet("1_Product_Master_Export")
    regimens = export_sheet("2_Regimen_Master_Export", source_refreshed=True)
    peds = export_sheet("6_Pediatric_Dosing", source_refreshed=True)
    antibiotics = export_sheet("7_Antibiotic_Rows", source_refreshed=True)
    queries: list[dict[str, Any]] = []

    def add(priority: str, product_id: str, product_name: str, generic: str, disease_key: str, category: str, target: str, query: str, fields: str, notes: str = "") -> None:
        queries.append(
            {
                "query_id": stable_id("gq", priority, product_id, generic, disease_key, category, target, query),
                "priority": priority,
                "product_id": product_id,
                "product_name": product_name,
                "generic_name": generic,
                "disease_key": disease_key,
                "source_category": category,
                "source_target": target,
                "query": query,
                "expected_fields": fields,
                "retrieval_status": "queued",
                "notes": notes,
            }
        )

    for row in products[:910]:
        generic = row.get("generic_name") or row.get("composition") or ""
        brand = row.get("brand_name") or ""
        pid = row.get("product_id") or ""
        if generic:
            add("A" if row.get("antibiotic_flag") == "True" or row.get("pediatric_flag") == "True" else "B", pid, brand, generic, "", "product_label", "Thai FDA/NDI", f"{generic} Thai FDA SmPC", "composition; strength; form; route; contraindications; cautions")
            add("B", pid, brand, generic, "", "official_label", "DailyMed/FDA/eMC", f"{generic} DailyMed dosage contraindications interactions", "dose; safety; interactions")

    seen_regimen = set()
    for row in regimens:
        key = (row.get("disease_key"), row.get("composition") or row.get("drug_name"))
        if key in seen_regimen:
            continue
        seen_regimen.add(key)
        disease = row.get("disease_key") or row.get("disease_name") or ""
        generic = row.get("composition") or row.get("drug_name") or ""
        add("A", row.get("product_id", ""), row.get("drug_name", ""), generic, disease, "disease_guideline", "Thai RDU/MOPH/NICE/CDC", f"{disease} guideline {generic} dose duration", "indication; adult dose; route; frequency; duration; red flags")

    for row in peds:
        generic = row.get("generic_key") or row.get("display_name") or ""
        add("A", row.get("product_id", ""), row.get("display_name", ""), generic, "", "pediatric_formulary", "Thai Pediatric Society/WHO/BNFc", f"{generic} pediatric dose mg/kg max dose concentration", "age range; weight rule; dose formula; max dose; concentration")

    for row in antibiotics:
        disease = row.get("disease_key") or row.get("disease_name") or ""
        generic = row.get("composition") or row.get("drug_name") or ""
        add("A", row.get("product_id", ""), row.get("drug_name", ""), generic, disease, "antibiotic_guideline", "Thai RDU/WHO AWaRe/NICE/IDSA", f"{disease} antibiotic criteria {generic} dose duration", "bacterial criteria; line of therapy; duration; safety gate")

    write_csv(REPORT_GOLD / "source_query_manifest.csv", queries)
    acquisition = [dict(row, queue_status="pending_source_acquisition") for row in queries]
    write_csv(REPORT_GOLD / "source_acquisition_queue.csv", acquisition)
    return queries


def source_records() -> list[dict[str, Any]]:
    accepted = read_json("data/source_refresh/source_manifest.accepted.json", {"sources": []}).get("sources", [])
    records = []
    for source in accepted:
        records.append(
            {
                "source_id": source.get("source_id", ""),
                "source_title": source.get("source_title", ""),
                "source_org": source.get("organization", ""),
                "source_url": source.get("source_url", ""),
                "access_date": source.get("access_date") or today(),
                "source_type": source.get("source_type", ""),
                "source_country_or_region": source.get("country") or source.get("country_or_region") or "",
                "evidence_field_supported": source.get("clinical_domain", ""),
                "evidence_snippet": "",
                "confidence": "",
                "linked_product_id": "",
                "linked_regimen_id": "; ".join(source.get("related_regimens") or []),
                "linked_disease_key": "; ".join(source.get("disease_keys") or []),
                "linked_generic_name": "; ".join(source.get("related_generics") or []),
                "adapter_name": "existing_source_refresh_manifest",
                "retrieval_status": "accepted_metadata_available",
                "extraction_status": "text_extracted" if source.get("text_extracted") else "pending_extraction",
            }
        )
    return records


def evidence_claims() -> list[dict[str, Any]]:
    claims = []
    for path in ["data/source_refresh/evidence_claims.json", "data/source_refresh/exact_evidence_claims.json", "data/evidence/evidence_claims.json"]:
        payload = read_json(path, {})
        items = payload.get("claims") or payload.get("items") or []
        for item in items:
            snippet = item.get("short_snippet") or item.get("evidence_snippet") or item.get("snippet") or ""
            if not snippet:
                continue
            claims.append(
                {
                    "claim_id": item.get("claim_id") or stable_id("claim", path, item.get("source_id"), item.get("claim_type"), snippet[:80]),
                    "source_id": item.get("source_id", ""),
                    "source_title": item.get("source_title", ""),
                    "source_org": item.get("organization") or item.get("source_org") or "",
                    "source_url": item.get("url_or_file") or item.get("source_url") or "",
                    "source_type": item.get("source_type", ""),
                    "evidence_field": item.get("claim_type", ""),
                    "evidence_snippet": snippet[:700],
                    "confidence": item.get("confidence_score") or item.get("evidence_confidence") or "",
                    "linked_product_id": item.get("product_id", ""),
                    "linked_regimen_id": item.get("regimen_id", ""),
                    "linked_disease_key": item.get("disease_key", ""),
                    "linked_generic_name": item.get("generic_name", ""),
                    "status": item.get("status", ""),
                }
            )
    return claims


def status_for_regimen(row: dict[str, str]) -> str:
    if row.get("final_verification_status") == "ready_source_verified":
        return "gold_ready_adult"
    if row.get("final_verification_status") == "blocked_conflict":
        return "source_conflict_hide_from_rx"
    disease_blob = (row.get("disease_key", "") + " " + row.get("disease_name", "")).lower()
    if any(token in disease_blob for token in ["viral", "dry_eye", "allergic_rhinitis", "allergic_conjunctivitis"]):
        if "antibiotic" in (row.get("old_runtime_status", "") + row.get("blocked_reason", "")).lower():
            return "not_recommended_for_this_disease"
    if row.get("product_id"):
        return "source_missing_hide_from_rx"
    return "catalog_hidden_from_rx"


def build_gold_tables() -> dict[str, int]:
    products = export_sheet("1_Product_Master_Export")
    regimens = export_sheet("2_Regimen_Master_Export", source_refreshed=True)
    peds = export_sheet("6_Pediatric_Dosing", source_refreshed=True)
    antibiotics = export_sheet("7_Antibiotic_Rows", source_refreshed=True)
    citations = evidence_claims()

    product_gold = []
    for row in products:
        product_gold.append(
            {
                "product_id": row.get("product_id", ""),
                "product_name": row.get("brand_name", ""),
                "generic_name": row.get("generic_name", ""),
                "composition": row.get("composition", ""),
                "strength": row.get("strength", ""),
                "form": row.get("dosage_form", ""),
                "route": row.get("route", ""),
                "pack": row.get("pack", ""),
                "price": row.get("price", ""),
                "brand_aliases": [row.get("brand_name", "")],
                "generic_aliases": [row.get("generic_name", ""), row.get("composition", "")],
                "workbook_source_file": "exports/refresh_csv/1_Product_Master_Export.csv",
                "workbook_source_sheet": "Drug_Master_Lookup",
                "local_thai_registration_found": False,
                "product_metadata_source_ids": [],
                "source_status": "source_missing",
                "reference_only_allowed": True,
                "rx_eligible": False,
                "notes": "Workbook inventory seed only; product metadata not gold verified in Phase 1.",
            }
        )

    regimen_gold = []
    for idx, row in enumerate(regimens):
        status = status_for_regimen(row)
        regimen_gold.append(
            {
                "gold_regimen_row_id": stable_id("gold_regimen", idx, row.get("regimen_id"), row.get("product_id"), row.get("role")),
                "regimen_id": row.get("regimen_id", ""),
                "disease_key": row.get("disease_key", ""),
                "disease_name": row.get("disease_name", ""),
                "icd10": row.get("ICD10", ""),
                "product_id": row.get("product_id", ""),
                "generic_name": row.get("composition") or row.get("drug_name", ""),
                "line_of_therapy": row.get("tier", ""),
                "modality": row.get("role", ""),
                "adult_dose": row.get("sig", ""),
                "adult_route": "",
                "adult_frequency": "",
                "adult_duration": row.get("duration", ""),
                "adult_max_dose": "",
                "indication_verified": False,
                "dose_verified": False,
                "route_verified": False,
                "frequency_verified": False,
                "duration_verified": False,
                "safety_minimum_ready": False,
                "source_ids": [s for s in str(row.get("source_ids", "")).split(";") if s.strip()],
                "final_rx_status": status,
            }
        )

    peds_gold = []
    for row in peds:
        peds_gold.append(
            {
                "pediatric_rule_id": stable_id("peds", row.get("product_id"), row.get("generic_key")),
                "product_id": row.get("product_id", ""),
                "generic_name": row.get("generic_key") or row.get("display_name", ""),
                "disease_key": "",
                "age_min_months": "",
                "age_max_months": "",
                "weight_min_kg": "",
                "weight_max_kg": "",
                "dose_basis": row.get("dose_basis", ""),
                "dose_min_mg_per_kg": "",
                "dose_max_mg_per_kg": "",
                "fixed_dose": "",
                "frequency": "",
                "duration": "",
                "max_mg_per_dose": row.get("max_dose", ""),
                "max_mg_per_day": "",
                "product_concentration": row.get("concentration", ""),
                "calculation_formula": "",
                "volume_formula": "",
                "rounding_rule": "",
                "contraindicated_age": "",
                "pediatric_formula_ready": False,
                "source_ids": [],
                "final_pediatric_status": "source_missing_hide_from_rx",
            }
        )

    antibiotic_gold = []
    for idx, row in enumerate(antibiotics):
        disease = (row.get("disease_key", "") + " " + row.get("disease_name", "")).lower()
        no_antibiotic = any(token in disease for token in ["viral", "allergic", "dry_eye", "simple", "watery"])
        antibiotic_gold.append(
            {
                "antibiotic_gate_id": stable_id("abx", idx, row.get("regimen_id"), row.get("product_id"), row.get("disease_key")),
                "product_id": row.get("product_id", ""),
                "generic_name": row.get("composition") or row.get("drug_name", ""),
                "disease_key": row.get("disease_key", ""),
                "bacterial_criteria_required": True,
                "criteria_text": "",
                "not_for_viral_use": no_antibiotic,
                "line_of_therapy": row.get("tier", ""),
                "duration_rule": row.get("duration", ""),
                "allergy_alternative": "",
                "avoid_if": "",
                "pregnancy_caution": "",
                "pediatric_caution": "",
                "renal_caution": "",
                "major_interactions": "",
                "gate_logic": "",
                "antibiotic_gate_ready": False,
                "source_ids": [],
                "final_antibiotic_status": "not_recommended_for_this_disease" if no_antibiotic else "source_missing_hide_from_rx",
            }
        )

    safety_gold = []
    for row in products:
        safety_gold.append(
            {
                "safety_id": stable_id("safe", row.get("product_id")),
                "product_id": row.get("product_id", ""),
                "generic_name": row.get("generic_name", ""),
                "contraindications": row.get("contraindication", ""),
                "precautions": row.get("caution", ""),
                "common_side_effects": row.get("side_effect", ""),
                "serious_side_effects": "",
                "major_interactions": "",
                "pregnancy_lactation": row.get("pregnancy_lactation", ""),
                "pediatric_notes": "",
                "renal_notes": "",
                "hepatic_notes": "",
                "red_flag_referral": "",
                "safety_source_level": "workbook_seed_only",
                "safety_ready": False,
                "source_ids": [],
            }
        )

    aliases = []
    for row in products:
        for alias, alias_type in [(row.get("brand_name", ""), "brand"), (row.get("generic_name", ""), "generic"), (row.get("composition", ""), "composition")]:
            if alias:
                aliases.append({"alias_id": stable_id("alias", row.get("product_id"), alias_type, alias), "product_id": row.get("product_id", ""), "alias": alias, "alias_type": alias_type, "language": "mixed", "target_type": "product", "target_id": row.get("product_id", "")})

    citation_gold = []
    for claim in citations:
        citation_gold.append(
            {
                "source_id": claim.get("source_id", ""),
                "source_title": claim.get("source_title", ""),
                "source_org": claim.get("source_org", ""),
                "source_url": claim.get("source_url", ""),
                "source_type": claim.get("source_type", ""),
                "source_country_or_region": "",
                "access_date": today(),
                "evidence_field": claim.get("evidence_field", ""),
                "evidence_snippet": claim.get("evidence_snippet", ""),
                "confidence": claim.get("confidence", ""),
                "linked_row_id": claim.get("claim_id", ""),
                "linked_product_id": claim.get("linked_product_id", ""),
                "linked_regimen_id": claim.get("linked_regimen_id", ""),
                "linked_disease_key": claim.get("linked_disease_key", ""),
            }
        )

    for filename, payload in {
        "product_master_gold.json": {"items": product_gold},
        "disease_regimen_gold.json": {"items": regimen_gold},
        "pediatric_dose_engine.json": {"items": peds_gold},
        "antibiotic_gate_map.json": {"items": antibiotic_gold},
        "safety_profile_gold.json": {"items": safety_gold},
        "search_alias_index.json": {"items": aliases},
        "source_citations_gold.json": {"items": citation_gold},
    }.items():
        write_json(DATA_GOLD / filename, payload)

    return {
        "products": len(product_gold),
        "regimens": len(regimen_gold),
        "pediatric": len(peds_gold),
        "antibiotics": len(antibiotic_gold),
        "safety": len(safety_gold),
        "aliases": len(aliases),
        "citations": len(citation_gold),
    }


def build_rx_eligibility() -> dict[str, int]:
    regimens = read_json(DATA_GOLD / "disease_regimen_gold.json", {"items": []}).get("items", [])
    products = read_json(DATA_GOLD / "product_master_gold.json", {"items": []}).get("items", [])
    rx_now_ready = [r for r in regimens if r.get("final_rx_status") in {"gold_ready_adult", "gold_ready_pediatric", "gold_ready_conditional"}]
    swaps_ready = [r for r in regimens if r.get("final_rx_status") in {"gold_ready_adult", "gold_ready_pediatric", "gold_ready_conditional", "conditional_use_when_criteria_met"}]
    reference_only = [p for p in products if p.get("reference_only_allowed") and not p.get("rx_eligible")]
    blocked = [r for r in regimens if r.get("final_rx_status") in {"source_conflict_hide_from_rx", "absolute_block", "not_recommended_for_this_disease"}]
    not_ready = [r for r in regimens if r.get("final_rx_status") in {"source_missing_hide_from_rx", "catalog_hidden_from_rx", "use_with_warning"}]
    payload = {
        "feature_flag": "USE_GOLD_RX_ENGINE",
        "default_enabled": False,
        "rx_now_ready": rx_now_ready,
        "swaps_ready": swaps_ready,
        "reference_only_products": reference_only,
        "blocked_rows": blocked,
        "not_ready_rows": not_ready,
        "rules": {
            "rx_now_requires_source_citation": True,
            "source_missing_hidden_from_rx": True,
            "source_conflict_hidden_from_rx": True,
            "catalog_only_hidden_from_prescribing": True,
        },
    }
    write_json(DATA_GOLD / "rx_eligibility_map.json", payload)
    write_json(DATA_GOLD / "gold_runtime_config.json", {"USE_GOLD_RX_ENGINE": False, "fallback_to_legacy_runtime": True, "overlay_path": "gold/rx_eligibility_map.json"})
    for base in [DATA_GOLD / "review", DIST_GOLD / "review"]:
        write_csv(base / "rx_now_ready_rows.csv", rx_now_ready)
        write_csv(base / "swaps_ready_rows.csv", swaps_ready)
        write_csv(base / "reference_only_rows.csv", reference_only)
        write_csv(base / "blocked_rows.csv", blocked)
        write_csv(base / "not_ready_rows.csv", not_ready)
    return {"rx_now_ready": len(rx_now_ready), "swaps_ready": len(swaps_ready), "reference_only": len(reference_only), "blocked": len(blocked), "not_ready": len(not_ready)}


def validation_errors() -> list[str]:
    errors: list[str] = []
    products = read_json(DATA_GOLD / "product_master_gold.json", {"items": []}).get("items", [])
    regimens = read_json(DATA_GOLD / "disease_regimen_gold.json", {"items": []}).get("items", [])
    peds = read_json(DATA_GOLD / "pediatric_dose_engine.json", {"items": []}).get("items", [])
    antibiotics = read_json(DATA_GOLD / "antibiotic_gate_map.json", {"items": []}).get("items", [])
    safety = read_json(DATA_GOLD / "safety_profile_gold.json", {"items": []}).get("items", [])
    aliases = read_json(DATA_GOLD / "search_alias_index.json", {"items": []}).get("items", [])
    citations = read_json(DATA_GOLD / "source_citations_gold.json", {"items": []}).get("items", [])
    rx = read_json(DATA_GOLD / "rx_eligibility_map.json", {})
    source_ids = {c.get("source_id") for c in citations if c.get("source_id")}
    safety_products = {s.get("product_id") for s in safety}
    alias_products = {a.get("product_id") for a in aliases}
    for table_name, rows, key in [
        ("product", products, "product_id"),
        ("regimen", regimens, "gold_regimen_row_id"),
        ("pediatric", peds, "pediatric_rule_id"),
        ("antibiotic", antibiotics, "antibiotic_gate_id"),
        ("safety", safety, "safety_id"),
    ]:
        ids = [row.get(key) for row in rows if row.get(key)]
        if len(ids) != len(set(ids)):
            errors.append(f"duplicate_{table_name}_ids")
    for row in regimens:
        status = row.get("final_rx_status")
        if status not in ALLOWED_FINAL_STATUSES:
            errors.append(f"invalid_regimen_status:{status}")
        if status in {"gold_ready_adult", "gold_ready_pediatric", "gold_ready_conditional"}:
            if not row.get("source_ids"):
                errors.append(f"rx_ready_without_source:{row.get('regimen_id')}")
            if not all(row.get(field) for field in ["adult_dose", "adult_duration"]):
                errors.append(f"rx_ready_missing_dose_duration:{row.get('regimen_id')}")
            if not row.get("safety_minimum_ready"):
                errors.append(f"rx_ready_without_safety:{row.get('regimen_id')}")
            if row.get("product_id") not in safety_products:
                errors.append(f"rx_ready_product_without_safety_row:{row.get('product_id')}")
            if row.get("product_id") not in alias_products:
                errors.append(f"rx_ready_product_without_alias:{row.get('product_id')}")
    for row in rx.get("rx_now_ready", []):
        if row.get("final_rx_status") in {"source_missing_hide_from_rx", "source_conflict_hide_from_rx", "catalog_hidden_from_rx", "absolute_block"}:
            errors.append(f"hidden_status_in_rx_now:{row.get('regimen_id')}")
        if not row.get("source_ids") or not any(sid in source_ids for sid in row.get("source_ids", [])):
            errors.append(f"rx_now_without_citation:{row.get('regimen_id')}")
    for row in peds:
        if row.get("final_pediatric_status") == "gold_ready_pediatric" and not row.get("pediatric_formula_ready"):
            errors.append(f"peds_ready_without_formula:{row.get('pediatric_rule_id')}")
        if row.get("pediatric_formula_ready") and not row.get("product_concentration"):
            errors.append(f"peds_formula_blank_concentration:{row.get('pediatric_rule_id')}")
    for row in antibiotics:
        if row.get("final_antibiotic_status") in {"gold_ready_conditional", "conditional_use_when_criteria_met"} and not row.get("antibiotic_gate_ready"):
            errors.append(f"antibiotic_ready_without_gate:{row.get('antibiotic_gate_id')}")
    if not products or not regimens:
        errors.append("unexpected_empty_gold_tables")
    return errors


def validate_gold() -> int:
    errors = validation_errors()
    rx = read_json(DATA_GOLD / "rx_eligibility_map.json", {})
    peds = read_json(DATA_GOLD / "pediatric_dose_engine.json", {"items": []}).get("items", [])
    antibiotics = read_json(DATA_GOLD / "antibiotic_gate_map.json", {"items": []}).get("items", [])
    lines = [
        f"- Pass: {not errors}",
        f"- Errors: {len(errors)}",
        f"- RX NOW ready rows: {len(rx.get('rx_now_ready', []))}",
        f"- SWAPS ready rows: {len(rx.get('swaps_ready', []))}",
        f"- Reference-only products: {len(rx.get('reference_only_products', []))}",
        f"- Hidden/not-ready rows: {len(rx.get('not_ready_rows', []))}",
        f"- Blocked rows: {len(rx.get('blocked_rows', []))}",
        f"- Pediatric formula-ready rows: {sum(1 for row in peds if row.get('pediatric_formula_ready'))}",
        f"- Antibiotic gate-ready rows: {sum(1 for row in antibiotics if row.get('antibiotic_gate_ready'))}",
        *(f"- {error}" for error in errors[:100]),
    ]
    write_report(REPORT_GOLD / "gold_validation_report.md", "Gold Validation Report", lines)
    print(f"gold_validate: pass={not errors} errors={len(errors)}")
    return 1 if errors else 0


def gap_reports() -> None:
    peds = read_json(DATA_GOLD / "pediatric_dose_engine.json", {"items": []}).get("items", [])
    antibiotics = read_json(DATA_GOLD / "antibiotic_gate_map.json", {"items": []}).get("items", [])
    safety = read_json(DATA_GOLD / "safety_profile_gold.json", {"items": []}).get("items", [])
    regimens = read_json(DATA_GOLD / "disease_regimen_gold.json", {"items": []}).get("items", [])
    write_csv(REPORT_GOLD / "pediatric_formula_gap_report.csv", [{**row, "missing_fields": "source; age/BW; dose formula; max dose; concentration/rounding as applicable"} for row in peds if not row.get("pediatric_formula_ready")])
    write_csv(REPORT_GOLD / "antibiotic_gate_gap_report.csv", [{**row, "missing_fields": "bacterial criteria; source-backed dose; duration; safety gate"} for row in antibiotics if not row.get("antibiotic_gate_ready")])
    write_csv(REPORT_GOLD / "safety_gap_report.csv", [{**row, "missing_fields": "source-backed contraindications; interactions; side effects; pregnancy/renal/hepatic cautions"} for row in safety if not row.get("safety_ready")])
    write_csv(REPORT_GOLD / "conflict_report.csv", [row for row in regimens if row.get("final_rx_status") == "source_conflict_hide_from_rx"])
    write_csv(REPORT_GOLD / "evidence_extraction_report.csv", evidence_claims())


def copy_gold_to_dist() -> None:
    (DIST_GOLD / "review").mkdir(parents=True, exist_ok=True)
    for filename in GOLD_JSON_FILES:
        source = DATA_GOLD / filename
        if source.exists():
            shutil.copy2(source, DIST_GOLD / filename)
    for filename in REVIEW_FILES:
        source = DIST_GOLD / "review" / filename
        if not source.exists():
            write_csv(source, [])


def export_bundle() -> Path:
    date_part = datetime.now().strftime("%Y%m%d")
    bundle = EXPORTS / f"Druglist_Gold_Source_Acquisition_Output_{date_part}.zip"
    if bundle.exists():
        bundle.unlink()
    readme = REPORT_GOLD / "README_FOR_CODEX_IMPORT.md"
    readme.write_text(
        "# Druglist Gold Import Bundle\n\n"
        "Rows are RX eligible only when exact source-backed evidence passes the validator. "
        "Incomplete rows are hidden from prescribing output.\n",
        encoding="utf-8",
    )
    import_instructions = REPORT_GOLD / "import_instructions.md"
    import_instructions.write_text(
        "# Import Instructions\n\n"
        "1. Run `python3 scripts/gold/run_gold_pipeline.py`.\n"
        "2. Run `python3 scripts/gold/09_validate_gold_readiness.py`.\n"
        "3. Only after review, run `python3 scripts/gold/promote_gold_overlay_to_runtime.py`.\n",
        encoding="utf-8",
    )
    patch_summary = REPORT_GOLD / "patch_summary.json"
    write_json(patch_summary, {"created_at": now_iso(), "phase": "gold_phase_1", "promotion_run": False})
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename in GOLD_JSON_FILES:
            path = DATA_GOLD / filename
            if path.exists():
                zf.write(path, f"import_ready/{filename}")
        for filename in REVIEW_FILES:
            path = DATA_GOLD / "review" / filename
            if path.exists():
                zf.write(path, f"review/{filename}")
        for extra in [
            REPORT_GOLD / "source_acquisition_queue.csv",
            REPORT_GOLD / "pediatric_formula_gap_report.csv",
            REPORT_GOLD / "antibiotic_gate_gap_report.csv",
            REPORT_GOLD / "safety_gap_report.csv",
            REPORT_GOLD / "conflict_report.csv",
            REPORT_GOLD / "gold_validation_report.md",
            readme,
            import_instructions,
            patch_summary,
            REPORT_GOLD / "current_repo_mapping.md",
            REPORT_GOLD / "source_file_discovery_report.md",
            REPORT_GOLD / "workbook_extraction_report.md",
            REPORT_GOLD / "gold_pipeline_final_summary.md",
        ]:
            if extra.exists():
                root_name = "codex" if extra.name in {"README_FOR_CODEX_IMPORT.md", "import_instructions.md", "patch_summary.json"} else "reports"
                if extra.name in {"source_acquisition_queue.csv", "pediatric_formula_gap_report.csv", "antibiotic_gate_gap_report.csv", "safety_gap_report.csv", "conflict_report.csv", "gold_validation_report.md"}:
                    root_name = "review"
                zf.write(extra, f"{root_name}/{extra.name}")
    return bundle


def final_summary(selected: dict[str, Any], query_count: int, counts: dict[str, int], rx_counts: dict[str, int], bundle: Path) -> None:
    source_count = len(source_records())
    evidence_count = len(evidence_claims())
    conflicts = len(read_csv(REPORT_GOLD / "conflict_report.csv"))
    acquisition_queue = len(read_csv(REPORT_GOLD / "source_acquisition_queue.csv"))
    lines = [
        "Rows are RX eligible only when exact source-backed evidence passes the validator. Incomplete rows are hidden from prescribing output.",
        f"- Workbook used: `{selected.get('selected_workbook') or 'none_found'}`",
        f"- Products found: {counts.get('products', 0)}",
        f"- Draft regimen rows found: {counts.get('regimens', 0)}",
        f"- Source queries generated: {query_count}",
        f"- Accredited source metadata available: {source_count}",
        f"- Evidence fields extracted: {evidence_count}",
        f"- RX NOW ready count: {rx_counts.get('rx_now_ready', 0)}",
        f"- SWAPS ready count: {rx_counts.get('swaps_ready', 0)}",
        f"- Pediatric formula-ready count: {sum(1 for row in read_json(DATA_GOLD / 'pediatric_dose_engine.json', {'items': []}).get('items', []) if row.get('pediatric_formula_ready'))}",
        f"- Antibiotic gate-ready count: {sum(1 for row in read_json(DATA_GOLD / 'antibiotic_gate_map.json', {'items': []}).get('items', []) if row.get('antibiotic_gate_ready'))}",
        f"- Reference-only count: {rx_counts.get('reference_only', 0)}",
        f"- Hidden/not-ready count: {rx_counts.get('not_ready', 0)}",
        f"- Conflict count: {conflicts}",
        f"- Source acquisition queue count: {acquisition_queue}",
        f"- Output bundle: `{bundle.relative_to(ROOT)}`",
        "- Promotion was not run.",
        "- Next command: `python3 scripts/gold/run_gold_pipeline.py && python3 scripts/gold/09_validate_gold_readiness.py`",
    ]
    write_report(REPORT_GOLD / "gold_pipeline_final_summary.md", "Gold Pipeline Final Summary", lines)


def run_pipeline() -> dict[str, Any]:
    ensure_dirs()
    selected = discover_workbook()
    repo_mapping()
    workbook_extraction_report(selected)
    queries = build_queries()
    write_csv(REPORT_GOLD / "source_acquisition_queue.csv", [dict(row, retrieval_status="queued") for row in queries])
    write_csv(REPORT_GOLD / "evidence_extraction_report.csv", evidence_claims())
    sources = source_records()
    write_json(DATA_GOLD / "source_citations_gold.json", {"items": []})
    counts = build_gold_tables()
    rx_counts = build_rx_eligibility()
    gap_reports()
    copy_gold_to_dist()
    validation_code = validate_gold()
    bundle = export_bundle()
    final_summary(selected, len(queries), counts, rx_counts, bundle)
    return {
        "selected": selected,
        "query_count": len(queries),
        "sources": len(sources),
        "evidence_fields": len(evidence_claims()),
        "counts": counts,
        "rx_counts": rx_counts,
        "validation_code": validation_code,
        "bundle": str(bundle),
    }


def load_runtime_with_gold_overlay(use_gold: bool | None = None, gold_dir: Path | None = None) -> dict[str, Any]:
    if use_gold is None:
        use_gold = os.environ.get("USE_GOLD_RX_ENGINE", "false").lower() == "true"
    legacy = read_json("data/core/app_seed_runtime.json", {})
    if not use_gold:
        return {"engine": "legacy", "runtime": legacy, "gold_overlay": None}
    gold_dir = gold_dir or DATA_GOLD
    try:
        rx = read_json(gold_dir / "rx_eligibility_map.json", None)
        if not rx:
            raise ValueError("missing rx_eligibility_map")
        return {"engine": "gold", "runtime": legacy, "gold_overlay": rx}
    except Exception as exc:
        return {"engine": "legacy_fallback", "runtime": legacy, "gold_overlay": None, "fallback_reason": str(exc)}


def promote_gold_overlay_to_runtime() -> int:
    if validate_gold() != 0:
        print("gold promotion blocked: validation failed")
        return 2
    report = [
        "- Promotion mode: dry-run scaffold.",
        "- Phase 1 does not overwrite production runtime automatically.",
        "- To implement later, backup `data/core/`, copy only validator-approved RX eligibility maps, then rebuild frontend seed.",
    ]
    write_report(REPORT_GOLD / "gold_promotion_report.md", "Gold Promotion Report", report)
    print("gold promotion scaffold written; production runtime was not changed")
    return 0


def git_commit() -> str:
    try:
        result = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=True)
        return result.stdout.strip()
    except Exception:
        return ""
