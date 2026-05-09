#!/usr/bin/env python3
"""Build the first-unlock source acquisition priority queue.

This queue is deliberately row-specific. It does not accept sources or verify
claims; it records exact missing evidence needed before a row can move.
"""

from __future__ import annotations

from collections import defaultdict

from export_refresh_workbook import union_columns, write_xlsx
from medical_refresh_common import EXPORT_DIR, read_csv_sheet, stable_id, write_csv, write_json, write_report

OUT_JSON = "data/source_refresh/source_acquisition_priority.json"
OUT_XLSX = EXPORT_DIR / "Source_Acquisition_Priority.xlsx"
OUT_REPORT = "reports/source_refresh/source_acquisition_priority_report.md"

PRIORITY_DEFS = [
    {
        "label": "acyclovir_herpes_zoster_adult",
        "rank": 1,
        "disease_tokens": ["herpes_zoster", "zoster", "shingles"],
        "generic_tokens": ["acyclovir", "aciclovir"],
        "exact_missing_evidence_fields": ["adult dose", "frequency", "duration", "timing window", "red flags/referral"],
        "minimum_acceptable_source_type": "official guideline or national formulary with disease-specific regimen",
        "thai_query": "กระทรวงสาธารณสุข acyclovir herpes zoster shingles adult dose duration guideline",
        "english_query": "official herpes zoster acyclovir 800 mg five times daily duration guideline",
        "targets": ["moph.go.th", "dms.moph.go.th", "cdc.gov", "nice.org.uk", "gov.br", "who.int"],
        "safety_priority": "A",
        "can_unlock_ready": "yes_if_exact_current_row_matches",
    },
    {
        "label": "herpes_labialis_adult",
        "rank": 2,
        "disease_tokens": ["herpes_labialis", "cold sore"],
        "generic_tokens": ["acyclovir", "aciclovir"],
        "exact_missing_evidence_fields": ["indication", "adult dose", "frequency", "duration", "route"],
        "minimum_acceptable_source_type": "official guideline with herpes labialis regimen",
        "thai_query": "กระทรวงสาธารณสุข acyclovir herpes labialis dose duration guideline",
        "english_query": "official herpes labialis oral acyclovir dose duration guideline",
        "targets": ["moph.go.th", "dms.moph.go.th", "cdc.gov", "nice.org.uk"],
        "safety_priority": "A",
        "can_unlock_ready": "yes_if_exact_current_row_matches",
    },
    {
        "label": "pediatric_paracetamol_fever_pain",
        "rank": 3,
        "disease_tokens": ["fever", "pain", "uri"],
        "generic_tokens": ["paracetamol", "acetaminophen"],
        "exact_missing_evidence_fields": ["pediatric dose", "age/BW rule", "frequency", "max dose", "concentration"],
        "minimum_acceptable_source_type": "pediatric guideline/formulary plus product concentration source",
        "thai_query": "Thai pediatric paracetamol dose mg kg max dose fever guideline",
        "english_query": "official pediatric paracetamol mg/kg dose max dose guideline",
        "targets": ["moph.go.th", "who.int", "nice.org.uk", "aap.org"],
        "safety_priority": "A",
        "can_unlock_ready": "yes_if_all_pediatric_gates_pass",
    },
    {
        "label": "viral_uri_no_antibiotic",
        "rank": 7,
        "disease_tokens": ["uri", "cough", "cold", "viral"],
        "generic_tokens": [],
        "exact_missing_evidence_fields": ["no antibiotic criteria", "red flags/referral"],
        "minimum_acceptable_source_type": "antimicrobial stewardship guideline",
        "thai_query": "RDU viral URI no antibiotic guideline Thailand cough cold",
        "english_query": "official acute cough upper respiratory tract infection do not offer antibiotic guideline",
        "targets": ["moph.go.th", "nice.org.uk", "cdc.gov"],
        "safety_priority": "A",
        "can_unlock_ready": "yes_for_no_antibiotic_safety_rule_only",
    },
    {
        "label": "bacterial_conjunctivitis_topical_antibiotic",
        "rank": 9,
        "disease_tokens": ["bacterial_conjunctivitis"],
        "generic_tokens": ["chloramphenicol", "fusidic", "oxytetracycline"],
        "exact_missing_evidence_fields": ["bacterial criteria", "drug choice", "adult dose/frequency/duration", "red flags"],
        "minimum_acceptable_source_type": "ophthalmology or antimicrobial guideline",
        "thai_query": "Thai guideline bacterial conjunctivitis chloramphenicol eye drops dose",
        "english_query": "official bacterial conjunctivitis chloramphenicol eye drops dose guideline",
        "targets": ["moph.go.th", "nice.org.uk", "aao.org", "cdc.gov"],
        "safety_priority": "A",
        "can_unlock_ready": "yes_if_criteria_and_dose_duration_match",
    },
    {
        "label": "red_eye_red_flags",
        "rank": 11,
        "disease_tokens": ["red_eye", "photophobia", "vision"],
        "generic_tokens": [],
        "exact_missing_evidence_fields": ["red flags", "referral criteria"],
        "minimum_acceptable_source_type": "ophthalmology guideline",
        "thai_query": "Thai red eye pain photophobia vision loss urgent referral guideline",
        "english_query": "official red eye pain photophobia vision loss urgent referral guideline",
        "targets": ["moph.go.th", "aao.org", "nice.org.uk", "cdc.gov"],
        "safety_priority": "A",
        "can_unlock_ready": "yes_for_blocking_rule_only",
    },
]


