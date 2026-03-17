#!/usr/bin/env python3
"""Inject build/app_seed.json into index.html <script id='seed'> block."""
from __future__ import annotations
import re, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
SEED = ROOT / "build" / "app_seed.json"

if not SEED.exists():
    raise SystemExit("build/app_seed.json not found; run scripts/build_from_workbook.py first")

seed_obj = json.loads(SEED.read_text())
seed_min = json.dumps(seed_obj, ensure_ascii=False, separators=(",", ":"))
text = INDEX.read_text()
pat = r'(<script id="seed" type="application/json">)(.*?)(</script>)'
m = re.search(pat, text, re.S)
if not m:
    raise SystemExit("seed script block not found in index.html")
new = re.sub(pat, r'\1'+seed_min+r'\3', text, flags=re.S)
INDEX.write_text(new)
print("Injected seed into index.html")
print(f"drugs={len(seed_obj.get('dr',[]))} complaints={len(seed_obj.get('cp',[]))} priced={seed_obj.get('m',{}).get('pricedDrugCount')}")
