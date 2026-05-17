#!/usr/bin/env python3
"""Compose generated layers into a frontend-compatible runtime seed."""
from __future__ import annotations

from collections import Counter
import json
import re

from engine_common import ROOT, load_embedded_seed, now_iso, read_json, write_json
from runtime_readiness import readiness_for_med


def legacy_drug(product: dict[str, object], evidence_summary: dict[str, object] | None = None) -> dict[str, object]:
    manual = product.get("manual_review", {}) or {}
    source = product.get("source", {}) or {}
    evidence_summary = evidence_summary or {}
    evidence_status = str(evidence_summary.get("evidence_status") or "pending_source_collection")
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
        "evidence_status": evidence_status,
        "evidence_score": 0,
        "evidence_confidence": "none",
        "evidence_source_ids": [],
        "evidence_required_fields_missing": ["source collection", "source extraction"],
        "auto_resolution_status": evidence_status,
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
    guideline_patch_manual = read_json("data/meta/guideline_patch_manual_review_queue.json", {"items": []})
    source_registry = read_json("data/guidelines/source_registry.json", {"sources": []})
    source_gaps = read_json("data/guidelines/source_gap_list.json", {"items": []})
    evidence_summary = read_json("data/evidence/evidence_runtime_summary.json", {})
    runtime = read_json("data/core/opd_fast_index.json", {"index": []})
    peds = read_json("data/pediatric/peds_product_dose_output.json", {"items": []})
    guideline_patch_peds = read_json("data/pediatric/imported_guideline_peds_shortcuts.json", {"items": []})
    peds_rules = read_json("data/pediatric/reviewed_peds_dose_rules.json", {"rules": []}).get("rules", [])
    clinical_issues = read_json("data/meta/clinical_regimen_quality_issues.json", {"issues": []}).get("issues", [])
    antiviral_issues = read_json("data/meta/antiviral_regimen_quality_issues.json", {"issues": []}).get("issues", [])
    antibiotic_issues = read_json("data/meta/antibiotic_rdu_quality_issues.json", {"issues": []}).get("issues", [])
    peds_priority = read_json("data/pediatric/pediatric_source_gap_priority.json", {"items": []}).get("items", [])
    regimen_safety = read_json("data/safety/regimen_safety_rules.json", {"items": []}).get("items", [])
    workbook_issues = read_json("data/meta/workbook_quality_issues.json", {"issues": []}).get("issues", [])
    corrections = read_json("data/meta/correction_overlay_applied.json", {"items": []}).get("items", [])
    source_todo = read_json("data/evidence/source_manifest.todo.json", {"items": []}).get("items", [])

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
    output["dr"] = [legacy_drug(product, evidence_summary) for product in products]
    product_by_id = {drug["i"]: drug for drug in output["dr"]}
    base_complaints = [row for row in seed.get("cp") or [] if row.get("src") != "guideline_patch_20260516"]
    output["cp"] = merge_runtime_overlay_complaints(annotate_runtime_complaints(base_complaints, product_by_id))
    output["pd"] = build_pediatric_templates(peds.get("items", []), product_by_id)
    output["cg"] = []
    output["m"] = {
        **(seed.get("m") or {}),
        "source": "generated_runtime_layers",
        "schema_version": "drug-assistant-runtime-v1",
        "build_version": f"runtime-{now_iso()}",
        "generated_at": now_iso(),
        "drugCount": len(products),
        "pedsCount": len(output["pd"]),
        "pricedDrugCount": 0,
        "classCompareCount": 0,
        "manual_review_count": len(manual_queue.get("items", [])) + len(source_gaps.get("items", [])) + len(peds.get("items", [])) + len(guideline_patch_manual.get("items", [])) + len(guideline_patch_peds.get("items", [])),
        "manual_review_product_count": len(flagged_products),
        "manual_review_queue_count": len(manual_queue.get("items", [])),
        "source_gap_count": len(source_gaps.get("items", [])),
        "pediatric_review_count": len(peds.get("items", [])),
        "guideline_patch_manual_review_count": len(guideline_patch_manual.get("items", [])),
        "guideline_patch_pediatric_shortcut_count": len(guideline_patch_peds.get("items", [])),
        "pediatric_verified_count": sum(1 for rule in peds_rules if rule.get("reviewer_status") == "verified"),
        "pediatric_label_reference_only_count": sum(1 for rule in peds_rules if rule.get("reviewer_status") == "label_reference_only"),
        "pediatric_pending_source_count": sum(1 for rule in peds_rules if rule.get("reviewer_status") == "pending_source"),
        "pediatric_do_not_use_count": sum(1 for rule in peds_rules if rule.get("reviewer_status") == "do_not_use"),
        "manual_review_reason_counts": dict(sorted(review_reason_counts.items())),
        "source_coverage": source_coverage,
        "verified_source_count": len(verified_sources),
        "registered_source_count": len(sources),
        "runtime_index_count": len(runtime.get("index", [])),
        "guideline_patch_runtime_count": sum(1 for complaint in output["cp"] if complaint.get("src") == "guideline_patch_20260516"),
        "evidence_status": evidence_summary.get("evidence_status", "pending_source_collection"),
        "evidence_auto_verified_count": evidence_summary.get("auto_verified_claim_count", 0),
        "evidence_auto_resolved_gap_count": evidence_summary.get("auto_resolved_gap_count", 0),
        "evidence_pending_source_collection_count": evidence_summary.get("pending_source_collection_count", 0),
        "evidence_blocked_low_confidence_count": evidence_summary.get("blocked_low_confidence_count", 0),
        "evidence_blocked_missing_required_safety_field_count": evidence_summary.get("blocked_missing_required_safety_field_count", 0),
        "evidence_blocked_conflict_count": evidence_summary.get("blocked_conflict_count", 0),
        "evidence_peds_auto_verified_count": evidence_summary.get("peds_auto_verified_count", 0),
        "evidence_antibiotic_auto_verified_count": evidence_summary.get("antibiotic_auto_verified_count", 0),
        "clinical_audit_issue_count": len(clinical_issues),
        "clinical_audit_blocker_count": sum(1 for issue in clinical_issues if issue.get("severity") == "blocker"),
        "antiviral_audit_issue_count": len(antiviral_issues),
        "pediatric_source_gap_count": len(peds_priority),
        "antibiotic_rdu_issue_count": len(antibiotic_issues),
        "regimen_safety_blocker_count": sum(1 for row in regimen_safety if row.get("regimen_safety_status") == "blocked"),
        "workbook_qa_issue_count": len(workbook_issues),
        "correction_overlay_applied_count": len(corrections),
        "source_manifest_todo_count": len(source_todo),
        "clinical_status": "source_workbook_only_with_unverified_legacy_regimens",
    }
    write_json("data/core/app_seed_runtime.json", output)
    inject_runtime_seed(output)
    return output["m"]


