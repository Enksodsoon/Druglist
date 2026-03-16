#!/usr/bin/env python3
"""One-command release preparation pipeline.

Steps:
1) Build seed from workbook
2) Validate built seed
3) Inject seed into index.html
4) Re-validate index embedded seed consistency
5) Emit consolidated release report
"""
from __future__ import annotations
import json, subprocess, re
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
REPORT = BUILD / "release_prepare_report.json"

BUILD.mkdir(exist_ok=True)


def run(cmd: list[str]) -> dict:
    p = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    return {
        "cmd": " ".join(cmd),
        "returncode": p.returncode,
        "stdout": p.stdout,
        "stderr": p.stderr,
    }

steps = []
steps.append(run(["python", "scripts/build_from_workbook.py"]))
if steps[-1]["returncode"] != 0:
    REPORT.write_text(json.dumps({"pass": False, "failed_step": steps[-1], "steps": steps}, indent=2))
    raise SystemExit(1)

steps.append(run(["python", "scripts/validate_data.py"]))
if steps[-1]["returncode"] != 0:
    REPORT.write_text(json.dumps({"pass": False, "failed_step": steps[-1], "steps": steps}, indent=2))
    raise SystemExit(1)

steps.append(run(["python", "scripts/inject_seed.py"]))
if steps[-1]["returncode"] != 0:
    REPORT.write_text(json.dumps({"pass": False, "failed_step": steps[-1], "steps": steps}, indent=2))
    raise SystemExit(1)

# embedded seed consistency check
index = (ROOT / "index.html").read_text()
m = re.search(r'<script id="seed" type="application/json">(.*?)</script>', index, re.S)
if not m:
    raise SystemExit("seed block missing after injection")
seed = json.loads(m.group(1))
summary = {
    "drugCount": len(seed.get("dr", [])),
    "complaintCount": len(seed.get("cp", [])),
    "pricedDrugCount": seed.get("m", {}).get("pricedDrugCount"),
    "schema_version": seed.get("m", {}).get("schema_version"),
    "build_version": seed.get("m", {}).get("build_version"),
    "price_updated_at": seed.get("m", {}).get("price_updated_at"),
}

out = {
    "pass": True,
    "generated_at": datetime.utcnow().isoformat() + "Z",
    "summary": summary,
    "steps": steps,
}
REPORT.write_text(json.dumps(out, indent=2))
print(json.dumps(summary, indent=2))
print("release_prepare: PASS")
