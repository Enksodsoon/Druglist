#!/usr/bin/env python3
"""One-command release preparation pipeline with strict guardrails and regression checks."""
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
HISTORY_JSON = BUILD / "release_history.json"
HISTORY_MD = BUILD / "release_history.md"
TREND_SUMMARY = BUILD / "release_trend_summary.md"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Prepare release artifact with strict guardrails.")
    p.add_argument("--min-price-rate", type=float, default=0.30)
    p.add_argument("--min-peds-rate", type=float, default=0.20)
    p.add_argument("--min-direct-generic-rate", type=float, default=0.04)
    p.add_argument("--min-peds-weighted-rate", type=float, default=0.12)
    p.add_argument("--max-price-regression", type=float, default=0.04, help="Max allowed drop vs previous snapshot")
    p.add_argument("--max-peds-regression", type=float, default=0.03, help="Max allowed peds weighted drop vs previous snapshot")
    p.add_argument("--max-direct-generic-regression", type=float, default=0.03, help="Max allowed direct+generic drop vs previous snapshot")
    return p.parse_args()


def run(cmd: list[str]) -> dict:
    p = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    return {"cmd": " ".join(cmd), "returncode": p.returncode, "stdout": p.stdout, "stderr": p.stderr}


def write_history(snap: dict) -> tuple[list[dict], str]:
    history: list[dict] = []
    if HISTORY_JSON.exists():
        try:
            history = json.loads(HISTORY_JSON.read_text())
        except Exception:
            history = []
    history.append(snap)
    history = history[-30:]
    HISTORY_JSON.write_text(json.dumps(history, indent=2))

    lines = [
        "# Release Regression History",
        "",
        "| Date | Build | PriceRate | Direct+GenericRate | PedsRate | PedsWeighted | Errors |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for h in reversed(history[-15:]):
        lines.append(
            f"| {h.get('generated_at','')} | {h.get('build_version','')} | {h.get('priceCoverageRate',0):.4f} | "
            f"{h.get('directGenericPriceRate',0):.4f} | {h.get('pedsCoverageRate',0):.4f} | {h.get('pedsWeightedQualityRate',0):.4f} | {h.get('errorCount',0)} |"
        )
    HISTORY_MD.write_text("\n".join(lines) + "\n")

    trend_lines = ["# Release Trend Summary", ""]
    if len(history) >= 2:
        cur = history[-1]
        prev = history[-2]
        trend_lines += [
            f"- priceCoverageRate: {prev.get('priceCoverageRate',0):.4f} -> {cur.get('priceCoverageRate',0):.4f}",
            f"- directGenericPriceRate: {prev.get('directGenericPriceRate',0):.4f} -> {cur.get('directGenericPriceRate',0):.4f}",
            f"- pedsCoverageRate: {prev.get('pedsCoverageRate',0):.4f} -> {cur.get('pedsCoverageRate',0):.4f}",
            f"- pedsWeightedQualityRate: {prev.get('pedsWeightedQualityRate',0):.4f} -> {cur.get('pedsWeightedQualityRate',0):.4f}",
            f"- errorCount: {prev.get('errorCount',0)} -> {cur.get('errorCount',0)}",
        ]
    else:
        trend_lines.append("- First snapshot captured; no previous baseline yet.")
    TREND_SUMMARY.write_text("\n".join(trend_lines) + "\n")

    return history, str(HISTORY_MD)


def fail(steps: list[dict], failed_step: dict, extra: dict | None = None) -> None:
    payload = {"pass": False, "failed_step": failed_step, "steps": steps}
    if extra:
        payload.update(extra)
    REPORT.write_text(json.dumps(payload, indent=2))
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
                "--min-direct-generic-rate",
                str(args.min_direct_generic_rate),
                "--min-peds-weighted-rate",
                str(args.min_peds_weighted_rate),
            ]
        )
    )
    if steps[-1]["returncode"] != 0:
        fail(steps, steps[-1])

    steps.append(run(["python", "scripts/inject_seed.py"]))
    if steps[-1]["returncode"] != 0:
        fail(steps, steps[-1])

    m = re.search(r'<script id="seed" type="application/json">(.*?)</script>', (ROOT / "index.html").read_text(), re.S)
    if not m:
        raise SystemExit("seed block missing after injection")
    seed = json.loads(m.group(1))

    vr = json.loads((BUILD / "validation_report.json").read_text())
    snapshot = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "build_version": seed.get("m", {}).get("build_version"),
        "priceCoverageRate": vr.get("priceCoverageRate", 0),
        "directGenericPriceRate": vr.get("directGenericPriceRate", 0),
        "pedsCoverageRate": vr.get("pedsCoverageRate", 0),
        "pedsWeightedQualityRate": vr.get("pedsWeightedQualityRate", 0),
        "errorCount": len(vr.get("errors", [])),
    }

    history, history_md_path = write_history(snapshot)

    regressions: list[str] = []
    if len(history) >= 2:
        prev = history[-2]
        if snapshot["priceCoverageRate"] < prev.get("priceCoverageRate", 0) - args.max_price_regression:
            regressions.append(
                f"priceCoverageRate regressed from {prev.get('priceCoverageRate',0):.4f} to {snapshot['priceCoverageRate']:.4f}"
            )
        if snapshot["pedsWeightedQualityRate"] < prev.get("pedsWeightedQualityRate", 0) - args.max_peds_regression:
            regressions.append(
                f"pedsWeightedQualityRate regressed from {prev.get('pedsWeightedQualityRate',0):.4f} to {snapshot['pedsWeightedQualityRate']:.4f}"
            )
        if snapshot["directGenericPriceRate"] < prev.get("directGenericPriceRate", 0) - args.max_direct_generic_regression:
            regressions.append(
                f"directGenericPriceRate regressed from {prev.get('directGenericPriceRate',0):.4f} to {snapshot['directGenericPriceRate']:.4f}"
            )

    if regressions:
        fail(steps, {"cmd": "regression-check", "returncode": 1, "stdout": "\n".join(regressions), "stderr": ""}, {"regressions": regressions})

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
            "min_direct_generic_rate": args.min_direct_generic_rate,
            "min_peds_weighted_rate": args.min_peds_weighted_rate,
        },
        "snapshot": snapshot,
        "history_markdown": history_md_path,
        "trend_summary": str(TREND_SUMMARY),
    }

    out = {"pass": True, "generated_at": datetime.utcnow().isoformat() + "Z", "summary": summary, "steps": steps}
    REPORT.write_text(json.dumps(out, indent=2))
    print(json.dumps(summary, indent=2))
    try:
        print(TREND_SUMMARY.read_text())
    except Exception:
        pass
    print("release_prepare: PASS")


if __name__ == "__main__":
    main()
