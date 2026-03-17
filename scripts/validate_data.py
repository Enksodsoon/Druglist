#!/usr/bin/env python3
"""Validate build/app_seed.json integrity and thresholds."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validate app seed integrity and release thresholds.")
    p.add_argument("--seed", default="build/app_seed.json", help="Path to app seed JSON")
    p.add_argument("--strict", action="store_true", help="Treat threshold misses as hard errors")
    p.add_argument("--min-price-rate", type=float, default=0.30, help="Minimum priced-drug ratio")
    p.add_argument("--min-peds-rate", type=float, default=0.20, help="Minimum pediatric-coverage ratio")
    p.add_argument("--min-direct-generic-rate", type=float, default=0.04, help="Minimum direct+generic price confidence ratio")
    p.add_argument("--min-peds-weighted-rate", type=float, default=0.12, help="Minimum weighted pediatric quality ratio")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    seed = root / args.seed
    if not seed.exists():
        raise SystemExit(f"{args.seed} not found; run scripts/build_from_workbook.py first")

    D = json.loads(seed.read_text())
    dr = D.get("dr", [])
    cp = D.get("cp", [])
    pd = D.get("pd", [])
    ids = [d.get("i") for d in dr if d.get("i")]
    idset = set(ids)

    errs: list[str] = []
    warns: list[str] = []

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

    total = len(dr) or 1
    priced = sum(1 for d in dr if isinstance(d.get("pr"), (int, float)) and d.get("pr") > 0)

    price_conf = {"direct": 0, "generic_imputed": 0, "category_imputed": 0, "form_imputed": 0, "other": 0}
    for d in dr:
        c = d.get("price_confidence")
        price_conf[c if c in price_conf else "other"] += 1

    peds_quality = {"auto_mapped": 0, "parser_manual": 0, "generic_uplift_manual": 0, "manual_unknown": 0, "none": 0}
    for d in dr:
        q = (d.get("tl") or {}).get("q", "none")
        peds_quality[q if q in peds_quality else "none"] += 1

    peds_cov = peds_quality["auto_mapped"] + peds_quality["parser_manual"] + peds_quality["generic_uplift_manual"] + peds_quality["manual_unknown"]
    price_rate = priced / total
    peds_rate = peds_cov / total
    direct_generic_rate = (price_conf["direct"] + price_conf["generic_imputed"]) / total
    peds_weighted_score = (
        peds_quality["auto_mapped"] * 1.0
        + peds_quality["parser_manual"] * 0.7
        + peds_quality["generic_uplift_manual"] * 0.4
        + peds_quality["manual_unknown"] * 0.5
    )
    peds_weighted_rate = peds_weighted_score / total

    threshold_fails: list[str] = []
    if price_rate < args.min_price_rate:
        threshold_fails.append(f"price_coverage_below_threshold={price_rate:.3f}<min={args.min_price_rate:.3f}")
    if peds_rate < args.min_peds_rate:
        threshold_fails.append(f"peds_coverage_below_threshold={peds_rate:.3f}<min={args.min_peds_rate:.3f}")
    if direct_generic_rate < args.min_direct_generic_rate:
        threshold_fails.append(
            f"direct_generic_price_ratio_below_threshold={direct_generic_rate:.3f}<min={args.min_direct_generic_rate:.3f}"
        )
    if peds_weighted_rate < args.min_peds_weighted_rate:
        threshold_fails.append(
            f"peds_weighted_quality_below_threshold={peds_weighted_rate:.3f}<min={args.min_peds_weighted_rate:.3f}"
        )

    if args.strict:
        errs.extend(threshold_fails)
    else:
        warns.extend(threshold_fails)

    out = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "schema_version": D.get("m", {}).get("schema_version"),
        "build_version": D.get("m", {}).get("build_version"),
        "strict_mode": args.strict,
        "min_price_rate": args.min_price_rate,
        "min_peds_rate": args.min_peds_rate,
        "min_direct_generic_rate": args.min_direct_generic_rate,
        "min_peds_weighted_rate": args.min_peds_weighted_rate,
        "drugCount": len(dr),
        "complaintCount": len(cp),
        "pricedDrugCount": priced,
        "pedsCoverageCount": peds_cov,
        "priceCoverageRate": round(price_rate, 4),
        "pedsCoverageRate": round(peds_rate, 4),
        "directGenericPriceRate": round(direct_generic_rate, 4),
        "pedsWeightedQualityRate": round(peds_weighted_rate, 4),
        "priceConfidenceCounts": price_conf,
        "pedsQualityCounts": peds_quality,
        "errors": errs,
        "warnings": warns,
        "pass": not errs,
    }

    print(json.dumps(out, indent=2))
    (root / "build" / "validation_report.json").write_text(json.dumps(out, indent=2))
    return 0 if not errs else 1


if __name__ == "__main__":
    raise SystemExit(main())
