#!/usr/bin/env python3
"""One-command release preparation pipeline.

Steps:
1) Build seed from workbook
2) Validate built seed in strict release mode
3) Inject seed into index.html
4) Re-validate index embedded seed consistency
5) Emit consolidated release report
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
REPORT = BUILD / "release_prepare_report.json"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Prepare release artifact with strict guardrails.")
    p.add_argument("--min-price-rate", type=float, default=0.30)
    p.add_argument("--min-peds-rate", type=float, default=0.20)
    return p.parse_args()


def run(cmd: list[str]) -> dict:
    p = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    return {
        "cmd": " ".join(cmd),
        "returncode": p.returncode,
        "stdout": p.stdout,
        "stderr": p.stderr,
    }


def fail(steps: list[dict], failed_step: dict) -> None:
    REPORT.write_text(json.dumps({"pass": False, "failed_step": failed_step, "steps": steps}, indent=2))
    raise SystemExit(1)


def main() -> None:
    args = parse_args()
    BUILD.mkdir(exist_ok=True)

    steps: list[dict] = []

    steps.append(run(["python", "scripts/build_from_workbook.py"]))
    if steps[-1]["returncode"] != 0:
        fail(steps, steps[-1])

    steps.append(
        run(
            [
                "python",
                "scripts/validate_data.py",
                "--strict",
                "--min-price-rate",
                str(args.min_price_rate),
                "--min-peds-rate",
                str(args.min_peds_rate),
            ]
        )
    )
    if steps[-1]["returncode"] != 0:
        fail(steps, steps[-1])

    steps.append(run(["python", "scripts/inject_seed.py"]))
    if steps[-1]["returncode"] != 0:
        fail(steps, steps[-1])

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
        "release_thresholds": {
            "min_price_rate": args.min_price_rate,
            "min_peds_rate": args.min_peds_rate,
        },
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


if __name__ == "__main__":
    main()
