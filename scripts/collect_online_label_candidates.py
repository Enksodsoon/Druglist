#!/usr/bin/env python3
"""Collect non-destructive online label candidates for Druglist evidence gaps.

This script intentionally does not modify active runtime, product dose fields, or
Fast Mode flags. It records official label snippets as candidate evidence only.
"""
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from engine_common import ROOT, clean, norm_key, now_iso, stable_id, write_json

OUT_DIR = ROOT / "data" / "evidence_gap_candidates"
REPORT_DIR = ROOT / "reports"
SOURCE_ID = "dailymed_official_label"
SOURCE_NAME = "DailyMed official drug label"
DAILYMED_BASE = "https://dailymed.nlm.nih.gov/dailymed"
NS = {"h": "urn:hl7-org:v3"}

OTC_CATEGORY_HINTS = {
    "analgesic_antipyretic",
    "allergy_respiratory",
    "cough_cold",
    "gastrointestinal",
    "eye_ear",
    "ยาอมแก้เจ็บคอ",
    "ยาระบาย",
    "ยาพ่นและยาหยอดจมูก",
}

SECTION_KEYS = {
    "INDICATIONS": "indications",
    "INDICATIONS & USAGE": "indications",
    "DOSAGE": "dosage",
    "DOSAGE & ADMINISTRATION": "dosage",
    "WARNINGS": "warnings",
    "CONTRAINDICATIONS": "contraindications",
    "DRUG INTERACTIONS": "interactions",
    "OTC - DO NOT USE": "do_not_use",
    "OTC - ASK DOCTOR": "ask_doctor",
    "OTC - ASK DOCTOR/PHARMACIST": "ask_doctor_pharmacist",
    "OTC - KEEP OUT OF REACH OF CHILDREN": "keep_out_of_reach",
}

FIELD_PATTERNS = {
    "has_age_terms": re.compile(r"\b(child|children|pediatric|infant|age|years?|months?)\b", re.I),
    "has_weight_terms": re.compile(r"\b(weight|kg|kilogram|lb|pound)\b", re.I),
    "has_frequency": re.compile(r"\b(every|once|twice|daily|hours?|times? (a|per) day|q\d+h)\b", re.I),
    "has_duration": re.compile(r"\b(for \d+ days?|for up to \d+ days?|do not use (for )?more than)\b", re.I),
    "has_max_dose": re.compile(r"\b(maximum|max|not exceed|do not (give|take|use) more than|no more than)\b", re.I),
    "has_strength": re.compile(r"\b\d+(\.\d+)?\s*(mg|mcg|g|ml|%)\b", re.I),
}


def load_json(path: str, default: Any) -> Any:
    target = ROOT / path
    if not target.exists():
        return default
    return json.loads(target.read_text(encoding="utf-8"))


def url_json(url: str, timeout: int) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": "DruglistEvidenceCandidateBot/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def url_bytes(url: str, timeout: int) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "DruglistEvidenceCandidateBot/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def search_terms_for_generic(generic: str) -> list[str]:
    generic = clean(generic)
    terms = [generic]
    if "+" in generic:
        pieces = [clean(piece) for piece in generic.split("+") if clean(piece)]
        terms.append(" ".join(pieces))
        terms.extend(pieces)
    if "," in generic:
        terms.extend(clean(piece) for piece in generic.split(",") if clean(piece))
    normalized = []
    seen: set[str] = set()
    for term in terms:
        term = normalize_generic(term)
        if term and term not in seen:
            normalized.append(term)
            seen.add(term)
    return normalized


def query_spls(generic: str, timeout: int, spl_limit: int) -> list[dict[str, Any]]:
    urls = []
    for term in search_terms_for_generic(generic):
        quoted = urllib.parse.quote(term)
        urls.extend(
            [
                f"{DAILYMED_BASE}/services/v1/drugname/{quoted}/human/otc/spls.json",
                f"{DAILYMED_BASE}/services/v1/drugname/{quoted}/human/spls.json",
            ]
        )
    by_setid: dict[str, dict[str, Any]] = {}
    for url in urls:
        try:
            payload = url_json(url, timeout)
        except Exception:
            continue
        columns = payload.get("COLUMNS") or []
        for row in payload.get("DATA") or []:
            item = {columns[i].lower(): row[i] for i in range(min(len(columns), len(row)))}
            setid = clean(item.get("setid"))
            if setid and setid not in by_setid:
                item["search_url"] = url
                by_setid[setid] = item
            if len(by_setid) >= spl_limit:
                break
        if len(by_setid) >= spl_limit:
            break
    return list(by_setid.values())[:spl_limit]


