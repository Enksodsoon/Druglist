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
import urllib.parse
import urllib.request
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
ACCEPTED_EVIDENCE = ROOT / "imports/accepted_evidence"
PHASE2_BUNDLE_PREFIX = "Druglist_Gold_All_Drug_Accredited_Sweep_Output"

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
    "all_drug_accredited_sweep.json",
]

REVIEW_FILES = [
    "rx_now_ready_rows.csv",
    "swaps_ready_rows.csv",
    "reference_only_rows.csv",
    "blocked_rows.csv",
    "not_ready_rows.csv",
]

COMMON_OPD_DISEASE_TOKENS = {
    "allergic_rhinitis",
    "uri",
    "pharyngitis",
    "sore",
    "cough",
    "diarrhea",
    "gastroenteritis",
    "gerd",
    "dyspepsia",
    "constipation",
    "dry_eye",
    "conjunctivitis",
    "tinea",
    "dermatitis",
    "aphthous",
}

ADAPTER_NAMES = [
    "dailymed_adapter",
    "msf_adapter",
    "nice_bnf_query_adapter",
    "cdc_guideline_adapter",
    "nice_guideline_adapter",
    "thai_fda_query_adapter",
    "thai_ndi_query_adapter",
    "who_formulary_query_adapter",
    "local_evidence_cache_adapter",
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
        ACCEPTED_EVIDENCE,
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
    records.extend(phase2_sources())
    records.extend(PEDIATRIC_SOURCE_RECORDS)
    records.extend(accredited_sweep_sources())
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
                    "source_type": item.get("source_type") or "guideline_or_label",
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
    for item in phase2_claims():
        snippet = item.get("evidence_snippet") or ""
        if not snippet:
            continue
        claims.append(
            {
                "claim_id": item.get("claim_id") or stable_id("claim", "phase2", item.get("source_id"), item.get("evidence_field"), snippet[:80]),
                "source_id": item.get("source_id", ""),
                "source_title": item.get("source_title", ""),
                "source_org": item.get("source_org", ""),
                "source_url": item.get("source_url", ""),
                "source_type": item.get("source_type") or "official_product_label",
                "source_country_or_region": item.get("source_country_or_region", ""),
                "evidence_field": item.get("evidence_field", ""),
                "evidence_snippet": snippet[:700],
                "confidence": item.get("confidence", ""),
                "linked_product_id": item.get("linked_product_id", ""),
                "linked_regimen_id": item.get("linked_regimen_id", ""),
                "linked_disease_key": item.get("linked_disease_key", ""),
                "linked_generic_name": item.get("linked_generic_name", ""),
                "status": "phase2_accepted",
            }
        )
    claims.extend(pediatric_formula_claims())
    claims.extend(accredited_sweep_claims())
    return claims


def claims_by_product_disease() -> dict[tuple[str, str], dict[str, list[dict[str, Any]]]]:
    grouped: dict[tuple[str, str], dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for claim in evidence_claims():
        product_id = str(claim.get("linked_product_id") or "")
        disease_key = str(claim.get("linked_disease_key") or "")
        if product_id and disease_key:
            grouped[(product_id, disease_key)][str(claim.get("evidence_field") or "")].append(claim)
    return grouped


def claims_by_product() -> dict[str, dict[str, list[dict[str, Any]]]]:
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for claim in evidence_claims():
        product_id = str(claim.get("linked_product_id") or "")
        if product_id:
            grouped[product_id][str(claim.get("evidence_field") or "")].append(claim)
    return grouped


def first_claim(group: dict[str, list[dict[str, Any]]], field: str) -> dict[str, Any]:
    return (group.get(field) or [{}])[0]


def claim_value(group: dict[str, list[dict[str, Any]]], field: str, fallback: str = "") -> str:
    claim = first_claim(group, field)
    return str(claim.get("evidence_value") or fallback or claim.get("evidence_snippet") or "")


def has_fields(group: dict[str, list[dict[str, Any]]], fields: list[str]) -> bool:
    return all(group.get(field) and group[field][0].get("evidence_snippet") for field in fields)


ADULT_REQUIRED_FIELDS = [
    "adult_indication",
    "adult_dose",
    "adult_route",
    "adult_frequency",
    "adult_duration",
    "adult_max_dose",
    "contraindication",
    "precaution",
    "common_side_effect",
    "major_interaction",
    "pregnancy_lactation",
    "composition_strength_form_route",
]


def source_ids_for_claim_group(group: dict[str, list[dict[str, Any]]]) -> list[str]:
    return sorted({claim.get("source_id", "") for claims in group.values() for claim in claims if claim.get("source_id")})


PEDIATRIC_SOURCE_RECORDS = [
    {
        "source_id": "msf_paracetamol_oral_peds_2024",
        "source_title": "PARACETAMOL = ACETAMINOPHEN oral",
        "source_org": "MSF Medical Guidelines",
        "source_url": "https://medicalguidelines.msf.org/es/viewport/EssDr/spanish/paracetamol-acetaminofen-oral-22282995.html",
        "access_date": today(),
        "source_type": "authoritative_formulary",
        "source_country_or_region": "International",
        "adapter_name": "msf_adapter",
        "retrieval_status": "retrieved",
        "extraction_status": "field_snippets_extracted",
    },
    {
        "source_id": "msf_ibuprofen_oral_peds_2024",
        "source_title": "IBUPROFEN oral",
        "source_org": "MSF Medical Guidelines",
        "source_url": "https://medicalguidelines.msf.org/en/viewport/EssDr/english/ibuprofen-oral-16683877.html",
        "access_date": today(),
        "source_type": "authoritative_formulary",
        "source_country_or_region": "International",
        "adapter_name": "msf_adapter",
        "retrieval_status": "retrieved",
        "extraction_status": "field_snippets_extracted",
    },
    {
        "source_id": "msf_ors_peds_2024",
        "source_title": "ORAL REHYDRATION SALTS = ORS",
        "source_org": "MSF Medical Guidelines",
        "source_url": "https://medicalguidelines.msf.org/es/viewport/EssDr/spanish/sales-de-rehidratacion-oral-sro-ors-22283024.html?language_content_entity=en",
        "access_date": today(),
        "source_type": "authoritative_formulary",
        "source_country_or_region": "International",
        "adapter_name": "msf_adapter",
        "retrieval_status": "retrieved",
        "extraction_status": "field_snippets_extracted",
    },
]


def pediatric_formula_claims() -> list[dict[str, Any]]:
    snippets = {
        "paracetamol": {
            "source_id": "msf_paracetamol_oral_peds_2024",
            "source_title": "PARACETAMOL = ACETAMINOPHEN oral",
            "source_url": "https://medicalguidelines.msf.org/es/viewport/EssDr/spanish/paracetamol-acetaminofen-oral-22282995.html",
            "generic_name": "paracetamol",
            "snippet": "Children under 1 month: 10 mg/kg 3 or 4 times daily (max. 40 mg/kg daily). Children 1 month and over: 15 mg/kg 3 or 4 times daily (max. 60 mg/kg daily).",
        },
        "ibuprofen": {
            "source_id": "msf_ibuprofen_oral_peds_2024",
            "source_title": "IBUPROFEN oral",
            "source_url": "https://medicalguidelines.msf.org/en/viewport/EssDr/english/ibuprofen-oral-16683877.html",
            "generic_name": "ibuprofen",
            "snippet": "Child over 3 months: 5 to 10 mg/kg 3 to 4 times daily (max. 30 mg/kg daily). 100 mg/5 ml oral suspension, with pipette graduated per kg of body weight.",
        },
        "ors": {
            "source_id": "msf_ors_peds_2024",
            "source_title": "ORAL REHYDRATION SALTS = ORS",
            "source_url": "https://medicalguidelines.msf.org/es/viewport/EssDr/spanish/sales-de-rehidratacion-oral-sro-ors-22283024.html?language_content_entity=en",
            "generic_name": "oral rehydration salts",
            "snippet": "Prevention: child under 24 months 50 to 100 ml after each loose stool; 2 to 10 years 100 to 200 ml; over 10 years and adult 200 to 400 ml. Moderate dehydration: ORS volumes by age/weight over the first four hours.",
        },
    }
    rows = []
    for key, item in snippets.items():
        for field in [
            "pediatric_indication",
            "pediatric_age_range",
            "pediatric_weight_rule",
            "pediatric_dose_formula",
            "pediatric_frequency",
            "pediatric_duration",
            "pediatric_max_dose",
            "pediatric_safety",
        ]:
            rows.append(
                {
                    "claim_id": f"claim_{item['source_id']}_{field}",
                    "source_id": item["source_id"],
                    "source_title": item["source_title"],
                    "source_org": "MSF Medical Guidelines",
                    "source_url": item["source_url"],
                    "source_type": "authoritative_formulary",
                    "source_country_or_region": "International",
                    "evidence_field": field,
                    "evidence_snippet": item["snippet"],
                    "confidence": 0.92,
                    "linked_product_id": "",
                    "linked_regimen_id": "",
                    "linked_disease_key": "pediatric_formula",
                    "linked_generic_name": item["generic_name"],
                    "status": "pediatric_formula_source_accepted",
                }
            )
    return rows


def parsed_concentration_mg_per_ml(value: str) -> float | None:
    try:
        payload = json.loads(value or "{}")
        if payload.get("unit") == "mg_per_ml" and not payload.get("manual_review"):
            return float(payload.get("value"))
    except Exception:
        return None
    return None


SAFETY_PHRASES = {
    "contraindication": [
        "do not use",
        "contraindications",
        "contraindicated",
    ],
    "precaution": [
        "ask a doctor before use",
        "warnings",
        "precautions",
    ],
    "common_side_effect": [
        "adverse reactions",
        "side effects",
        "stop use and ask a doctor",
    ],
    "major_interaction": [
        "drug interactions",
        "ask a doctor or pharmacist before use if you are",
        "taking",
    ],
    "pregnancy_lactation": [
        "pregnant or breast-feeding",
        "pregnancy",
        "lactation",
    ],
    "composition_strength_form_route": [
        "active ingredient",
        "dosage forms and strengths",
        "description",
    ],
}


def normalized_generic(value: str) -> str:
    text = (value or "").lower()
    text = re.sub(r"\b(hcl|hydrochloride|sodium|potassium|dihydrochloride|maleate|besylate|furoate|monohydrate)\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def strength_tokens(row: dict[str, str]) -> list[str]:
    text = " ".join([row.get("strength", ""), row.get("composition", ""), row.get("generic_name", "")]).lower()
    tokens = []
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*(mg|mcg|g|%|iu|unit|units|ml)", text):
        token = f"{match.group(1).rstrip('0').rstrip('.') if '.' in match.group(1) else match.group(1)} {match.group(2)}"
        if token not in tokens:
            tokens.append(token)
    return tokens[:3]


def form_tokens(row: dict[str, str]) -> list[str]:
    text = " ".join([row.get("dosage_form", ""), row.get("route", ""), row.get("composition", "")]).lower()
    tokens = []
    for token in ["tablet", "caplet", "capsule", "syrup", "suspension", "cream", "ointment", "gel", "drops", "spray", "solution", "injection"]:
        if token in text:
            tokens.append(token)
    return tokens


def source_text_window(text: str, phrase: str, width: int = 520) -> str:
    idx = text.lower().find(phrase.lower())
    if idx < 0:
        return ""
    start = max(0, idx - width // 2)
    end = min(len(text), idx + width // 2)
    return re.sub(r"\s+", " ", text[start:end]).strip()[:700]


def fetch_url_text(url: str, timeout: int = 15, max_bytes: int = 2_500_000) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "DruglistGold/3.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read(max_bytes).decode("utf-8", errors="ignore")
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw)).strip()


def fetch_json_url(url: str, timeout: int = 15) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "DruglistGold/3.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="ignore"))


def run_full_accredited_source_sweep(products: list[dict[str, str]]) -> dict[str, int]:
    """Acquire official label snippets for every product where exact matching is possible.

    This is intentionally conservative: DailyMed product labels can support
    product metadata and safety snippets, but they do not by themselves unlock
    disease-specific Thai OPD regimen rows.
    """

    source_rows: list[dict[str, Any]] = []
    claim_rows: list[dict[str, Any]] = []
    rejection_rows: list[dict[str, Any]] = []
    task_rows: list[dict[str, Any]] = []
    text_cache: dict[str, str] = {}
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)

    for row in products:
        product_id = row.get("product_id", "")
        generic = row.get("generic_name") or row.get("composition") or ""
        generic_norm = normalized_generic(generic)
        if not product_id or not generic_norm or "+" in generic:
            continue
        primary = " ".join(generic_norm.split()[:3])
        if primary:
            groups[primary].append(row)

    max_groups = int(os.environ.get("GOLD_FULL_SWEEP_MAX_GROUPS", "10"))
    sorted_groups = sorted(groups.items(), key=lambda item: (-len(item[1]), item[0]))
    deferred_groups = sorted_groups[max_groups:]
    for primary, group_rows in deferred_groups:
        for row in group_rows:
            rejection_rows.append(
                {
                    "product_id": row.get("product_id", ""),
                    "generic_name": row.get("generic_name", ""),
                    "status": "deferred_acquisition_queue",
                    "reason": f"Automatic web retrieval capped at {max_groups} generic groups for this run; source query remains queued.",
                }
            )
    for primary, group_rows in sorted_groups[:max_groups]:
        query = urllib.parse.quote(primary)
        search_url = f"https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json?drug_name={query}&pagesize=1"
        task_rows.append(
            {
                "generic_group": primary,
                "product_count": len(group_rows),
                "source_target": "DailyMed official label",
                "query_url": search_url,
                "status": "searched",
                "expected_fields": "composition/strength/form/route; contraindications; precautions; adverse reactions; interactions; pregnancy/lactation",
            }
        )
        try:
            payload = fetch_json_url(search_url, timeout=4)
        except Exception as exc:
            for row in group_rows:
                rejection_rows.append({"product_id": row.get("product_id", ""), "generic_name": row.get("generic_name", ""), "status": "dailymed_search_failed", "reason": str(exc)})
            continue
        label_texts = []
        for candidate in (payload.get("data") or [])[:1]:
            setid = candidate.get("setid")
            if not setid:
                continue
            xml_url = f"https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/{setid}.xml"
            try:
                label_texts.append((candidate, text_cache.setdefault(setid, fetch_url_text(xml_url, timeout=4))))
            except Exception as exc:
                rejection_rows.append({"generic_group": primary, "source_url": xml_url, "status": "dailymed_label_fetch_failed", "reason": str(exc)})

        for row in group_rows:
            product_id = row.get("product_id", "")
            generic = row.get("generic_name") or row.get("composition") or ""
            generic_norm = normalized_generic(generic)
            matched = False
            for candidate, text in label_texts:
                setid = candidate.get("setid")
                title = candidate.get("title", "")
                text_lower = text.lower()
                generic_terms = [term for term in generic_norm.split() if len(term) >= 4][:2]
                generic_match = all(term in text_lower for term in generic_terms) if generic_terms else False
                strengths = strength_tokens(row)
                strength_match = not strengths or any(token in text_lower or token.replace(" ", "") in text_lower for token in strengths)
                forms = form_tokens(row)
                form_match = not forms or any(token in text_lower or token in title.lower() for token in forms)
                if not (generic_match and strength_match and form_match):
                    continue
                snippets: dict[str, str] = {}
                for field, phrases in SAFETY_PHRASES.items():
                    snippets[field] = ""
                    for phrase in phrases:
                        window = source_text_window(text, phrase)
                        if window:
                            snippets[field] = window
                            break
                missing = [field for field, snippet in snippets.items() if not snippet]
                if missing:
                    rejection_rows.append(
                        {
                            "product_id": product_id,
                            "generic_name": generic,
                            "source_title": title,
                            "source_url": f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={setid}",
                            "status": "label_matched_but_missing_required_safety_snippets",
                            "missing_fields": "; ".join(missing),
                        }
                    )
                    continue
                matched = True
                source_id = stable_id("dailymed", setid, product_id)
                source_url = f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={setid}"
                source_rows.append(
                    {
                        "source_id": source_id,
                        "source_title": title,
                        "source_org": "DailyMed / U.S. National Library of Medicine",
                        "source_url": source_url,
                        "access_date": today(),
                        "source_type": "official_product_label",
                        "source_country_or_region": "United States",
                        "adapter_name": "full_dailymed_accredited_sweep",
                        "retrieval_status": "retrieved",
                        "extraction_status": "field_snippets_extracted",
                        "linked_product_id": product_id,
                        "linked_generic_name": generic,
                    }
                )
                for field, snippet in snippets.items():
                    claim_rows.append(
                        {
                            "claim_id": stable_id("claim", source_id, product_id, field),
                            "source_id": source_id,
                            "source_title": title,
                            "source_org": "DailyMed / U.S. National Library of Medicine",
                            "source_url": source_url,
                            "source_type": "official_product_label",
                            "source_country_or_region": "United States",
                            "evidence_field": field,
                            "evidence_value": "source-backed product label field",
                            "evidence_snippet": snippet,
                            "confidence": 0.9,
                            "linked_product_id": product_id,
                            "linked_regimen_id": "",
                            "linked_disease_key": "",
                            "linked_generic_name": generic,
                            "adapter_name": "full_dailymed_accredited_sweep",
                            "product_match_status": "generic_strength_form_route_match",
                            "rx_unlock_scope": "product_safety_metadata_only",
                        }
                    )
                break
            if not matched:
                rejection_rows.append(
                    {
                        "product_id": product_id,
                        "generic_name": generic,
                        "status": "no_exact_dailymed_label_match",
                        "reason": "No accessible DailyMed result matched generic plus strength/form sufficiently for product-level acceptance.",
                    }
                )

    write_json(DATA_GOLD / "accredited_source_sweep_sources.json", {"items": source_rows})
    write_json(DATA_GOLD / "accredited_source_sweep_evidence.json", {"items": claim_rows})
    write_csv(REPORT_GOLD / "full_accredited_source_sweep_tasks.csv", task_rows)
    write_csv(REPORT_GOLD / "full_accredited_source_acceptance_report.csv", source_rows)
    write_csv(REPORT_GOLD / "full_accredited_source_rejection_report.csv", rejection_rows)
    return {
        "searched_products": sum(len(rows) for rows in groups.values()),
        "searched_generic_groups": len(groups),
        "accepted_sources": len(source_rows),
        "accepted_claims": len(claim_rows),
        "rejected_or_unmatched": len(rejection_rows),
    }


def accredited_sweep_claims() -> list[dict[str, Any]]:
    return read_json(DATA_GOLD / "accredited_source_sweep_evidence.json", {"items": []}).get("items", [])


def accredited_sweep_sources() -> list[dict[str, Any]]:
    return read_json(DATA_GOLD / "accredited_source_sweep_sources.json", {"items": []}).get("items", [])


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
    claim_groups = claims_by_product_disease()
    product_claim_groups = claims_by_product()
    phase2_product_sources = defaultdict(list)
    for claim in citations:
        if claim.get("linked_product_id") and claim.get("source_id"):
            phase2_product_sources[claim.get("linked_product_id")].append(claim.get("source_id"))

    product_gold = []
    for row in products:
        pid = row.get("product_id", "")
        metadata_sources = sorted({s for s in phase2_product_sources.get(pid, []) if s})
        product_gold.append(
            {
                "product_id": pid,
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
                "product_metadata_source_ids": metadata_sources,
                "source_status": "metadata_source_linked" if metadata_sources else "source_missing",
                "reference_only_allowed": True,
                "rx_eligible": bool(metadata_sources),
                "notes": "Gold product metadata linked to accepted official generic/product evidence; Thai brand registration remains separate unless Thai source is present." if metadata_sources else "Workbook inventory seed only; product metadata not gold verified.",
            }
        )

    regimen_gold = []
    for idx, row in enumerate(regimens):
        status = status_for_regimen(row)
        group = claim_groups.get((row.get("product_id", ""), row.get("disease_key", "")), {})
        if has_fields(group, ADULT_REQUIRED_FIELDS):
            status = "gold_ready_adult"
            source_ids = source_ids_for_claim_group(group)
            dose = claim_value(group, "adult_dose", row.get("sig", ""))
            route = claim_value(group, "adult_route", "PO")
            frequency = claim_value(group, "adult_frequency", "")
            duration = claim_value(group, "adult_duration", row.get("duration", ""))
            max_dose = claim_value(group, "adult_max_dose", "")
            flags = True
        else:
            source_ids = [s for s in str(row.get("source_ids", "")).split(";") if s.strip()]
            dose = row.get("sig", "")
            route = ""
            frequency = ""
            duration = row.get("duration", "")
            max_dose = ""
            flags = False
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
                "adult_dose": dose,
                "adult_route": route,
                "adult_frequency": frequency,
                "adult_duration": duration,
                "adult_max_dose": max_dose,
                "indication_verified": flags,
                "dose_verified": flags,
                "route_verified": flags,
                "frequency_verified": flags,
                "duration_verified": flags,
                "safety_minimum_ready": flags,
                "source_ids": source_ids,
                "final_rx_status": status,
            }
        )

    peds_gold = []
    for row in peds:
        generic = (row.get("generic_key") or row.get("display_name", "")).lower()
        concentration = parsed_concentration_mg_per_ml(row.get("concentration", ""))
        source_ids: list[str] = []
        formula_template_ready = False
        dose_basis = row.get("dose_basis", "")
        dose_min = ""
        dose_max = ""
        frequency = ""
        max_day = ""
        calculation_formula = ""
        volume_formula = ""
        rounding_rule = ""
        contraindicated_age = ""
        if "paracetamol" in generic and concentration:
            source_ids = ["msf_paracetamol_oral_peds_2024"]
            formula_template_ready = True
            dose_basis = "weight_based_mg_per_kg_per_dose_age_adjusted"
            dose_min = "10"
            dose_max = "15"
            frequency = "3 to 4 times daily"
            max_day = "40 mg/kg/day if age_months < 1; 60 mg/kg/day if age_months >= 1"
            calculation_formula = "if age_months < 1: dose_mg = 10 * weight_kg; else: dose_mg = 15 * weight_kg"
            volume_formula = f"dose_ml = dose_mg / {concentration:g}; concentration_mg_per_ml = {concentration:g}"
            rounding_rule = "display exact calculated mL to 0.1 mL; cap total daily dose by age-specific max_mg_per_day"
            contraindicated_age = "none stated by selected MSF source; reduce dose in severe acute malnutrition or dengue warning signs"
        elif "ibuprofen" in generic and concentration:
            source_ids = ["msf_ibuprofen_oral_peds_2024"]
            formula_template_ready = True
            dose_basis = "weight_based_mg_per_kg_per_dose_range"
            dose_min = "5"
            dose_max = "10"
            frequency = "3 to 4 times daily"
            max_day = "30 mg/kg/day"
            calculation_formula = "dose_min_mg = 5 * weight_kg; dose_max_mg = 10 * weight_kg; max_mg_per_day = 30 * weight_kg"
            volume_formula = f"dose_min_ml = dose_min_mg / {concentration:g}; dose_max_ml = dose_max_mg / {concentration:g}; concentration_mg_per_ml = {concentration:g}"
            rounding_rule = "display exact min-max mL range to 0.1 mL; do not exceed max_mg_per_day"
            contraindicated_age = "do not administer to children under 3 months"
        peds_gold.append(
            {
                "pediatric_rule_id": stable_id("peds", row.get("product_id"), row.get("generic_key")),
                "product_id": row.get("product_id", ""),
                "generic_name": row.get("generic_key") or row.get("display_name", ""),
                "disease_key": "",
                "age_min_months": "0" if "paracetamol" in generic and formula_template_ready else ("3" if "ibuprofen" in generic and formula_template_ready else ""),
                "age_max_months": "",
                "weight_min_kg": "",
                "weight_max_kg": "",
                "dose_basis": dose_basis,
                "dose_min_mg_per_kg": dose_min,
                "dose_max_mg_per_kg": dose_max,
                "fixed_dose": "",
                "frequency": frequency,
                "duration": "",
                "max_mg_per_dose": row.get("max_dose", ""),
                "max_mg_per_day": max_day,
                "product_concentration": row.get("concentration", ""),
                "calculation_formula": calculation_formula,
                "volume_formula": volume_formula,
                "rounding_rule": rounding_rule,
                "contraindicated_age": contraindicated_age,
                "formula_template_ready": formula_template_ready,
                "pediatric_formula_ready": False,
                "source_ids": source_ids,
                "final_pediatric_status": "source_missing_hide_from_rx",
                "pediatric_formula_block_reason": "formula source available but product concentration remains workbook-derived; needs accredited product label/concentration source" if formula_template_ready else "missing pediatric dose formula source and/or parsed concentration",
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
        pid = row.get("product_id", "")
        product_groups = [group for (product_id, _disease), group in claim_groups.items() if product_id == pid]
        product_only_group = product_claim_groups.get(pid, {})
        safety_group = product_only_group if has_fields(product_only_group, ["contraindication", "precaution", "common_side_effect", "major_interaction", "pregnancy_lactation"]) else next((group for group in product_groups if has_fields(group, ["contraindication", "precaution", "common_side_effect", "major_interaction", "pregnancy_lactation"])), {})
        safety_ready = bool(safety_group)
        safety_source_ids = source_ids_for_claim_group(safety_group) if safety_ready else []
        safety_gold.append(
            {
                "safety_id": stable_id("safe", row.get("product_id")),
                "product_id": pid,
                "generic_name": row.get("generic_name", ""),
                "contraindications": first_claim(safety_group, "contraindication").get("evidence_snippet", row.get("contraindication", "")),
                "precautions": first_claim(safety_group, "precaution").get("evidence_snippet", row.get("caution", "")),
                "common_side_effects": first_claim(safety_group, "common_side_effect").get("evidence_snippet", row.get("side_effect", "")),
                "serious_side_effects": "",
                "major_interactions": first_claim(safety_group, "major_interaction").get("evidence_snippet", ""),
                "pregnancy_lactation": first_claim(safety_group, "pregnancy_lactation").get("evidence_snippet", row.get("pregnancy_lactation", "")),
                "pediatric_notes": "",
                "renal_notes": "",
                "hepatic_notes": "",
                "red_flag_referral": "",
                "safety_source_level": "official_product_label" if safety_ready else "workbook_seed_only",
                "safety_ready": safety_ready,
                "source_ids": safety_source_ids,
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
                "source_country_or_region": claim.get("source_country_or_region", ""),
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
    rx_now_ready = [
        r for r in regimens
        if r.get("modality") == "RX NOW"
        and r.get("final_rx_status") in {"gold_ready_adult", "gold_ready_pediatric", "gold_ready_conditional"}
    ]
    swaps_ready = [
        r for r in regimens
        if r.get("modality") == "SWAP"
        and r.get("final_rx_status") in {"gold_ready_adult", "gold_ready_pediatric", "gold_ready_conditional", "conditional_use_when_criteria_met"}
    ]
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


def unique_coverage_reports() -> dict[str, int]:
    rx = read_json(DATA_GOLD / "rx_eligibility_map.json", {})
    ready = list(rx.get("rx_now_ready", []))
    swaps = list(rx.get("swaps_ready", []))
    all_ready = ready + swaps
    pair_counts = Counter((row.get("product_id", ""), row.get("disease_key", "")) for row in all_ready)
    duplicate_rows = sum(max(0, count - 1) for count in pair_counts.values())
    rows = []
    for row in all_ready:
        rows.append(
            {
                "output_bucket": "RX NOW" if row in ready else "SWAP",
                "product_id": row.get("product_id", ""),
                "generic_name": row.get("generic_name", ""),
                "disease_key": row.get("disease_key", ""),
                "regimen_id": row.get("regimen_id", ""),
                "final_rx_status": row.get("final_rx_status", ""),
                "source_ids": row.get("source_ids", []),
                "duplicate_product_disease_rows": pair_counts[(row.get("product_id", ""), row.get("disease_key", ""))],
            }
        )
    write_csv(REPORT_GOLD / "gold_unique_coverage_report.csv", rows)
    summary = {
        "rx_now_rows": len(ready),
        "swaps_rows": len(swaps),
        "unique_products_rx_ready": len({row.get("product_id") for row in all_ready if row.get("product_id")}),
        "unique_generic_names_rx_ready": len({row.get("generic_name") for row in all_ready if row.get("generic_name")}),
        "unique_disease_keys_rx_ready": len({row.get("disease_key") for row in all_ready if row.get("disease_key")}),
        "unique_product_disease_pairs_rx_ready": len(pair_counts),
        "duplicate_row_count": duplicate_rows,
    }
    write_report(
        REPORT_GOLD / "gold_unique_coverage_summary.md",
        "Gold Unique Coverage Summary",
        [f"- {key}: {value}" for key, value in summary.items()],
    )
    return summary


def product_match_gap_report() -> None:
    regimens = read_json(DATA_GOLD / "disease_regimen_gold.json", {"items": []}).get("items", [])
    claims = evidence_claims()
    evidence_generics = {str(claim.get("linked_generic_name", "")).lower() for claim in claims}
    rows = []
    for row in regimens:
        if row.get("final_rx_status") != "source_missing_hide_from_rx":
            continue
        generic = str(row.get("generic_name", "")).lower()
        reason = ""
        if "ibuprofen" in generic:
            reason = "DailyMed first-pack evidence found for 200 mg OTC ibuprofen label, but workbook row is 400 mg/combination or lacks exact strength/form match."
        elif any(token and token in generic for token in evidence_generics):
            reason = "Generic evidence exists, but this product/disease row lacks exact product, strength, form, route, or disease mapping evidence."
        elif any(token in generic for token in ["ambroxol", "bromhexine", "acetylcysteine", "racecadotril", "sodium chloride"]):
            reason = "High-priority OPD row still needs accredited source evidence and product-specific match."
        if reason:
            rows.append({**row, "product_match_gap_reason": reason})
    write_csv(REPORT_GOLD / "product_match_gap_report.csv", rows)


def all_drug_accredited_sweep_reports() -> dict[str, int]:
    products = read_json(DATA_GOLD / "product_master_gold.json", {"items": []}).get("items", [])
    regimens = read_json(DATA_GOLD / "disease_regimen_gold.json", {"items": []}).get("items", [])
    peds = read_json(DATA_GOLD / "pediatric_dose_engine.json", {"items": []}).get("items", [])
    antibiotics = read_json(DATA_GOLD / "antibiotic_gate_map.json", {"items": []}).get("items", [])
    rx = read_json(DATA_GOLD / "rx_eligibility_map.json", {})
    ready_pairs = {(row.get("product_id", ""), row.get("disease_key", "")) for row in rx.get("rx_now_ready", []) + rx.get("swaps_ready", [])}
    product_query_rows = read_csv(REPORT_GOLD / "source_acquisition_queue.csv")
    queries_by_product = defaultdict(list)
    for row in product_query_rows:
        if row.get("product_id"):
            queries_by_product[row["product_id"]].append(row.get("query", ""))

    product_rows = []
    for row in products:
        pid = row.get("product_id", "")
        source_ids = row.get("product_metadata_source_ids") or []
        verified = bool(source_ids)
        product_rows.append(
            {
                "product_id": pid,
                "product_name": row.get("product_name", ""),
                "generic_name": row.get("generic_name", ""),
                "composition": row.get("composition", ""),
                "form": row.get("form", ""),
                "route": row.get("route", ""),
                "gold_inventory_status": "in_gold_inventory",
                "accredited_source_status": "accredited_source_linked" if verified else "pending_accredited_source",
                "rx_eligible": row.get("rx_eligible", False),
                "source_ids": source_ids,
                "missing_accredited_fields": "" if verified else "product label or Thai registration source; safety fields; product strength/form/route confirmation",
                "next_action": "review linked citations before promotion" if verified else "retrieve accredited Thai FDA/NDI/SmPC/DailyMed/eMC source and extract field-level evidence",
                "query_count": len(queries_by_product.get(pid, [])),
                "sample_queries": queries_by_product.get(pid, [])[:3],
            }
        )

    regimen_rows = []
    for row in regimens:
        status = row.get("final_rx_status", "")
        ready = (row.get("product_id", ""), row.get("disease_key", "")) in ready_pairs and status.startswith("gold_ready")
        missing = []
        if not row.get("source_ids"):
            missing.append("source citation")
        if not row.get("indication_verified"):
            missing.append("indication")
        if not row.get("dose_verified"):
            missing.append("dose")
        if not row.get("route_verified"):
            missing.append("route")
        if not row.get("frequency_verified"):
            missing.append("frequency")
        if not row.get("duration_verified"):
            missing.append("duration")
        if not row.get("safety_minimum_ready"):
            missing.append("minimum safety")
        regimen_rows.append(
            {
                "gold_regimen_row_id": row.get("gold_regimen_row_id", ""),
                "regimen_id": row.get("regimen_id", ""),
                "product_id": row.get("product_id", ""),
                "generic_name": row.get("generic_name", ""),
                "disease_key": row.get("disease_key", ""),
                "modality": row.get("modality", ""),
                "final_rx_status": status,
                "accredited_source_status": "ready_source_verified" if ready else "pending_exact_accredited_evidence",
                "missing_accredited_fields": "; ".join(missing),
                "next_action": "eligible only through Gold overlay review" if ready else "find accepted source with exact indication/dose/route/frequency/duration/safety snippets",
            }
        )

    peds_rows = [
        {
            **row,
            "accredited_source_status": "pediatric_formula_ready" if row.get("pediatric_formula_ready") else "blocked_pending_complete_pediatric_source",
            "missing_accredited_fields": "" if row.get("pediatric_formula_ready") else "age/BW rule; dose formula; max dose; concentration; rounding; pediatric citation",
            "next_action": "ready for pediatric formula review" if row.get("pediatric_formula_ready") else "retrieve pediatric formulary/guideline and product concentration source",
        }
        for row in peds
    ]
    antibiotic_rows = [
        {
            **row,
            "accredited_source_status": "antibiotic_gate_ready" if row.get("antibiotic_gate_ready") else "blocked_pending_antibiotic_criteria_source",
            "missing_accredited_fields": "" if row.get("antibiotic_gate_ready") else "bacterial criteria; drug choice; dose; duration; gate logic; safety citation",
            "next_action": "ready for antibiotic gate review" if row.get("antibiotic_gate_ready") else "retrieve RDU/AWaRe/NICE/IDSA/Thai guideline with exact disease criteria and dosing",
        }
        for row in antibiotics
    ]

    write_csv(REPORT_GOLD / "all_drug_accredited_product_sweep.csv", product_rows)
    write_csv(REPORT_GOLD / "all_regimen_accredited_sweep.csv", regimen_rows)
    write_csv(REPORT_GOLD / "all_pediatric_accredited_sweep.csv", peds_rows)
    write_csv(REPORT_GOLD / "all_antibiotic_accredited_sweep.csv", antibiotic_rows)
    write_json(
        DATA_GOLD / "all_drug_accredited_sweep.json",
        {
            "products": product_rows,
            "regimens": regimen_rows,
            "pediatric": peds_rows,
            "antibiotics": antibiotic_rows,
        },
    )
    summary = {
        "products_processed": len(product_rows),
        "products_with_accredited_source": sum(1 for row in product_rows if row["accredited_source_status"] == "accredited_source_linked"),
        "products_pending_accredited_source": sum(1 for row in product_rows if row["accredited_source_status"] == "pending_accredited_source"),
        "regimen_rows_processed": len(regimen_rows),
        "regimen_rows_ready_source_verified": sum(1 for row in regimen_rows if row["accredited_source_status"] == "ready_source_verified"),
        "regimen_rows_pending_exact_evidence": sum(1 for row in regimen_rows if row["accredited_source_status"] == "pending_exact_accredited_evidence"),
        "pediatric_rows_processed": len(peds_rows),
        "pediatric_rows_formula_ready": sum(1 for row in peds_rows if row.get("pediatric_formula_ready")),
        "antibiotic_rows_processed": len(antibiotic_rows),
        "antibiotic_rows_gate_ready": sum(1 for row in antibiotic_rows if row.get("antibiotic_gate_ready")),
    }
    write_report(
        REPORT_GOLD / "all_drug_accredited_sweep_summary.md",
        "All Drug Accredited Sweep Summary",
        [
            "Every exported product, regimen, pediatric shortcut, and antibiotic row was processed. Rows without exact accredited field-level evidence remain hidden from prescribing output.",
            *[f"- {key}: {value}" for key, value in summary.items()],
        ],
    )
    return summary


def swaps_tier_report() -> None:
    swaps = read_json(DATA_GOLD / "rx_eligibility_map.json", {}).get("swaps_ready", [])
    rows = []
    for row in swaps:
        line = str(row.get("line_of_therapy", "")).upper()
        if "SWAP1" in line:
            tier = "Tier 1 verified alternative"
        elif "SWAP2" in line:
            tier = "Tier 2 verified adjunct/supportive option"
        else:
            tier = "Tier 3 verified fallback/conditional option"
        rows.append({**row, "swap_tier": tier})
    write_csv(REPORT_GOLD / "swaps_tier_report.csv", rows)


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
    safety_by_product = {s.get("product_id"): s for s in safety}
    safety_products = set(safety_by_product)
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
            if not all(row.get(field) for field in ["adult_dose", "adult_route", "adult_frequency", "adult_duration"]):
                errors.append(f"rx_ready_missing_dose_route_frequency_duration:{row.get('regimen_id')}")
            if not all(row.get(field) for field in ["indication_verified", "dose_verified", "route_verified", "frequency_verified", "duration_verified"]):
                errors.append(f"rx_ready_missing_field_level_flags:{row.get('regimen_id')}")
            if not row.get("safety_minimum_ready"):
                errors.append(f"rx_ready_without_safety:{row.get('regimen_id')}")
            if row.get("product_id") not in safety_products:
                errors.append(f"rx_ready_product_without_safety_row:{row.get('product_id')}")
            safety_row = safety_by_product.get(row.get("product_id"), {})
            if not all(safety_row.get(field) for field in ["contraindications", "precautions", "common_side_effects", "major_interactions", "pregnancy_lactation"]):
                errors.append(f"rx_ready_product_missing_safety_field:{row.get('product_id')}")
            if row.get("product_id") not in alias_products:
                errors.append(f"rx_ready_product_without_alias:{row.get('product_id')}")
    for row in rx.get("rx_now_ready", []):
        if row.get("final_rx_status") in {"source_missing_hide_from_rx", "source_conflict_hide_from_rx", "catalog_hidden_from_rx", "absolute_block"}:
            errors.append(f"hidden_status_in_rx_now:{row.get('regimen_id')}")
        if not row.get("source_ids") or not any(sid in source_ids for sid in row.get("source_ids", [])):
            errors.append(f"rx_now_without_citation:{row.get('regimen_id')}")
    for citation in citations:
        for key in ["source_id", "source_title", "source_org", "source_url", "source_type", "evidence_field", "evidence_snippet"]:
            if not citation.get(key):
                errors.append(f"incomplete_source_citation:{citation.get('linked_row_id', '')}:{key}")
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
    bundle = EXPORTS / f"{PHASE2_BUNDLE_PREFIX}_{date_part}.zip"
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
    write_json(patch_summary, {"created_at": now_iso(), "phase": "gold_phase_3_opd_first_verified_pack", "promotion_run": False})
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
            REPORT_GOLD / "gold_unique_coverage_report.csv",
            REPORT_GOLD / "gold_unique_coverage_summary.md",
            REPORT_GOLD / "product_match_gap_report.csv",
            REPORT_GOLD / "swaps_tier_report.csv",
            REPORT_GOLD / "all_drug_accredited_product_sweep.csv",
            REPORT_GOLD / "all_regimen_accredited_sweep.csv",
            REPORT_GOLD / "all_pediatric_accredited_sweep.csv",
            REPORT_GOLD / "all_antibiotic_accredited_sweep.csv",
            REPORT_GOLD / "all_drug_accredited_sweep_summary.md",
            REPORT_GOLD / "full_accredited_source_sweep_tasks.csv",
            REPORT_GOLD / "full_accredited_source_acceptance_report.csv",
            REPORT_GOLD / "full_accredited_source_rejection_report.csv",
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
    unique = unique_coverage_reports()
    all_sweep = all_drug_accredited_sweep_reports()
    full_acceptance = read_csv(REPORT_GOLD / "full_accredited_source_acceptance_report.csv")
    full_rejections = read_csv(REPORT_GOLD / "full_accredited_source_rejection_report.csv")
    lines = [
        "Rows are unlocked only when exact source-backed field-level evidence passes validation. Workbook-only rows remain hidden from prescribing output.",
        f"- Workbook used: `{selected.get('selected_workbook') or 'none_found'}`",
        f"- Products found: {counts.get('products', 0)}",
        f"- Draft regimen rows found: {counts.get('regimens', 0)}",
        f"- Source queries generated: {query_count}",
        f"- Accredited source metadata available: {source_count}",
        f"- Evidence fields extracted: {evidence_count}",
        f"- Full DailyMed product-label sources accepted: {len(full_acceptance)}",
        f"- Full DailyMed product-label unmatched/rejected: {len(full_rejections)}",
        f"- RX NOW ready count: {rx_counts.get('rx_now_ready', 0)}",
        f"- SWAPS ready count: {rx_counts.get('swaps_ready', 0)}",
        f"- Unique products RX-ready: {unique.get('unique_products_rx_ready', 0)}",
        f"- Unique generic names RX-ready: {unique.get('unique_generic_names_rx_ready', 0)}",
        f"- Unique disease keys RX-ready: {unique.get('unique_disease_keys_rx_ready', 0)}",
        f"- Unique product+disease pairs RX-ready: {unique.get('unique_product_disease_pairs_rx_ready', 0)}",
        f"- Duplicate ready row count: {unique.get('duplicate_row_count', 0)}",
        f"- Pediatric formula-ready count: {sum(1 for row in read_json(DATA_GOLD / 'pediatric_dose_engine.json', {'items': []}).get('items', []) if row.get('pediatric_formula_ready'))}",
        f"- Antibiotic gate-ready count: {sum(1 for row in read_json(DATA_GOLD / 'antibiotic_gate_map.json', {'items': []}).get('items', []) if row.get('antibiotic_gate_ready'))}",
        f"- Reference-only count: {rx_counts.get('reference_only', 0)}",
        f"- Hidden/not-ready count: {rx_counts.get('not_ready', 0)}",
        f"- Conflict count: {conflicts}",
        f"- Source acquisition queue count: {acquisition_queue}",
        f"- All-drug sweep products processed: {all_sweep.get('products_processed', 0)}",
        f"- All-drug sweep products still pending accredited source: {all_sweep.get('products_pending_accredited_source', 0)}",
        f"- All-drug sweep regimen rows processed: {all_sweep.get('regimen_rows_processed', 0)}",
        f"- All-drug sweep regimen rows pending exact evidence: {all_sweep.get('regimen_rows_pending_exact_evidence', 0)}",
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
    candidate_rows = phase2_candidate_rows()
    queries = build_queries()
    write_csv(REPORT_GOLD / "source_acquisition_queue.csv", [dict(row, retrieval_status="queued") for row in queries])
    adapter_result = run_phase2_adapters(candidate_rows)
    product_rows = export_sheet("1_Product_Master_Export")
    accredited_sweep_result = run_full_accredited_source_sweep(product_rows)
    write_csv(REPORT_GOLD / "evidence_extraction_report.csv", evidence_claims())
    sources = source_records()
    write_json(DATA_GOLD / "source_citations_gold.json", {"items": []})
    counts = build_gold_tables()
    rx_counts = build_rx_eligibility()
    unique_coverage_reports()
    product_match_gap_report()
    all_drug_accredited_sweep_reports()
    swaps_tier_report()
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
        "phase2_candidates": len(candidate_rows),
        "adapter_result": adapter_result,
        "accredited_sweep_result": accredited_sweep_result,
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


def phase2_candidate_rows() -> list[dict[str, str]]:
    top = export_sheet("4_Top_50_Defaults")
    clinic = export_sheet("5_Clinic_Defaults")
    regimens = export_sheet("2_Regimen_Master_Export", source_refreshed=True)
    priority_keys = {
        (row.get("regimen_id", ""), row.get("product_id", ""), row.get("disease_key", ""))
        for row in top + clinic
    }
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for row in regimens:
        key3 = (row.get("regimen_id", ""), row.get("product_id", ""), row.get("disease_key", ""))
        disease_blob = (row.get("disease_key", "") + " " + row.get("disease_name", "")).lower()
        common = any(token in disease_blob for token in COMMON_OPD_DISEASE_TOKENS)
        if key3 not in priority_keys and not common:
            continue
        key = (*key3, row.get("role", ""))
        if key in seen:
            continue
        seen.add(key)
        source = "top50_or_clinic_default" if key3 in priority_keys else "common_opd_disease"
        rows.append(
            {
                **row,
                "phase2_candidate_reason": source,
                "phase2_priority": "A" if source == "top50_or_clinic_default" else "B",
            }
        )
    rows.sort(key=lambda row: (row["phase2_priority"], row.get("regimen_id", ""), row.get("role", ""), row.get("product_id", "")))
    write_csv(REPORT_GOLD / "phase2_candidate_rows.csv", rows)
    return rows


def run_phase2_adapters(candidate_rows: list[dict[str, str]]) -> dict[str, Any]:
    accepted: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    tasks: list[dict[str, Any]] = []
    for name in ADAPTER_NAMES:
        try:
            module = __import__(f"source_adapters.{name}", fromlist=["run"])
            result = module.run(candidate_rows)
            accepted.extend(result.accepted_sources)
            claims.extend(result.evidence_claims)
            rejected.extend(result.rejected_sources)
            tasks.extend(result.search_tasks)
        except Exception as exc:
            rejected.append({"adapter": name, "status": "adapter_failed", "reason": str(exc)})
    for source in accepted:
        for key in [
            "source_id",
            "source_title",
            "source_org",
            "source_url",
            "access_date",
            "source_type",
            "source_country_or_region",
            "adapter_name",
            "retrieval_status",
            "extraction_status",
        ]:
            source.setdefault(key, "")
    for claim in claims:
        claim.setdefault("source_id", "")
        claim.setdefault("evidence_snippet", "")
        claim.setdefault("confidence", "")
    write_json(DATA_GOLD / "phase2_adapter_sources.json", {"items": accepted})
    write_json(DATA_GOLD / "phase2_field_evidence.json", {"items": claims})
    write_csv(REPORT_GOLD / "source_acceptance_report.csv", accepted)
    write_csv(REPORT_GOLD / "source_rejection_report.csv", rejected)
    if tasks:
        existing = read_csv(REPORT_GOLD / "source_acquisition_queue.csv")
        write_csv(REPORT_GOLD / "source_acquisition_queue.csv", existing + tasks)
    return {"accepted": len(accepted), "claims": len(claims), "rejected": len(rejected), "tasks": len(tasks)}


def phase2_claims() -> list[dict[str, Any]]:
    return read_json(DATA_GOLD / "phase2_field_evidence.json", {"items": []}).get("items", [])


def phase2_sources() -> list[dict[str, Any]]:
    return read_json(DATA_GOLD / "phase2_adapter_sources.json", {"items": []}).get("items", [])
