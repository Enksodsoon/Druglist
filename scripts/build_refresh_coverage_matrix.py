#!/usr/bin/env python3
"""Build row-level medical refresh coverage matrix with explicit final statuses."""

from __future__ import annotations

from collections import Counter

from export_refresh_workbook import write_xlsx, union_columns
from medical_refresh_common import EXPORT_DIR, lower_blob, read_csv_sheet, stable_id, write_csv, write_json, write_report

TARGET_SHEETS = [
    "2_Regimen_Master_Export",
    "6_Pediatric_Dosing",
    "7_Antibiotic_Rows",
    "8_Source_Evidence_Queue",
    "9_Clinical_QC",
    "11_OPD_Fast_Index_Template",
    "12_Drug_Short_Lookup_Template",
]

FINAL_STATUSES = {
    "ready_source_verified",
    "usable_with_warning_source_partial",
    "label_only_catalog",
    "manual_review_required_with_exact_reason",
    "blocked_source_missing",
    "blocked_vague_source",
    "blocked_conflict",
    "blocked_peds_missing_required_fields",
    "blocked_antibiotic_missing_criteria",
    "blocked_safety_red_flag",
}


def needs_for(row: dict[str, str], sheet: str) -> list[str]:
    blob = lower_blob(row)
    needs = []
    if sheet == "6_Pediatric_Dosing" or "pediatric" in blob or "child" in blob:
        needs += ["pediatric_dose_source", "max_dose_source", "concentration_source", "route_form_source"]
    if sheet == "7_Antibiotic_Rows" or "antibiotic" in blob:
        needs += ["antibiotic_criteria_source", "duration_source", "adult_dose_source"]
    if any(token in blob for token in ["acyclovir", "zoster", "shingles", "herpes"]):
        needs += ["disease_strategy_source", "adult_dose_source", "duration_source", "red_flag_source"]
    if any(token in blob for token in ["red eye", "photophobia", "vision", "severe", "petechiae"]):
        needs += ["red_flag_source"]
    if not row.get("source_ids") and row.get("source_status") != "source_verified":
        needs += ["disease_strategy_source"]
    if sheet == "12_Drug_Short_Lookup_Template":
        needs = ["product_label_source"]
    return sorted(set(needs or ["disease_strategy_source"]))


def classify(row: dict[str, str], sheet: str, needs: list[str]) -> tuple[str, str, str]:
    blob = lower_blob(row)
    source_verified = row.get("source_status") == "source_verified" or bool(row.get("source_ids"))
    current = row.get("clinical_readiness") or row.get("dose_output_status") or row.get("review_status") or ""
    if "conflict" in blob:
        return "blocked_conflict", "conflicting source or audit signal requires clinical review", "resolve conflicting evidence"
    if "red flag" in blob or any(x in blob for x in ["photophobia", "vision loss", "petechiae", "severe dehydration"]):
        return "blocked_safety_red_flag", "red-flag source/referral gate required", "add red-flag/referral source and keep routine prescribing blocked"
    if sheet == "6_Pediatric_Dosing":
        missing = [need for need in needs if need in {"pediatric_dose_source", "max_dose_source", "concentration_source", "route_form_source"}]
        if source_verified and not missing and current == "ready":
            return "ready_source_verified", "complete pediatric source gates present", "eligible for guarded pediatric import"
        return "blocked_peds_missing_required_fields", "; ".join(missing or ["accepted pediatric source required"]), "add accepted pediatric source with age/BW, dose basis, max dose, concentration, route/form"
    if sheet == "7_Antibiotic_Rows" or "antibiotic" in blob:
        if source_verified and current == "ready" and "duration_source" not in needs:
            return "ready_source_verified", "source-backed antibiotic criteria and dose present", "eligible for import"
        if any(x in blob for x in ["viral", "simple diarrhea", "allergic rhinitis", "dry eye", "allergic conjunctivitis"]):
            return "blocked_antibiotic_missing_criteria", "no-routine-antibiotic condition unless criteria source proves otherwise", "add no-antibiotic or bacterial criteria source"
        return "blocked_antibiotic_missing_criteria", "antibiotic disease criteria/dose/duration source incomplete", "add accepted antibiotic/RDU guideline with criteria, dose, duration"
    if sheet == "12_Drug_Short_Lookup_Template":
        return "label_only_catalog", "drug short lookup is product/catalog metadata only", "use label/source only for product metadata, not disease regimen readiness"
    if source_verified and current == "ready":
        return "ready_source_verified", "source-backed ready status present", "eligible for import"
    if str(row.get("fast_mode_allowed")).lower() == "true" or current == "usable_with_warning":
        return "usable_with_warning_source_partial", "low-risk/supportive row has partial or pending source context", "attach accepted source before marking ready"
    if "vague" in blob or "standard dose" in blob or "as appropriate" in blob:
        return "blocked_vague_source", "source text is vague or lacks exact dose/criteria", "find exact dose/criteria source"
    if sheet in {"8_Source_Evidence_Queue", "9_Clinical_QC"}:
        return "manual_review_required_with_exact_reason", row.get("issue_type") or row.get("notes") or "quality/source queue item requires explicit resolution", "resolve linked source/evidence queue item"
    return "blocked_source_missing", row.get("blocked_reason") or row.get("missing_requirements") or "accepted source-backed evidence missing", row.get("next_action") or "add accepted source with snippet and row mapping"