def section_name(section: ET.Element) -> str:
    code = section.find("h:code", NS)
    title = section.find("h:title", NS)
    return clean((code.attrib.get("displayName") if code is not None else "") or (title.text if title is not None else ""))


def compact_text(element: ET.Element) -> str:
    return clean(" ".join("".join(element.itertext()).split()))


def extract_label_sections(xml_bytes: bytes) -> dict[str, str]:
    root = ET.fromstring(xml_bytes)
    sections: dict[str, str] = {}
    for section in root.findall(".//h:section", NS):
        name = section_name(section)
        upper = name.upper()
        for key, target in SECTION_KEYS.items():
            if key in upper:
                text = compact_text(section)
                if text and target not in sections:
                    sections[target] = text[:2200]
    return sections


def normalize_generic(generic: str) -> str:
    generic = re.sub(r"\b(eq\.?\s*to|bp|usp|hcl|hydrochloride|dihydrochloride|maleate|besylate|sodium|calcium)\b", " ", generic, flags=re.I)
    generic = re.sub(r"\s+", " ", generic)
    return clean(generic)


def is_otc_like(product: dict[str, Any]) -> bool:
    category = clean(product.get("category"))
    if category in OTC_CATEGORY_HINTS:
        return True
    flags = product.get("flags") or {}
    if flags.get("antibiotic"):
        return False
    text = norm_key(f"{product.get('display_name')} {product.get('category')} {product.get('subcategory_th')}")
    return any(token in text for token in ["pain", "fever", "cough", "cold", "allergy", "antacid", "laxative", "eye", "ear"])


def target_products(limit: int | None = None, scope: str = "all") -> list[dict[str, Any]]:
    products = load_json("data/core/drug_master_rebuilt.json", {"products": []}).get("products", [])
    peds = load_json("data/pediatric/pediatric_source_gap_priority.json", {"items": []}).get("items", [])
    peds_ids = {clean(item.get("product_id")) for item in peds}
    selected = []
    for product in products:
        generic = clean(product.get("generic_key") or product.get("generic"))
        if not generic:
            continue
        if scope == "all" or is_otc_like(product) or clean(product.get("id")) in peds_ids:
            selected.append(product)
    selected.sort(key=lambda p: (clean(p.get("generic_key")), clean(p.get("id"))))
    return selected[:limit] if limit else selected


def extracted_fields(sections: dict[str, str]) -> dict[str, Any]:
    dosage = sections.get("dosage", "")
    combined = " ".join(sections.values())
    return {
        "has_indication_text": bool(sections.get("indications")),
        "has_dosage_text": bool(dosage),
        "has_warning_text": bool(sections.get("warnings")),
        "has_contraindication_text": bool(sections.get("contraindications") or sections.get("do_not_use")),
        "has_interaction_text": bool(sections.get("interactions") or sections.get("ask_doctor_pharmacist")),
        "has_pediatric_age_terms": bool(FIELD_PATTERNS["has_age_terms"].search(dosage)),
        "has_pediatric_weight_terms": bool(FIELD_PATTERNS["has_weight_terms"].search(dosage)),
        "has_frequency_terms": bool(FIELD_PATTERNS["has_frequency"].search(dosage)),
        "has_duration_terms": bool(FIELD_PATTERNS["has_duration"].search(dosage)),
        "has_max_dose_terms": bool(FIELD_PATTERNS["has_max_dose"].search(combined)),
        "has_strength_terms": bool(FIELD_PATTERNS["has_strength"].search(combined)),
    }


def candidate_status(product: dict[str, Any], sections: dict[str, str], pediatric_target: bool) -> tuple[str, list[str]]:
    missing = []
    fields = extracted_fields(sections)
    if not sections.get("dosage"):
        missing.append("dosage_section")
    if not sections.get("warnings"):
        missing.append("warnings_section")
    if not sections.get("indications"):
        missing.append("indications_section")
    if pediatric_target:
        if not (fields["has_pediatric_age_terms"] or fields["has_pediatric_weight_terms"]):
            missing.append("pediatric_age_or_weight_bounds")
        if not fields["has_frequency_terms"]:
            missing.append("pediatric_frequency")
        if not fields["has_max_dose_terms"]:
            missing.append("pediatric_max_dose")
    if product.get("flags", {}).get("antibiotic"):
        missing.append("antibiotic_gate_required")
    return ("source_matched_candidate" if not missing else "blocked_missing_required_safety_field", missing)