def row_blob(row: dict[str, str]) -> str:
    return " ".join(str(v or "") for v in row.values()).lower()


def matching_rows(defn: dict[str, object], rows: list[dict[str, str]]) -> list[dict[str, str]]:
    disease_tokens = [str(x).lower() for x in defn["disease_tokens"]]
    generic_tokens = [str(x).lower() for x in defn["generic_tokens"]]
    out = []
    for row in rows:
        blob = row_blob(row)
        disease_match = not disease_tokens or any(token in blob for token in disease_tokens)
        generic_match = not generic_tokens or any(token in blob for token in generic_tokens)
        if disease_match and generic_match:
            out.append(row)
    return out


def main() -> int:
    regimen_rows = read_csv_sheet("2_Regimen_Master_Export")
    peds_rows = read_csv_sheet("6_Pediatric_Dosing")
    antibiotic_rows = read_csv_sheet("7_Antibiotic_Rows")
    all_rows = regimen_rows + peds_rows + antibiotic_rows
    records = []
    for defn in PRIORITY_DEFS:
        rows = matching_rows(defn, all_rows)
        ids_by_regimen = sorted({r.get("regimen_id", "") for r in rows if r.get("regimen_id")})
        ids_by_product = sorted({r.get("product_id", "") for r in rows if r.get("product_id")})
        diseases = sorted({r.get("disease_key", "") for r in rows if r.get("disease_key")})
        generics = sorted({r.get("generic_name", "") or r.get("composition", "") for r in rows if r.get("generic_name") or r.get("composition")})
        records.append(
            {
                "source_need_id": stable_id("need", defn["label"]),
                "source_pack_id": defn["label"],
                "priority_rank": defn["rank"],
                "disease_key": "; ".join(diseases),
                "generic_name": "; ".join(generics[:20]),
                "product_id": "; ".join(ids_by_product[:40]),
                "regimen_id": "; ".join(ids_by_regimen[:40]),
                "rows_affected": len(rows),
                "exact_missing_evidence_fields": "; ".join(defn["exact_missing_evidence_fields"]),
                "minimum_acceptable_source_type": defn["minimum_acceptable_source_type"],
                "thai_preferred_query": defn["thai_query"],
                "english_fallback_query": defn["english_query"],
                "suggested_official_source_targets": "; ".join(defn["targets"]),
                "expected_unlock_count": len(rows),
                "safety_priority": defn["safety_priority"],
                "can_unlock_ready": defn["can_unlock_ready"],
            }
        )
    records.sort(key=lambda row: (str(row["safety_priority"]), int(row["priority_rank"])))
    write_json(OUT_JSON, {"source_needs": records})
    columns = union_columns(records, [])
    write_csv(EXPORT_DIR / "source_acquisition_priority.csv", records, columns)
    base = EXPORT_DIR / "Druglist_Data_Refresh_Master.xlsx"
    original = base.read_bytes() if base.exists() else None
    write_xlsx({"Source_Acquisition_Priority": (records, columns)})
    base.replace(OUT_XLSX)
    if original is not None:
        base.write_bytes(original)
    by_priority = defaultdict(int)
    for record in records:
        by_priority[record["safety_priority"]] += int(record["rows_affected"])
    write_report(
        OUT_REPORT,
        "Source Acquisition Priority Report",
        [
            f"- Source needs: {len(records)}",
            f"- Rows affected by priority A needs: {by_priority['A']}",
            "- This is an acquisition queue only; no source or clinical claim is accepted here.",
            "- Highest-risk target remains acyclovir/herpes zoster because current row duration may conflict with official sources.",
        ],
    )
    print(f"source_acquisition_priority: needs={len(records)} rows={sum(int(r['rows_affected']) for r in records)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
