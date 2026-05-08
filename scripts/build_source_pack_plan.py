#!/usr/bin/env python3
"""Group coverage records into clinical source packs."""

from __future__ import annotations

from collections import defaultdict

from export_refresh_workbook import write_xlsx, union_columns
from medical_refresh_common import EXPORT_DIR, read_json, stable_id, write_csv, write_json, write_report

PACK_RULES = [
    ("thai_nlem_ndi_rdu", "Thai NLEM / NDI / RDU pack", ["product_label_source", "drug_choice_source"]),
    ("thai_moph_dms_outpatient", "Thai MOPH / DMS outpatient CPG pack", ["disease_strategy_source"]),
    ("thai_pediatric_dose", "Thai pediatric dose pack", ["pediatric_dose_source", "max_dose_source"]),
    ("antiviral_herpes_zoster", "Antiviral / herpes / zoster pack", ["adult_dose_source", "duration_source", "red_flag_source"]),
    ("antibiotic_stewardship_aware", "Antibiotic stewardship / WHO AWaRe pack", ["antibiotic_criteria_source", "no_antibiotic_source"]),
    ("uri_sore_throat_cough", "URI / sore throat / cough no-antibiotic pack", ["no_antibiotic_source"]),
    ("diarrhea_dehydration_ors", "Diarrhea / dehydration / ORS pediatric pack", ["pediatric_dose_source", "concentration_source"]),
    ("uti_outpatient_antibiotic", "UTI outpatient antibiotic pack", ["antibiotic_criteria_source", "duration_source"]),
    ("eye_red_flag", "Eye / red eye / conjunctivitis / red-flag pack", ["red_flag_source"]),
    ("allergy_antihistamine_nasal", "Allergy / allergic rhinitis / antihistamine / nasal steroid pack", ["disease_strategy_source"]),
    ("pain_fever_nsaid_paracetamol", "Pain / fever / NSAID / paracetamol pack", ["adult_dose_source", "pediatric_dose_source", "max_dose_source"]),
    ("skin_fungal_dermatitis", "Skin fungal / dermatitis / topical steroid-antifungal pack", ["disease_strategy_source"]),
    ("gi_dyspepsia_constipation", "GI / dyspepsia / GERD / constipation pack", ["disease_strategy_source"]),
    ("product_label_smpc", "Product label / SmPC pack", ["product_label_source", "concentration_source", "route_form_source"]),
]

THAI_TARGETS = ["ndi.fda.moph.go.th", "ndp.fda.moph.go.th", "fda.moph.go.th", "dms.moph.go.th", "moph.go.th", "Thai specialty society", "Thai Pediatric Society"]
INTL_TARGETS = ["WHO EML/EMLc", "WHO AWaRe", "CDC", "NICE", "IDSA", "GINA", "GOLD", "ACG", "AAP", "EAU", "AAO", "AAO-HNS", "DailyMed/SmPC for product metadata only"]


def choose_pack(record: dict) -> str:
    needs = set(record.get("exact_evidence_needed") or [])
    blob = " ".join(str(record.get(k, "")).lower() for k in ["disease_key", "drug_name", "composition"])
    if any(x in blob for x in ["acyclovir", "zoster", "shingles", "herpes"]):
        return "antiviral_herpes_zoster"
    if record.get("pediatric_flag"):
        if any(x in blob for x in ["diarrhea", "ors", "dehydration"]):
            return "diarrhea_dehydration_ors"
        if any(x in blob for x in ["paracetamol", "ibuprofen", "fever", "pain"]):
            return "pain_fever_nsaid_paracetamol"
        return "thai_pediatric_dose"
    if record.get("antibiotic_flag"):
        if any(x in blob for x in ["uti", "dysuria", "cystitis"]):
            return "uti_outpatient_antibiotic"
        return "antibiotic_stewardship_aware"
    if "product_label_source" in needs and len(needs) <= 2:
        return "product_label_smpc"
    if any(x in blob for x in ["eye", "conjunctivitis", "photophobia", "vision"]):
        return "eye_red_flag"
    if any(x in blob for x in ["uri", "sore", "cough", "bronchitis"]):
        return "uri_sore_throat_cough"
    if any(x in blob for x in ["allergic", "rhinitis", "antihistamine"]):
        return "allergy_antihistamine_nasal"
    if any(x in blob for x in ["tinea", "fungal", "dermatitis", "rash"]):
        return "skin_fungal_dermatitis"
    if any(x in blob for x in ["gerd", "dyspepsia", "constipation", "diarrhea"]):
        return "gi_dyspepsia_constipation"
    return "thai_moph_dms_outpatient"


def main() -> int:
    records = read_json("data/source_refresh/refresh_coverage_matrix.json", {"records": []}).get("records", [])
    grouped = defaultdict(list)
    for record in records:
        grouped[choose_pack(record)].append(record)
    plans = []
    rule_map = {key: label for key, label, _needs in PACK_RULES}
    for key, label, _needs in PACK_RULES:
        rows = grouped.get(key, [])
        diseases = sorted({r.get("disease_key") for r in rows if r.get("disease_key")})
        generics = sorted({r.get("generic_name") or r.get("composition") for r in rows if r.get("generic_name") or r.get("composition")})
        needs = sorted({need for r in rows for need in (r.get("exact_evidence_needed") or [])})
        plans.append(
            {
                "pack_id": key,
                "clinical_domain": label,
                "diseases_covered": diseases[:80],
                "generics_covered": generics[:120],
                "workbook_rows_covered": len(rows),
                "coverage_ids": [r["coverage_id"] for r in rows],
                "evidence_fields_needed": needs,
                "thai_first_source_targets": THAI_TARGETS,
                "international_fallback_targets": INTL_TARGETS,
                "textbook_user_provided_source_targets": ["source_guidelines/textbooks/"],
                "search_queries": [
                    f"{label} official guideline Thai RDU MOPH",
                    f"{label} WHO CDC NICE guideline dose duration criteria",
                ],
                "minimum_acceptable_source_count": 1 if rows else 0,
                "cannot_unlock_without": needs,
            }
        )
    columns = union_columns(plans)
    write_json("data/source_refresh/source_pack_plan.json", {"packs": plans})
    write_csv(EXPORT_DIR / "Source_Pack_Plan.csv", plans, columns)
    original = (EXPORT_DIR / "Druglist_Data_Refresh_Master.xlsx").read_bytes()
    write_xlsx({"Source_Pack_Plan": (plans, columns)})
    (EXPORT_DIR / "Druglist_Data_Refresh_Master.xlsx").replace(EXPORT_DIR / "Source_Pack_Plan.xlsx")
    (EXPORT_DIR / "Druglist_Data_Refresh_Master.xlsx").write_bytes(original)
    write_report(
        "reports/source_refresh/source_pack_plan_report.md",
        "Source Pack Plan Report",
        [
            f"- Source packs: {len(plans)}",
            f"- Coverage rows assigned: {sum(p['workbook_rows_covered'] for p in plans)}",
            "",
            "## Pack Counts",
            *[f"- {p['pack_id']}: {p['workbook_rows_covered']}" for p in plans],
        ],
    )
    print(f"build_source_pack_plan: packs={len(plans)} records={len(records)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
