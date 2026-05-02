#!/usr/bin/env python3
"""Build the source-grounded product layer from the primary workbook."""
from __future__ import annotations

from collections import defaultdict

from engine_common import (
    PRIMARY_WORKBOOK,
    category_from_subcategory,
    clean,
    display_name,
    ensure_dirs,
    extract_generic,
    infer_form,
    infer_route,
    norm_key,
    now_iso,
    primary_workbook_rows,
    role_tags,
    stable_id,
    write_json,
    write_report,
)


def manual_reasons(row: dict[str, str], route: str, form: str, tags: list[str]) -> list[str]:
    reasons: list[str] = []
    if not row.get("Medicine code"):
        reasons.append("missing_medicine_code")
    if not row.get("Medicine name"):
        reasons.append("missing_medicine_name")
    if not row.get("ส่วนประกอบ"):
        reasons.append("missing_composition")
    if not route:
        reasons.append("route_uncertain")
    if form == "other":
        reasons.append("form_uncertain")
    if "antibiotic" in tags:
        reasons.append("antibiotic_requires_indication_duration_source")
    if "pediatric_candidate" in tags:
        reasons.append("pediatric_candidate_requires_verified_weight_age_rule")
    return reasons


def build() -> dict[str, object]:
    ensure_dirs("data/core", "data/meta", "reports")
    headers, source_rows = primary_workbook_rows()
    products: list[dict[str, object]] = []
    seen: dict[str, int] = {}

    for row in source_rows:
        code = clean(row.get("Medicine code"))
        if not code:
            code = stable_id("ROW", row.get("_excel_row"))
        seen[code] = seen.get(code, 0) + 1
        product_name = clean(row.get("ชื่อสินค้า") or row.get("Medicine name"))
        medicine_name = clean(row.get("Medicine name") or product_name)
        composition = clean(row.get("ส่วนประกอบ"))
        pack = clean(row.get("ขนาด"))
        subcategory = clean(row.get("ประเภทย่อย"))
        generic = extract_generic(composition, product_name)
        form = infer_form(medicine_name, pack, composition)
        route = infer_route(form, medicine_name, composition)
        category = category_from_subcategory(subcategory)
        tags = role_tags(category, generic, form, row.get("วิธีใช้ (Med-Links)", ""))
        flags = {
            "manual_review": False,
            "pediatric_candidate": "pediatric_candidate" in tags,
            "antibiotic": "antibiotic" in tags,
            "source_workbook_only": True,
            "no_price_source": True,
            "no_verified_clinical_dose": True,
        }
        reasons = manual_reasons(row, route, form, tags)
        if reasons:
            flags["manual_review"] = True

        products.append(
            {
                "id": code,
                "product_code": clean(row.get("รหัสสินค้า")),
                "bds_code": code,
                "product_name": product_name,
                "medicine_name": medicine_name,
                "composition": composition,
                "display_name": display_name(product_name or medicine_name, composition),
                "pack": pack,
                "form": form,
                "route": route,
                "category": category,
                "subcategory_th": subcategory,
                "generic": generic,
                "generic_key": norm_key(generic),
                "role_tags": tags,
                "flags": flags,
                "original_thai_sig": clean(row.get("วิธีใช้ (Med-Links)")),
                "english_sig_label": clean(row.get("วิธีใช้ (Med-Links).1") or row.get("col_10")),
                "source": {
                    "type": "workbook",
                    "file": PRIMARY_WORKBOOK.name,
                    "sheet": "Final approved",
                    "excel_row": int(row.get("_excel_row") or 0),
                    "columns": headers,
                    "status": "source_workbook_extracted",
                },
                "manual_review": {
                    "required": bool(reasons),
                    "reasons": reasons,
                    "status": "pending" if reasons else "not_required",
                    "notes": "",
                },
                "unsupported_fields": {
                    "price": "",
                    "cautions": "",
                    "side_effects": "",
                    "contraindications": "",
                    "verified_indications": "",
                    "verified_adult_dose": "",
                    "verified_pediatric_dose": "",
                },
            }
        )

    by_generic: dict[str, list[dict[str, str]]] = defaultdict(list)
    for product in products:
        by_generic[str(product["generic_key"])].append(
            {
                "id": str(product["id"]),
                "display_name": str(product["display_name"]),
                "form": str(product["form"]),
                "route": str(product["route"]),
                "category": str(product["category"]),
            }
        )

    short_lookup = {
        str(p["id"]): {
            "display_name": p["display_name"],
            "product_name": p["product_name"],
            "composition": p["composition"],
            "generic": p["generic"],
            "form": p["form"],
            "route": p["route"],
            "category": p["category"],
            "manual_review": p["manual_review"]["required"],
        }
        for p in products
    }
    cluster_map = {
        key or "unspecified": {"generic_key": key or "unspecified", "count": len(items), "products": items}
        for key, items in sorted(by_generic.items())
    }
    queue = [
        {
            "id": p["id"],
            "display_name": p["display_name"],
            "reasons": p["manual_review"]["reasons"],
            "source_row": p["source"]["excel_row"],
            "status": "pending",
        }
        for p in products
        if p["manual_review"]["required"]
    ]

    meta = {
        "generated_at": now_iso(),
        "source_file": PRIMARY_WORKBOOK.name,
        "source_sheet": "Final approved",
        "source_rows": len(source_rows),
        "product_count": len(products),
        "duplicate_bds_count": sum(count - 1 for count in seen.values() if count > 1),
        "manual_review_count": len(queue),
        "headers": headers,
    }
    write_json("data/core/drug_master_rebuilt.json", {"meta": meta, "products": products})
    write_json("data/core/drug_short_lookup.json", {"meta": meta, "lookup": short_lookup})
    write_json("data/core/generic_cluster_map.json", {"meta": meta, "clusters": cluster_map})
    write_json("data/meta/manual_review_queue.json", {"meta": meta, "items": queue})

    category_counts: dict[str, int] = defaultdict(int)
    for product in products:
        category_counts[str(product["category"])] += 1
    write_report(
        "reports/build_audit_report.md",
        "Product Layer Build Audit",
        [
            ("Source", f"Primary workbook: `{PRIMARY_WORKBOOK.name}`\n\nRows extracted: {len(source_rows)}"),
            ("Outputs", "\n".join([
                "- `data/core/drug_master_rebuilt.json`",
                "- `data/core/drug_short_lookup.json`",
                "- `data/core/generic_cluster_map.json`",
                "- `data/meta/manual_review_queue.json`",
            ])),
            ("Counts", f"Products: {len(products)}\n\nManual-review items: {len(queue)}\n\nDuplicate BDS entries: {meta['duplicate_bds_count']}"),
            ("Category Coverage", "\n".join(f"- {k}: {v}" for k, v in sorted(category_counts.items()))),
            ("Clinical Data Policy", "No prices, cautions, side effects, contraindications, indications, adult doses, or pediatric doses were fabricated. Unsupported fields are blank and review-gated."),
        ],
    )
    return meta


def main() -> int:
    meta = build()
    print(f"built product layer: products={meta['product_count']} manual_review={meta['manual_review_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