def build_candidate(product: dict[str, Any], spl: dict[str, Any], sections: dict[str, str], pediatric_target: bool) -> dict[str, Any]:
    status, missing = candidate_status(product, sections, pediatric_target)
    setid = clean(spl.get("setid"))
    return {
        "candidate_id": stable_id("ONLINE_LABEL", f"{product.get('id')}_{setid}"),
        "product_id": clean(product.get("id")),
        "display_name": clean(product.get("display_name")),
        "generic_key": clean(product.get("generic_key")),
        "route": clean(product.get("route")),
        "form": clean(product.get("form")),
        "category": clean(product.get("category")),
        "candidate_status": status,
        "fast_mode_allowed": False,
        "manual_review_required": True,
        "pediatric_target": pediatric_target,
        "required_fields_missing": missing,
        "extracted_field_presence": extracted_fields(sections),
        "source": {
            "source_id": SOURCE_ID,
            "source_name": SOURCE_NAME,
            "organization": "U.S. National Library of Medicine / FDA SPL",
            "setid": setid,
            "title": clean(spl.get("title")),
            "spl_version": clean(spl.get("spl_version")),
            "published_date": clean(spl.get("published_date")),
            "url": f"{DAILYMED_BASE}/dailymed/drugInfo.cfm?setid={setid}",
            "api_url": f"{DAILYMED_BASE}/services/v2/spls/{setid}.xml",
            "retrieved_at": now_iso(),
        },
        "sections": sections,
        "notes": "Candidate only. Does not modify product dose, pediatric calculator, antibiotic gates, or Fast Mode.",
    }


