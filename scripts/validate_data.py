#!/usr/bin/env python3
"""Validate build/app_seed.json integrity and thresholds."""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "build" / "app_seed.json"
if not SEED.exists():
    raise SystemExit("build/app_seed.json not found; run scripts/build_from_workbook.py first")
D = json.loads(SEED.read_text())

dr = D.get("dr", [])
cp = D.get("cp", [])
pd = D.get("pd", [])
ids = [d.get("i") for d in dr if d.get("i")]
idset = set(ids)
errs = []
warns = []
if len(ids) != len(idset):
    errs.append(f"duplicate_drug_ids={len(ids)-len(idset)}")
broken = 0
for t in pd:
    for r in (t.get("r") or []):
        b = r.get("b")
        if b and b not in idset:
            broken += 1
if broken:
    errs.append(f"broken_peds_links={broken}")
empty_reg = sum(1 for c in cp if not (c.get("r") or []))
if empty_reg:
    warns.append(f"complaints_without_regimen={empty_reg}")
priced = sum(1 for d in dr if isinstance(d.get("pr"),(int,float)) and d.get("pr")>0)
peds_cov = sum(1 for d in dr if (d.get("tl") or {}).get("s") in {"auto_mapped_from_same_generic_reference","calculator_ready_manual_target_needed"})
price_rate = (priced/len(dr)) if dr else 0
peds_rate = (peds_cov/len(dr)) if dr else 0
if price_rate < 0.30:
    warns.append(f"price_coverage_below_threshold={price_rate:.3f}")
if peds_rate < 0.20:
    warns.append(f"peds_coverage_below_threshold={peds_rate:.3f}")
out = {
    "generated_at": datetime.utcnow().isoformat()+"Z",
    "schema_version": D.get("m",{}).get("schema_version"),
    "build_version": D.get("m",{}).get("build_version"),
    "drugCount": len(dr),
    "complaintCount": len(cp),
    "pricedDrugCount": priced,
    "pedsCoverageCount": peds_cov,
    "priceCoverageRate": round(price_rate,4),
    "pedsCoverageRate": round(peds_rate,4),
    "errors": errs,
    "warnings": warns,
    "pass": not errs,
}
print(json.dumps(out, indent=2))
(Path(ROOT/"build"/"validation_report.json")).write_text(json.dumps(out, indent=2))
if errs:
    raise SystemExit(1)
