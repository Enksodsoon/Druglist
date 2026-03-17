#!/usr/bin/env python3
"""Build app-ready seed JSON from workbook + current app seed.

- Reads `index.html` embedded seed as baseline.
- Reads workbook `Price_Estimates_Online` to update `pr` and metadata `price_updated_at`.
- Expands price coverage using generic-level fallback when direct BDS price is missing.
- Applies pediatric parser upgrades for common concentration patterns.
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
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_price(v: object) -> float | None:
    if isinstance(v, (int, float)):
        return float(v) if float(v) > 0 else None
    s = str(v or "").strip()
    if not s:
        return None
    s = s.replace(",", "")
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    if not m:
        return None
    x = float(m.group(1))
    return x if x > 0 else None


def parse_concentration(drug: dict) -> tuple[float, str] | None:
    text = f"{drug.get('n','')} {drug.get('c','')}".lower()
    text = text.replace("μg", "mcg")

    # mg/ml patterns
    m = re.search(r"(\d+(?:\.\d+)?)\s*mg\s*/\s*(\d+(?:\.\d+)?)\s*ml", text, re.I)
    if m:
        mg = float(m.group(1))
        ml = float(m.group(2))
        if ml > 0:
            return round(mg / ml, 4), m.group(0)

    # mg/5ml etc
    m = re.search(r"(\d+(?:\.\d+)?)\s*mg\s*/\s*(\d+(?:\.\d+)?)\s*(?:ml|mL)", text, re.I)
    if m:
        mg = float(m.group(1))
        ml = float(m.group(2))
        if ml > 0:
            return round(mg / ml, 4), m.group(0)

    # percentage w/v ~= g per 100 ml
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    if m and any(k in text for k in ["ml", "syrup", "solution", "drops", "susp"]):
        pct = float(m.group(1))
        # 1% ~= 10 mg/mL
        return round(pct * 10, 4), m.group(0)

    # mcg/ml
    m = re.search(r"(\d+(?:\.\d+)?)\s*mcg\s*/\s*(\d+(?:\.\d+)?)\s*ml", text, re.I)
    if m:
        mcg = float(m.group(1))
        ml = float(m.group(2))
        if ml > 0:
            return round((mcg / 1000.0) / ml, 6), m.group(0)

    return None


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
        pack_price = parse_price(r[4])
        checked = r[7]

        if bds and pack_price and bds in by_id:
            by_id[bds]["pr"] = float(pack_price)
            by_id[bds]["price_source"] = "workbook_direct"
            direct_price_updates += 1

        if generic and pack_price:
            generic_price_pool.setdefault(generic, []).append(float(pack_price))

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

    # Generic-level fallback price imputation for same-generic products.
    for d in drugs:
        if isinstance(d.get("pr"), (int, float)) and d.get("pr") > 0:
            continue
        gk = norm_generic(d.get("g"))
        vals = generic_price_pool.get(gk)
        if vals:
            d["pr"] = float(round(median(vals), 2))
            d["price_source"] = "generic_median_imputed"
            generic_fallback_updates += 1
            continue
        cc = str(d.get("cc") or "").strip().lower()
        cv = category_price_pool.get(cc)
        if cv:
            d["pr"] = float(round(median(cv), 2))
            d["price_source"] = "category_median_imputed"
            category_fallback_updates += 1
            continue
        fm = str(d.get("f") or "").strip().lower()
        fv = form_price_pool.get(fm)
        if fv:
            d["pr"] = float(round(median(fv), 2))
            d["price_source"] = "form_median_imputed"
            form_fallback_updates += 1

    # Pediatric parser upgrade + top pediatric med uplift.
    upgraded_parse = 0
    upgraded_top_generic = 0
    top_peds_generics = {
        "paracetamol",
        "ibuprofen",
        "cetirizine",
        "loratadine",
        "chlorpheniramine",
        "amoxicillin",
        "azithromycin",
        "salbutamol",
        "bromhexine",
        "simethicone",
        "nystatin",
        "racecadotril",
    }

    for d in drugs:
        tl = d.get("tl") or {}
        status = tl.get("s")
        if status in {"auto_mapped_from_same_generic_reference", "calculator_ready_manual_target_needed"}:
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
            upgraded_parse += 1
            continue

        g = norm_generic(d.get("g"))
        if any(x in g for x in top_peds_generics) and status == "no_pediatric_target_found":
            tl["s"] = "calculator_ready_manual_target_needed"
            tl["dm"] = tl.get("dm") or "mgkg"
            tl["dv"] = tl.get("dv") or 10
            tl["nt"] = "Top pediatric generic uplift: manual target required for safe dosing confirmation."
            d["tl"] = tl
            upgraded_top_generic += 1

    seed.setdefault("m", {})
    seed["m"]["schema_version"] = "druglist-seed-v1"
    seed["m"]["build_version"] = f"auto-{date.today().isoformat()}"
    seed["m"]["price_updated_at"] = latest_date or "unknown"
    seed["m"]["pricedDrugCount"] = sum(1 for d in drugs if isinstance(d.get("pr"), (int, float)) and d.get("pr") > 0)

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(seed, ensure_ascii=False, separators=(",", ":")))

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
        "drugCount": len(drugs),
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
