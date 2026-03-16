#!/usr/bin/env python3
"""Build app-ready seed JSON from workbook + current app seed.

- Reads `index.html` embedded seed as baseline.
- Reads workbook `Price_Estimates_Online` to update `pr` and metadata `price_updated_at`.
- Applies lightweight pediatric parser upgrade for liquid forms with parseable mg/mL concentration.
- Writes build/app_seed.json and build/build_report.json.
"""
from __future__ import annotations
import json, re
from pathlib import Path
from datetime import date
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
WB = ROOT / "source_workbooks" / "drug_list_final_userfriendly_engine_ready_v7.xlsx"
OUT = ROOT / "build" / "app_seed.json"
REPORT = ROOT / "build" / "build_report.json"

seed_match = re.search(r'<script id="seed" type="application/json">(.*?)</script>', INDEX.read_text(), re.S)
if not seed_match:
    raise SystemExit("Cannot find seed JSON in index.html")
seed = json.loads(seed_match.group(1))

drugs = seed.get("dr", [])
by_id = {d.get("i"): d for d in drugs if d.get("i")}

wb = load_workbook(WB, data_only=True, read_only=True)
ws = wb["Price_Estimates_Online"]
rows = list(ws.iter_rows(min_row=2, values_only=True))
price_updates = 0
latest_date = None
for r in rows:
    if not r:
        continue
    bds = str(r[0]).strip() if r[0] else None
    pack_price = r[4]
    checked = r[7]
    if bds in by_id and isinstance(pack_price, (int, float)):
        by_id[bds]["pr"] = float(pack_price)
        price_updates += 1
    if checked:
        s = str(checked)
        if not latest_date or s > latest_date:
            latest_date = s

# Pediatric parser upgrade: improve manual-target coverage for liquid/syrup with parseable mg/ml.
upgraded = 0
for d in drugs:
    tl = d.get("tl") or {}
    if tl.get("s") != "no_pediatric_target_found":
        continue
    form = str(d.get("f") or "").lower()
    name = str(d.get("n") or "") + " " + str(d.get("c") or "")
    if not any(k in form for k in ["syrup", "susp", "solution", "drop", "spray", "liquid"]):
        continue
    m = re.search(r"(\d+(?:\.\d+)?)\s*mg\s*/\s*(\d+(?:\.\d+)?)\s*ml", name, re.I)
    if not m:
        continue
    mg = float(m.group(1)); ml = float(m.group(2))
    per_ml = round(mg / ml, 4) if ml else None
    if not per_ml:
        continue
    tl["s"] = "calculator_ready_manual_target_needed"
    tl["dm"] = tl.get("dm") or "mgkg"
    tl["dv"] = tl.get("dv") or 10
    tl["pc"] = {"kind": "mg", "per_ml": per_ml, "raw": m.group(0)}
    tl["nt"] = "Auto-upgraded by workbook build parser: parseable liquid concentration found."
    d["tl"] = tl
    upgraded += 1

seed.setdefault("m", {})
seed["m"]["schema_version"] = "druglist-seed-v1"
seed["m"]["build_version"] = f"auto-{date.today().isoformat()}"
seed["m"]["price_updated_at"] = latest_date or "unknown"
seed["m"]["pricedDrugCount"] = sum(1 for d in drugs if isinstance(d.get("pr"), (int, float)) and d.get("pr") > 0)

OUT.write_text(json.dumps(seed, ensure_ascii=False, separators=(",", ":")))
report = {
    "generated_at": date.today().isoformat(),
    "price_updates": price_updates,
    "latest_price_date": latest_date,
    "pediatric_manual_upgraded": upgraded,
    "pricedDrugCount": seed["m"].get("pricedDrugCount"),
    "drugCount": len(drugs),
}
REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False))
print(json.dumps(report, indent=2, ensure_ascii=False))
