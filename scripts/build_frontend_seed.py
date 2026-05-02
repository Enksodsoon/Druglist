#!/usr/bin/env python3
"""Compose generated layers into a frontend-compatible runtime seed."""
from __future__ import annotations

from engine_common import load_embedded_seed, now_iso, read_json, write_json


def legacy_drug(product: dict[str, object]) -> dict[str, object]:
    manual = product.get("manual_review", {}) or {}
    source = product.get("source", {}) or {}
    return {
        "i": product["id"],
        "n": product["display_name"],
        "g": product.get("generic", ""),
        "c": product.get("composition", ""),
        "cc": product.get("category", ""),
        "f": product.get("form", ""),
        "p": product.get("pack", ""),
        "pr": None,
        "dp": False,
        "tl": {
            "s": "manual_review_required" if manual.get("required") else "source_workbook_only",
            "m": [],
            "dm": None,
            "dv": None,
            "fn": None,
            "fx": None,
            "fu": None,
            "pc": None,
            "rp": "",
            "rs": "",
            "rf": "",
            "rd": "",
            "rdi": "",
            "nt": "No verified pediatric dose source attached.",
            "q": "none",
        },
        "ag": {"vmin": None, "vmax": None, "vt": "", "imin": None, "it": ""},
        "price_source": "",
        "price_confidence": "unsupported",
        "source_ids": ["PRIMARY_WORKBOOK"],
        "source_status": source.get("status", "source_workbook_extracted"),
        "manual_review_required": bool(manual.get("required")),
        "manual_review_reasons": manual.get("reasons", []),
        "fa": {
            "subcategory": product.get("subcategory_th", ""),
            "product_code": product.get("product_code", ""),
            "product_name": product.get("product_name", ""),
            "pack_size": product.get("pack", ""),
            "composition": product.get("composition", ""),
            "medicine_code": product.get("bds_code", ""),
            "medicine_name": product.get("medicine_name", ""),
            "instructions_th": product.get("original_thai_sig", ""),
            "instructions_en": product.get("english_sig_label", ""),
            "online_pack_price_thb": "",
            "online_unit_price_thb": "",
            "price_source_url": "",
            "price_checked_date": "",
            "price_notes": "",
            "category": product.get("category", ""),
            "source_row": source.get("excel_row", ""),
            "source_status": source.get("status", "source_workbook_extracted"),
        },
    }


def build() -> dict[str, object]:
    seed = load_embedded_seed()
    product_layer = read_json("data/core/drug_master_rebuilt.json", {"products": [], "meta": {}})
    manual_queue = read_json("data/meta/manual_review_queue.json", {"items": []})
    source_registry = read_json("data/guidelines/source_registry.json", {"sources": []})
    source_gaps = read_json("data/guidelines/source_gap_list.json", {"items": []})
    runtime = read_json("data/core/opd_fast_index.json", {"index": []})
    peds = read_json("data/pediatric/peds_product_dose_output.json", {"items": []})

    sources = source_registry.get("sources", [])
    verified_sources = [s for s in sources if s.get("access_status") == "available" and s.get("extraction_status") == "extracted"]
    source_coverage = round(len(verified_sources) / max(1, len(sources)), 4)
    products = product_layer.get("products", [])
    output = dict(seed)
    output["dr"] = [legacy_drug(product) for product in products]
    output["pd"] = []
    output["cg"] = []
    output["m"] = {
        **(seed.get("m") or {}),
        "source": "generated_runtime_layers",
        "schema_version": "drug-assistant-runtime-v1",
        "build_version": f"runtime-{now_iso()}",
        "generated_at": now_iso(),
        "drugCount": len(products),
        "pedsCount": 0,
        "pricedDrugCount": 0,
        "classCompareCount": 0,
        "manual_review_count": len(manual_queue.get("items", [])) + len(source_gaps.get("items", [])) + len(peds.get("items", [])),
        "source_coverage": source_coverage,
        "verified_source_count": len(verified_sources),
        "registered_source_count": len(sources),
        "runtime_index_count": len(runtime.get("index", [])),
        "clinical_status": "source_workbook_only_with_unverified_legacy_regimens",
    }
    write_json("data/core/app_seed_runtime.json", output)
    return output["m"]


def main() -> int:
    meta = build()
    print(
        "built frontend seed: "
        f"drugs={meta['drugCount']} source_coverage={meta['source_coverage']} manual_review={meta['manual_review_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