def coverage_record(sheet: str, row_number: int, row: dict[str, str]) -> dict[str, object]:
    needs = needs_for(row, sheet)
    status, reason, action = classify(row, sheet, needs)
    blob = lower_blob(row)
    high_risk = any(token in blob for token in ["acyclovir", "zoster", "shingles", "herpes", "antibiotic", "pediatric", "child", "eye", "nsaid", "steroid", "cough", "cold"])
    return {
        "coverage_id": stable_id("coverage", sheet, row_number, row.get("regimen_id"), row.get("product_id"), row.get("disease_key")),
        "sheet_name": sheet,
        "row_number": row_number,
        "product_id": row.get("product_id") or row.get("BDS") or "",
        "regimen_id": row.get("regimen_id") or "",
        "disease_key": row.get("disease_key") or "",
        "disease_name": row.get("disease_name") or "",
        "complaint_key": row.get("complaint_key") or "",
        "generic_name": row.get("generic_name") or row.get("generic") or "",
        "drug_name": row.get("drug_name") or row.get("display_name") or row.get("brand_name") or "",
        "composition": row.get("composition") or "",
        "BDS": row.get("BDS") or row.get("product_id") or "",
        "sig": row.get("sig") or row.get("order_text") or "",
        "duration": row.get("duration") or row.get("duration_label") or "",
        "route": row.get("route") or "",
        "form": row.get("form") or row.get("dosage_form") or "",
        "pediatric_flag": sheet == "6_Pediatric_Dosing" or "pediatric" in blob or "child" in blob,
        "antibiotic_flag": sheet == "7_Antibiotic_Rows" or "antibiotic" in blob,
        "high_risk_flag": high_risk,
        "current_readiness": row.get("clinical_readiness") or row.get("dose_output_status") or row.get("review_status") or "",
        "current_source_status": row.get("source_status") or "",
        "exact_evidence_needed": needs,
        "minimum_source_type": "product label" if needs == ["product_label_source"] else "accepted guideline/source with snippet",
        "source_priority": 1 if high_risk else 3,
        "final_status": status,
        "final_reason": reason,
        "next_action": action,
    }


def main() -> int:
    records = []
    for sheet in TARGET_SHEETS:
        for index, row in enumerate(read_csv_sheet(sheet), start=2):
            records.append(coverage_record(sheet, index, row))
    counts = Counter(record["final_status"] for record in records)
    need_counts = Counter(need for record in records for need in record["exact_evidence_needed"])
    write_json("data/source_refresh/refresh_coverage_matrix.json", {"records": records, "final_statuses": sorted(FINAL_STATUSES)})
    columns = union_columns(records)
    write_csv(EXPORT_DIR / "Refresh_Coverage_Matrix.csv", records, columns)
    original = (EXPORT_DIR / "Druglist_Data_Refresh_Master.xlsx").read_bytes()
    write_xlsx({"Refresh_Coverage_Matrix": (records, columns)})
    (EXPORT_DIR / "Druglist_Data_Refresh_Master.xlsx").replace(EXPORT_DIR / "Refresh_Coverage_Matrix.xlsx")
    (EXPORT_DIR / "Druglist_Data_Refresh_Master.xlsx").write_bytes(original)
    write_report(
        "reports/source_refresh/refresh_coverage_matrix_report.md",
        "Refresh Coverage Matrix Report",
        [
            f"- Coverage records: {len(records)}",
            f"- Rows requiring evidence: {sum(1 for r in records if r['final_status'] != 'ready_source_verified')}",
            f"- Rows needing disease guideline: {need_counts['disease_strategy_source']}",
            f"- Rows needing product label only: {need_counts['product_label_source']}",
            f"- Rows needing pediatric dose source: {need_counts['pediatric_dose_source']}",
            f"- Rows needing antibiotic criteria source: {need_counts['antibiotic_criteria_source']}",
            f"- Rows needing red flag source: {need_counts['red_flag_source']}",
            "",
            "## Final Status Counts",
            *[f"- {key}: {counts[key]}" for key in sorted(counts)],
        ],
    )
    print(f"build_refresh_coverage_matrix: records={len(records)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