def collect_for_generic(
    generic: str,
    grouped_products: list[dict[str, Any]],
    peds_ids: set[str],
    spl_limit: int,
    timeout: int,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    candidates: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    spls = query_spls(generic, timeout=timeout, spl_limit=spl_limit)
    if not spls:
        for product in grouped_products:
            skipped.append({"product_id": clean(product.get("id")), "generic_key": generic, "reason": "no_dailymed_label_found"})
        return candidates, skipped
    for spl in spls:
        setid = clean(spl.get("setid"))
        try:
            xml = url_bytes(f"{DAILYMED_BASE}/services/v2/spls/{setid}.xml", timeout=timeout)
            sections = extract_label_sections(xml)
        except Exception as exc:
            for product in grouped_products:
                skipped.append({"product_id": clean(product.get("id")), "generic_key": generic, "reason": f"label_fetch_failed:{type(exc).__name__}"})
            continue
        for product in grouped_products:
            candidates.append(build_candidate(product, spl, sections, clean(product.get("id")) in peds_ids))
    return candidates, skipped


def collect(limit: int | None, spl_limit: int, sleep_seconds: float, timeout: int, scope: str, workers: int) -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    peds = load_json("data/pediatric/pediatric_source_gap_priority.json", {"items": []}).get("items", [])
    peds_ids = {clean(item.get("product_id")) for item in peds}
    all_products = load_json("data/core/drug_master_rebuilt.json", {"products": []}).get("products", [])
    products = target_products(limit, scope=scope)
    by_generic: dict[str, list[dict[str, Any]]] = {}
    for product in products:
        generic = normalize_generic(clean(product.get("generic_key") or product.get("generic")))
        if generic:
            by_generic.setdefault(generic, []).append(product)

    candidates: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    items = sorted(by_generic.items())
    if workers <= 1:
        for idx, (generic, grouped_products) in enumerate(items, start=1):
            found, missed = collect_for_generic(generic, grouped_products, peds_ids, spl_limit=spl_limit, timeout=timeout)
            candidates.extend(found)
            skipped.extend(missed)
            if sleep_seconds:
                time.sleep(sleep_seconds)
            if idx % 25 == 0:
                print(f"progress: {idx}/{len(items)} generic queries", flush=True)
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(collect_for_generic, generic, grouped_products, peds_ids, spl_limit, timeout): generic
                for generic, grouped_products in items
            }
            for idx, future in enumerate(as_completed(futures), start=1):
                found, missed = future.result()
                candidates.extend(found)
                skipped.extend(missed)
                if sleep_seconds:
                    time.sleep(sleep_seconds)
                if idx % 25 == 0 or idx == len(futures):
                    print(f"progress: {idx}/{len(futures)} generic queries", flush=True)

    otc_candidates = [c for c in candidates if not c["pediatric_target"]]
    peds_candidates = [c for c in candidates if c["pediatric_target"]]
    products_with_candidates = {c["product_id"] for c in candidates}
    targeted_product_ids = {clean(p.get("id")) for p in products}
    no_candidate_products = sorted(targeted_product_ids - products_with_candidates)
    status_counts = Counter(c["candidate_status"] for c in candidates)
    category_counts = Counter(clean(p.get("category")) or "unspecified" for p in products)
    skipped_reason_counts = Counter(item["reason"].split(":")[0] for item in skipped)
    field_presence_counts = Counter()
    for candidate in candidates:
        for field, present in (candidate.get("extracted_field_presence") or {}).items():
            if present:
                field_presence_counts[field] += 1
    summary = {
        "generated_at": now_iso(),
        "source": SOURCE_NAME,
        "scope": scope,
        "total_catalog_products": len(all_products),
        "product_targets": len(products),
        "generic_queries": len(by_generic),
        "candidate_count": len(candidates),
        "products_with_candidates": len(products_with_candidates),
        "target_products_without_candidates": len(no_candidate_products),
        "otc_candidate_count": len(otc_candidates),
        "pediatric_candidate_count": len(peds_candidates),
        "skipped_count": len(skipped),
        "status_counts": dict(status_counts),
        "category_counts": dict(category_counts),
        "skipped_reason_counts": dict(skipped_reason_counts),
        "field_presence_counts": dict(field_presence_counts),
        "fast_mode_allowed_count": sum(1 for c in candidates if c["fast_mode_allowed"]),
        "manual_review_required_count": sum(1 for c in candidates if c["manual_review_required"]),
    }
    write_json(OUT_DIR / "online_label_candidates.json", {"meta": summary, "candidates": candidates})
    write_json(OUT_DIR / "otc_product_candidates.json", {"meta": summary, "candidates": otc_candidates})
    write_json(OUT_DIR / "pediatric_label_candidates.json", {"meta": summary, "candidates": peds_candidates})
    write_json(OUT_DIR / "skipped_online_label_candidates.json", {"meta": summary, "items": skipped})
    write_json(
        OUT_DIR / "coverage_summary.json",
        {
            "meta": summary,
            "target_products_without_candidates": no_candidate_products,
            "products_with_candidates": sorted(products_with_candidates),
        },
    )
    write_json(OUT_DIR / "import_manifest.json", summary)

    report_lines = [
        "# Online Evidence Gap Candidate Report",
        "",
        f"Generated: {summary['generated_at']}",
        "",
        f"- Source: {SOURCE_NAME}",
        f"- Scope: {summary['scope']}",
        f"- Total catalog products: {summary['total_catalog_products']}",
        f"- Product targets: {summary['product_targets']}",
        f"- Generic queries: {summary['generic_queries']}",
        f"- Candidates: {summary['candidate_count']}",
        f"- Products with candidates: {summary['products_with_candidates']}",
        f"- Target products without candidates: {summary['target_products_without_candidates']}",
        f"- OTC-like candidates: {summary['otc_candidate_count']}",
        f"- Pediatric candidates: {summary['pediatric_candidate_count']}",
        f"- Skipped labels/products: {summary['skipped_count']}",
        f"- Fast Mode allowed: {summary['fast_mode_allowed_count']}",
        f"- Manual review required: {summary['manual_review_required_count']}",
        f"- Status counts: {summary['status_counts']}",
        f"- Skipped reason counts: {summary['skipped_reason_counts']}",
        f"- Field presence counts: {summary['field_presence_counts']}",
        "",
        "Safety: these records are evidence candidates only. They do not update active runtime dosing, pediatric calculators, antibiotic gates, or Fast RX NOW.",
    ]
    (REPORT_DIR / "online_evidence_gap_candidate_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=80, help="Maximum target products to query; 0 means all eligible targets.")
    parser.add_argument("--scope", choices=["all", "otc-peds"], default="all", help="Collect every catalog product or only OTC-like/pediatric-priority products.")
    parser.add_argument("--spl-limit", type=int, default=1, help="Maximum DailyMed labels per generic.")
    parser.add_argument("--sleep", type=float, default=0.1, help="Delay between generic queries.")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout seconds.")
    parser.add_argument("--workers", type=int, default=8, help="Concurrent DailyMed lookup workers.")
    args = parser.parse_args()
    summary = collect(
        limit=None if args.limit == 0 else args.limit,
        spl_limit=args.spl_limit,
        sleep_seconds=args.sleep,
        timeout=args.timeout,
        scope=args.scope,
        workers=args.workers,
    )
    print(f"online_label_candidates: candidates={summary['candidate_count']} skipped={summary['skipped_count']} fast_mode_allowed={summary['fast_mode_allowed_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
