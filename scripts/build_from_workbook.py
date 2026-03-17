#!/usr/bin/env python3
"""Build app-ready seed JSON from workbook + current app seed.

- Reads `index.html` embedded seed as baseline.
- Reads workbook `Price_Estimates_Online` to update `pr` and metadata `price_updated_at`.
- Expands price coverage using generic/category/form fallback imputation.
- Applies pediatric parser upgrades for common concentration patterns.
- Adds explicit confidence metadata for price and pediatric quality.
- Writes build/app_seed.json and build/build_report.json.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from statistics import median

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
WB = ROOT / "source_workbooks" / "drug_list_final_userfriendly_engine_ready_v7.xlsx"
OUT = ROOT / "build" / "app_seed.json"
REPORT = ROOT / "build" / "build_report.json"


def norm_id(v: object) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(v or "").upper())


def norm_generic(v: object) -> str:
    s = str(v or "").lower().strip()
    s = re.sub(r"\([^)]*\)", "", s)
    s = re.sub(r"[^a-z0-9+ ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_price(v: object) -> float | None:
    if isinstance(v, (int, float)):
        x = float(v)
        return x if x > 0 else None
    s = str(v or "").strip().replace(",", "")
    if not s:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    if not m:
        return None
    x = float(m.group(1))
    return x if x > 0 else None


def parse_concentration(drug: dict) -> tuple[float, str] | None:
    text = f"{drug.get('n','')} {drug.get('c','')}".lower().replace("μg", "mcg")

    m = re.search(r"(\d+(?:\.\d+)?)\s*mg\s*/\s*(\d+(?:\.\d+)?)\s*ml", text, re.I)
    if m:
        mg, ml = float(m.group(1)), float(m.group(2))
        if ml > 0:
            return round(mg / ml, 4), m.group(0)

    m = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    if m and any(k in text for k in ["ml", "syrup", "solution", "drops", "susp"]):
        return round(float(m.group(1)) * 10, 4), m.group(0)

    m = re.search(r"(\d+(?:\.\d+)?)\s*mcg\s*/\s*(\d+(?:\.\d+)?)\s*ml", text, re.I)
    if m:
        mcg, ml = float(m.group(1)), float(m.group(2))
        if ml > 0:
            return round((mcg / 1000.0) / ml, 6), m.group(0)

    return None


def annotate_peds_quality(drug: dict) -> None:
    tl = drug.get("tl") or {}
    s = tl.get("s")
    nt = str(tl.get("nt") or "").lower()
    if s == "auto_mapped_from_same_generic_reference":
        tl["q"] = "auto_mapped"
    elif s == "calculator_ready_manual_target_needed":
        if "parser" in nt:
            tl["q"] = "parser_manual"
        elif "top pediatric generic uplift" in nt:
            tl["q"] = "generic_uplift_manual"
        else:
            tl["q"] = "manual_unknown"
    else:
        tl["q"] = "none"
    drug["tl"] = tl


def main() -> None:
    seed_match = re.search(r'<script id="seed" type="application/json">(.*?)</script>', INDEX.read_text(), re.S)
    if not seed_match:
        raise SystemExit("Cannot find seed JSON in index.html")
    seed = json.loads(seed_match.group(1))

    drugs = seed.get("dr", [])
    by_id = {norm_id(d.get("i")): d for d in drugs if d.get("i")}

    wb = load_workbook(WB, data_only=True, read_only=True)
    ws = wb["Price_Estimates_Online"]

    direct_price_updates = 0
    generic_fallback_updates = 0
    category_fallback_updates = 0
    form_fallback_updates = 0
    latest_date = None

    generic_price_pool: dict[str, list[float]] = {}
    category_price_pool: dict[str, list[float]] = {}
    form_price_pool: dict[str, list[float]] = {}

    for r in ws.iter_rows(min_row=2, values_only=True):
        if not r:
            continue
        bds = norm_id(r[0])
        generic = norm_generic(r[2])
        price = parse_price(r[4])
        checked = r[7]

        if bds and price and bds in by_id:
            by_id[bds]["pr"] = float(price)
            by_id[bds]["price_source"] = "workbook_direct"
            by_id[bds]["price_confidence"] = "direct"
            direct_price_updates += 1

        if generic and price:
            generic_price_pool.setdefault(generic, []).append(float(price))

        if checked:
            s = str(checked)
            if not latest_date or s > latest_date:
                latest_date = s

    for d in drugs:
        pr = d.get("pr")
        if not (isinstance(pr, (int, float)) and pr > 0):
            continue
        cc = str(d.get("cc") or "").strip().lower()
        fm = str(d.get("f") or "").strip().lower()
        if cc:
            category_price_pool.setdefault(cc, []).append(float(pr))
        if fm:
            form_price_pool.setdefault(fm, []).append(float(pr))

    for d in drugs:
        if isinstance(d.get("pr"), (int, float)) and d.get("pr") > 0:
            d.setdefault("price_source", "existing")
            d.setdefault("price_confidence", "direct" if d.get("price_source") == "workbook_direct" else "category_imputed")
            continue

        gk = norm_generic(d.get("g"))
        vals = generic_price_pool.get(gk)
        if vals:
            d["pr"] = float(round(median(vals), 2))
            d["price_source"] = "generic_median_imputed"
            d["price_confidence"] = "generic_imputed"
            generic_fallback_updates += 1
            continue

        cc = str(d.get("cc") or "").strip().lower()
        cv = category_price_pool.get(cc)
        if cv:
            d["pr"] = float(round(median(cv), 2))
            d["price_source"] = "category_median_imputed"
            d["price_confidence"] = "category_imputed"
            category_fallback_updates += 1
            continue

        fm = str(d.get("f") or "").strip().lower()
        fv = form_price_pool.get(fm)
        if fv:
            d["pr"] = float(round(median(fv), 2))
            d["price_source"] = "form_median_imputed"
            d["price_confidence"] = "form_imputed"
            form_fallback_updates += 1

    upgraded_parse = 0
    upgraded_top_generic = 0
    top_peds_generics = {
        "paracetamol", "ibuprofen", "cetirizine", "loratadine", "chlorpheniramine", "amoxicillin",
        "azithromycin", "salbutamol", "bromhexine", "simethicone", "nystatin", "racecadotril",
    }

    for d in drugs:
        tl = d.get("tl") or {}
        status = tl.get("s")
        if status in {"auto_mapped_from_same_generic_reference", "calculator_ready_manual_target_needed"}:
            annotate_peds_quality(d)
            continue

        form = str(d.get("f") or "").lower()
        has_liquid_hint = any(k in form for k in ["syrup", "susp", "solution", "drop", "spray", "liquid"])
        conc = parse_concentration(d)
        if conc and (has_liquid_hint or "ml" in str(d.get("c") or "").lower()):
            per_ml, raw = conc
            tl["s"] = "calculator_ready_manual_target_needed"
            tl["dm"] = tl.get("dm") or "mgkg"
            tl["dv"] = tl.get("dv") or 10
            tl["pc"] = {"kind": "mg", "per_ml": per_ml, "raw": raw}
            tl["nt"] = "Auto-upgraded by parser: concentration pattern recognized."
            d["tl"] = tl
            annotate_peds_quality(d)
            upgraded_parse += 1
            continue

        g = norm_generic(d.get("g"))
        if any(x in g for x in top_peds_generics) and status == "no_pediatric_target_found":
            tl["s"] = "calculator_ready_manual_target_needed"
            tl["dm"] = tl.get("dm") or "mgkg"
            tl["dv"] = tl.get("dv") or 10
            tl["nt"] = "Top pediatric generic uplift: manual target required for safe dosing confirmation."
            d["tl"] = tl
            annotate_peds_quality(d)
            upgraded_top_generic += 1
            continue

        annotate_peds_quality(d)

    seed.setdefault("m", {})
    seed["m"]["schema_version"] = "druglist-seed-v1"
    seed["m"]["build_version"] = f"auto-{date.today().isoformat()}"
    seed["m"]["price_updated_at"] = latest_date or "unknown"
    seed["m"]["pricedDrugCount"] = sum(1 for d in drugs if isinstance(d.get("pr"), (int, float)) and d.get("pr") > 0)

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(seed, ensure_ascii=False, separators=(",", ":")))

    conf = {"direct": 0, "generic_imputed": 0, "category_imputed": 0, "form_imputed": 0, "other": 0}
    for d in drugs:
        c = d.get("price_confidence")
        conf[c if c in conf else "other"] += 1

    pq = {"auto_mapped": 0, "parser_manual": 0, "generic_uplift_manual": 0, "manual_unknown": 0, "none": 0}
    for d in drugs:
        q = (d.get("tl") or {}).get("q", "none")
        pq[q if q in pq else "none"] += 1

    report = {
        "generated_at": date.today().isoformat(),
        "direct_price_updates": direct_price_updates,
        "generic_fallback_updates": generic_fallback_updates,
        "category_fallback_updates": category_fallback_updates,
        "form_fallback_updates": form_fallback_updates,
        "latest_price_date": latest_date,
        "pediatric_upgraded_parser": upgraded_parse,
        "pediatric_upgraded_top_generic": upgraded_top_generic,
        "pricedDrugCount": seed["m"].get("pricedDrugCount"),
        "price_confidence_counts": conf,
        "pediatric_quality_counts": pq,
        "drugCount": len(drugs),
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
