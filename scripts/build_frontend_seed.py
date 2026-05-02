#!/usr/bin/env python3
"""Compose generated layers into a frontend-compatible runtime seed."""
from __future__ import annotations

from collections import Counter

from engine_common import load_embedded_seed, now_iso, read_json, write_json
from runtime_readiness import readiness_for_med


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
    flagged_products = [product for product in products if (product.get("manual_review") or {}).get("required")]
    review_reason_counts = Counter(
        reason
        for product in flagged_products
        for reason in ((product.get("manual_review") or {}).get("reasons") or [])
    )
    output = dict(seed)
    output["dr"] = [legacy_drug(product) for product in products]
    product_by_id = {drug["i"]: drug for drug in output["dr"]}
    output["cp"] = annotate_runtime_complaints(seed.get("cp") or [], product_by_id)
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
        "manual_review_product_count": len(flagged_products),
        "manual_review_queue_count": len(manual_queue.get("items", [])),
        "source_gap_count": len(source_gaps.get("items", [])),
        "pediatric_review_count": len(peds.get("items", [])),
        "manual_review_reason_counts": dict(sorted(review_reason_counts.items())),
        "source_coverage": source_coverage,
        "verified_source_count": len(verified_sources),
        "registered_source_count": len(sources),
        "runtime_index_count": len(runtime.get("index", [])),
        "clinical_status": "source_workbook_only_with_unverified_legacy_regimens",
    }
    write_json("data/core/app_seed_runtime.json", output)
    return output["m"]


def annotate_runtime_complaints(complaints: list[dict[str, object]], product_by_id: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    annotated: list[dict[str, object]] = []
    for complaint in complaints:
        c_next = dict(complaint)
        disease_id = str(c_next.get("d") or c_next.get("c") or "")
        regimens = []
        for regimen in c_next.get("r") or []:
            r_next = dict(regimen)
            meds = []
            for med in r_next.get("m") or []:
                m_next = dict(med)
                product = product_by_id.get(str(m_next.get("i") or "")) or {}
                m_next.update(readiness_for_med(m_next, product, disease_id))
                meds.append(m_next)
            r_next["m"] = meds
            regimens.append(r_next)
        c_next["r"] = regimens
        annotated.append(c_next)
    return annotated


def main() -> int:
    meta = build()
    print(
        "built frontend seed: "
        f"drugs={meta['drugCount']} source_coverage={meta['source_coverage']} manual_review={meta['manual_review_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