def inject_runtime_seed(output: dict[str, object]) -> None:
    """Keep the embedded file:// fallback identical to the generated runtime seed."""
    index = ROOT / "index.html"
    text = index.read_text(encoding="utf-8")
    seed_min = json.dumps(output, ensure_ascii=False, separators=(",", ":"))
    pattern = r'(<script id="seed" type="application/json">)(.*?)(</script>)'
    next_text, count = re.subn(pattern, rf"\1{seed_min}\3", text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError("seed script block not found in index.html")
    index.write_text(next_text, encoding="utf-8")


def pediatric_template_row(product_id: str, product: dict[str, object], *, row_id: str = "", order: str = "", frequency: str = "", duration: str = "", dispense: str = "", note: str = "") -> dict[str, object]:
    return {
        "i": row_id or product_id,
        "b": product_id,
        "n": product.get("n") or product_id,
        "o": order,
        "f": frequency,
        "u": duration,
        "p": dispense,
        "cv": note,
    }


def build_pediatric_templates(peds_items: list[dict[str, object]], product_by_id: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    """Build manual-review pediatric template groups without inventing dose instructions."""
    templates: dict[str, dict[str, object]] = {}

    def add(template_id: str, name: str, product_id: str, *, order: str = "", frequency: str = "", duration: str = "", dispense: str = "", note: str = "") -> None:
        product = product_by_id.get(product_id)
        if not product:
            return
        template = templates.setdefault(template_id, {"d": template_id, "n": name, "r": []})
        rows = template["r"]
        if not isinstance(rows, list) or any(row.get("b") == product_id and row.get("o") == order for row in rows):
            return
        rows.append(pediatric_template_row(product_id, product, row_id=f"{template_id}_{len(rows) + 1}", order=order, frequency=frequency, duration=duration, dispense=dispense, note=note))
        template["c"] = len(rows)

    for item in peds_items:
        product_id = str(item.get("product_id") or "")
        if not product_id:
            continue
        generic = str(item.get("generic_key") or "").lower()
        form = str(item.get("form") or "").lower()
        reasons = "; ".join(str(reason) for reason in item.get("review_reasons") or [])
        if any(key in generic for key in ["paracetamol", "ibuprofen"]):
            add("peds_pain_fever_manual_review", "Pain / fever manual-review candidates", product_id, note=reasons)
        if any(key in generic for key in ["cetirizine", "loratadine", "chlorpheniramine", "desloratadine", "fexofenadine"]):
            add("peds_allergy_manual_review", "Allergy manual-review candidates", product_id, note=reasons)
        if any(key in generic for key in ["salbutamol", "montelukast", "bromhexine", "dextromethorphan"]):
            add("peds_respiratory_manual_review", "Respiratory manual-review candidates", product_id, note=reasons)
        if any(key in generic for key in ["simethicone", "racecadotril", "domperidone", "nystatin"]):
            add("peds_gi_manual_review", "GI manual-review candidates", product_id, note=reasons)
        if any(key in form for key in ["syrup", "suspension", "drops", "powder"]):
            add("peds_liquid_and_child_forms_review", "Liquid / child-form manual-review candidates", product_id, note=reasons)

    shortcut_rows = read_json("data/imported_guideline_patch/peds_dose_shortcuts_patch.json", {"items": []}).get("items", [])
    for row in shortcut_rows:
        bds = str(row.get("BDS") or "")
        if not bds.startswith("BDS") or str(row.get("Enabled") or "").upper() != "Y":
            continue
        dose_value = str(row.get("Dose_Value") or "")
        if dose_value.upper() in {"AVOID", "N/A"}:
            continue
        note = "; ".join(part for part in [str(row.get("Dose_Basis") or ""), str(row.get("Age_or_Weight_Note") or ""), str(row.get("Source_Anchor") or "")] if part)
        add(
            str(row.get("Disease_Key") or "pediatric_guideline_shortcuts_review"),
            str(row.get("Disease_Key") or "Pediatric guideline shortcuts review").replace("_", " ").title(),
            bds,
            note=f"Manual review shortcut: {note}",
        )

    return sorted(templates.values(), key=lambda item: str(item.get("n") or ""))


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


def merge_runtime_overlay_complaints(base: list[dict[str, object]]) -> list[dict[str, object]]:
    """Expose imported OPD overlay rows through the legacy frontend complaint schema."""
    complaint_index = read_json("data/core/complaint_index.json", {"items": []}).get("items", [])
    regimens = read_json("data/core/fast_regimen_master.json", {"regimens": []}).get("regimens", [])
    regimen_by_disease: dict[str, list[dict[str, object]]] = {}
    for regimen in regimens:
        if regimen.get("import_source") == "guideline_patch_20260516":
            regimen_by_disease.setdefault(str(regimen.get("disease_id") or ""), []).append(regimen)
    seen = {str(row.get("i") or "") for row in base}
    out = list(base)
    for complaint in complaint_index:
        if complaint.get("import_source") != "guideline_patch_20260516":
            continue
        complaint_id = str(complaint.get("complaint_id") or "")
        if not complaint_id or complaint_id in seen:
            continue
        disease_id = str(complaint.get("disease_id") or "")
        mapped_regimens = [frontend_regimen(row) for row in regimen_by_disease.get(disease_id, [])]
        out.append(
            {
                "i": complaint_id,
                "c": complaint.get("complaint") or complaint.get("normalized_input") or complaint_id,
                "d": disease_id,
                "g": complaint.get("complaint_group") or "",
                "a": complaint.get("age_group") or "",
                "p": complaint.get("priority") or 5,
                "mt": complaint.get("match_type") or "alias",
                "src": "guideline_patch_20260516",
                "manual_review": True,
                "r": mapped_regimens,
            }
        )
        seen.add(complaint_id)
    return out


def frontend_regimen(regimen: dict[str, object]) -> dict[str, object]:
    return {
        "i": regimen.get("regimen_id") or "",
        "d": regimen.get("display_name") or regimen.get("disease_name") or regimen.get("disease_id") or "",
        "w": regimen.get("likelihood_label") or regimen.get("use_when") or "",
        "y": bool(regimen.get("is_default")),
        "manual_review": True,
        "source_status": regimen.get("source_status", "pending_manual_review"),
        "fast_mode_allowed": False,
        "m": [frontend_line(line) for line in regimen.get("lines", [])],
    }


def frontend_line(line: dict[str, object]) -> dict[str, object]:
    line_type = str(line.get("line_type") or "")
    display_type = "RX NOW" if line_type == "RX_NOW" else line_type
    if line.get("non_drug_action"):
        display_type = "NON DRUG ACTION"
    return {
        "s": line.get("line_id") or "",
        "t": display_type,
        "i": line.get("product_id") or "",
        "n": line.get("display_name") or "",
        "o": line.get("order_text") or "",
        "u": line.get("duration_label") or "",
        "p": line.get("pack_label") or line.get("dispense_label") or "",
        "clinical_readiness": line.get("clinical_readiness", "manual_review_required"),
        "fast_mode_allowed": bool(line.get("fast_mode_allowed")),
        "missing_requirements": list(line.get("missing_requirements") or []),
        "source_status": line.get("source_status", "pending_manual_review"),
        "blocked_reason": line.get("blocked_reason") or "",
        "next_action": line.get("next_action") or "",
        "evidence_status": line.get("evidence_status", "pending_source_collection"),
        "evidence_score": line.get("evidence_score", 0),
        "evidence_confidence": line.get("evidence_confidence", "none"),
        "evidence_source_ids": list(line.get("evidence_source_ids") or []),
        "evidence_required_fields_missing": list(line.get("evidence_required_fields_missing") or ["source collection", "source extraction"]),
        "manual_review_required": True,
        "non_drug_action": bool(line.get("non_drug_action")),
        "quick_caution": line.get("quick_caution") or "",
        "quick_side_effects": line.get("quick_side_effects") or "",
    }


def main() -> int:
    meta = build()
    print(
        "built frontend seed: "
        f"drugs={meta['drugCount']} source_coverage={meta['source_coverage']} manual_review={meta['manual_review_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
