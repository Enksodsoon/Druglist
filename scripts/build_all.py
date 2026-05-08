#!/usr/bin/env python3
"""Run the full Drug Assistant data build pipeline."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from engine_common import ROOT, now_iso, write_json

STEPS = [
    "scripts/build_product_layer.py",
    "scripts/build_guideline_layer.py",
    "scripts/source_manifest.py",
    "scripts/auto_source_collect.py",
    "scripts/evidence_extract.py",
    "scripts/evidence_score.py",
    "scripts/evidence_resolve.py",
    "scripts/build_pediatric_layer.py",
    "scripts/build_safety_layer.py",
    "scripts/build_runtime_json.py",
    "scripts/build_frontend_seed.py",
]


def manifest_time() -> str:
    manifest = ROOT / "data/meta/build_manifest.json"
    if manifest.exists():
        try:
            return json.loads(manifest.read_text(encoding="utf-8")).get("generated_at") or now_iso()
        except json.JSONDecodeError:
            return now_iso()
    return now_iso()


def main() -> int:
    generated_at = manifest_time()
    env = dict(os.environ)
    env["DRUGLIST_BUILD_TIME"] = generated_at
    results = []
    for step in STEPS:
        proc = subprocess.run([sys.executable, step], cwd=ROOT, env=env, text=True, capture_output=True)
        results.append({"step": step, "returncode": proc.returncode, "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip()})
        if proc.stdout.strip():
            print(proc.stdout.strip())
        if proc.returncode != 0:
            if proc.stderr.strip():
                print(proc.stderr.strip(), file=sys.stderr)
            write_json("data/meta/build_manifest.json", {"generated_at": generated_at, "status": "failed", "steps": results})
            return proc.returncode

    outputs = sorted(
        str(path.relative_to(ROOT))
        for base in ["data/core", "data/guidelines", "data/pediatric", "data/safety", "data/meta", "data/evidence"]
        for path in (ROOT / base).glob("*.json")
    )
    manifest = {
        "generated_at": generated_at,
        "status": "pass",
        "steps": results,
        "outputs": outputs,
        "source_workbook_required": "source_workbooks/Drug list for physician usage added -update 29022024.xlsx",
    }
    write_json("data/meta/build_manifest.json", manifest)
    print(f"build_all complete: outputs={len(outputs)} generated_at={generated_at}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
