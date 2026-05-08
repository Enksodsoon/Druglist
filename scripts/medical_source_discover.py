#!/usr/bin/env python3
"""Generate official-source discovery tasks and conservative URL candidates."""

from __future__ import annotations

from collections import OrderedDict

from medical_refresh_common import (
    OFFICIAL_SOURCE_SEEDS,
    high_risk_rows,
    official_domain,
    read_json,
    stable_id,
    write_json,
    write_report,
)

SOURCE_TARGETS = [
    "Thai NLEM / NDI / FDA / National Drug Policy Division",
    "Thai RDU / MOPH / DMS / Thai clinical practice guidelines",
    "Thai specialty society guidelines",
    "Thai Pediatric Society or pediatric subspecialty guidelines",
    "WHO EML / EMLc / WHO disease guidance / WHO AWaRe",
    "CDC / NICE / IDSA / GINA / GOLD / ACG / AAP / EAU / AAO / AAO-HNS",
    "Product label / SmPC / package insert for product metadata only",
]


def task_from_row(row: dict[str, str], priority: int) -> dict[str, object]:
    disease = row.get("disease_key") or ""
    generic = row.get("generic_name") or row.get("composition") or row.get("drug_name") or ""
    drug = row.get("drug_name") or generic
    blob = " ".join(str(v) for v in row.values()).lower()
    if any(token in blob for token in ["acyclovir", "zoster", "shingles", "herpes"]):
        question = "Verify antiviral indication, adult dose, frequency, duration, timing window, and red flags."
        source_type = "disease guideline"
    elif any(token in blob for token in ["antibiotic", "amoxicillin", "cephalexin", "norfloxacin", "azithromycin"]):
        question = "Verify antibiotic indication criteria, no-antibiotic default, dose, duration, and stewardship caveats."
        source_type = "antibiotic/RDU guideline"
    elif any(token in blob for token in ["child", "pediatric", "paracetamol", "ibuprofen", "ors", "cetirizine"]):
        question = "Verify pediatric dose, age/BW gate, concentration, frequency, duration, and max dose."
        source_type = "pediatric guideline/formulary"
    elif any(token in blob for token in ["eye", "red eye", "photophobia", "vision"]):
        question = "Verify eye red flags, referral criteria, and safe outpatient support."
        source_type = "clinical guideline"
    else:
        question = "Verify source-backed indication, dose/duration if applicable, caution, and readiness."
        source_type = "clinical guideline"
    query = f"{disease} {drug} {question} official guideline"
    return {
        "source_task_id": stable_id("src_task", row.get("regimen_id"), row.get("product_id"), question),
        "disease_key": disease,
        "regimen_id": row.get("regimen_id") or "",
        "product_id": row.get("product_id") or "",
        "generic_name": generic,
        "clinical_question": question,
        "source_type_needed": source_type,
        "source_priority": priority,
        "search_query": query,
        "thai_first_search_query": f"{disease} {drug} แนวทางการรักษา กระทรวงสาธารณสุข RDU",
        "international_fallback_query": query + " WHO CDC NICE IDSA",
        "exact_next_source_needed": row.get("next_action") or question,
    }


def main() -> int:
    pack_plan = read_json("data/source_refresh/source_pack_plan.json", {"packs": []}).get("packs", [])
    tasks_by_id: OrderedDict[str, dict[str, object]] = OrderedDict()
    if pack_plan:
        for pack in pack_plan:
            for query in pack.get("search_queries") or []:
                task = {
                    "source_task_id": stable_id("src_task", pack.get("pack_id"), query),
                    "pack_id": pack.get("pack_id"),
                    "disease_key": "; ".join((pack.get("diseases_covered") or [])[:20]),
                    "regimen_id": "",
                    "product_id": "",
                    "generic_name": "; ".join((pack.get("generics_covered") or [])[:20]),
                    "clinical_question": f"Find accepted source pack evidence for {pack.get('clinical_domain')}",
                    "source_type_needed": "; ".join(pack.get("evidence_fields_needed") or []),
                    "source_priority": 1 if pack.get("workbook_rows_covered") else 5,
                    "search_query": query,
                    "thai_first_search_query": f"{pack.get('clinical_domain')} แนวทางการรักษา RDU MOPH",
                    "international_fallback_query": f"{pack.get('clinical_domain')} WHO CDC NICE guideline dose duration criteria",
                    "exact_next_source_needed": "; ".join(pack.get("cannot_unlock_without") or []),
                    "rows_potentially_covered": pack.get("coverage_ids") or [],
                }
                tasks_by_id[task["source_task_id"]] = task
    else:
        rows = high_risk_rows()
        candidates = rows["high"][:160] + rows["antibiotic"][:80]
        for index, row in enumerate(candidates, start=1):
            task = task_from_row(row, min(5, 1 + index // 40))
            tasks_by_id[task["source_task_id"]] = task
    tasks = list(tasks_by_id.values())
    queries = [
        {
            "source_task_id": task["source_task_id"],
            "search_query": task["search_query"],
            "thai_first_search_query": task["thai_first_search_query"],
            "international_fallback_query": task["international_fallback_query"],
        }
        for task in tasks
    ]
    candidate_rows = []
    for seed in OFFICIAL_SOURCE_SEEDS:
        matching_task = next((task for task in tasks if seed["domain"].replace("_", " ") in str(task).lower() or seed["task_hint"].split()[0].lower() in str(task).lower()), tasks[0] if tasks else {})
        status = "candidate_official" if official_domain(seed["url"]) else "candidate_needs_text_check"
        candidate_rows.append(
            {
                "candidate_id": stable_id("src_candidate", seed["source_id"], seed["url"]),
                "source_task_id": matching_task.get("source_task_id", ""),
                "source_id_suggestion": seed["source_id"],
                "disease_key": matching_task.get("disease_key", ""),
                "regimen_id": matching_task.get("regimen_id", ""),
                "product_id": matching_task.get("product_id", ""),
                "generic_name": matching_task.get("generic_name", ""),
                "clinical_question": matching_task.get("clinical_question", seed["task_hint"]),
                "source_priority": 1,
                "search_query": seed["task_hint"],
                "candidate_url": seed["url"],
                "candidate_title": seed["title"],
                "organization": seed["organization"],
                "country": seed["country"],
                "source_type": seed["source_type"],
                "year": seed["year"],
                "access_status": "pending_text_check",
                "confidence_score": 0.75,
                "status": status,
                "rejection_reason": "",
                "expected_claims": seed["expected_claims"],
                "pack_id": matching_task.get("pack_id", ""),
                "rows_potentially_covered": matching_task.get("rows_potentially_covered", []),
            }
        )
    by_pack = []
    for candidate in candidate_rows:
        by_pack.append(
            {
                "source_candidate_id": candidate["candidate_id"],
                "pack_id": candidate.get("pack_id") or "unmatched_seed",
                "source_title": candidate["candidate_title"],
                "organization": candidate["organization"],
                "url_or_file": candidate["candidate_url"],
                "source_type": candidate["source_type"],
                "country": candidate["country"],
                "year_version": candidate["year"],
                "diseases_covered": candidate.get("disease_key", ""),
                "drugs_covered": candidate.get("generic_name", ""),
                "evidence_fields_likely": candidate.get("expected_claims", []),
                "confidence_score": candidate.get("confidence_score", 0),
                "status": candidate.get("status"),
                "rejection_reason": candidate.get("rejection_reason", ""),
                "rows_potentially_covered": candidate.get("rows_potentially_covered", []),
            }
        )
    write_json("data/source_refresh/source_discovery_tasks.json", {"tasks": tasks})
    write_json("data/source_refresh/source_search_queries.json", {"queries": queries, "source_targets": SOURCE_TARGETS})
    write_json("data/source_refresh/source_url_candidates.json", {"candidates": candidate_rows})
    write_json("data/source_refresh/source_candidates_by_pack.json", {"candidates": by_pack})
    write_report(
        "reports/source_refresh/source_discovery_report.md",
        "Source Discovery Report",
        [
            f"- Discovery tasks: {len(tasks)}",
            f"- URL candidates: {len(candidate_rows)}",
            f"- Pack-aware candidates: {len(by_pack)}",
            f"- Candidate official sources: {sum(1 for c in candidate_rows if c['status'] == 'candidate_official')}",
            "- Auto-accepted sources: 0",
            "- Rule: search results never become accepted until source text is accessible and relevant snippets are confirmed.",
        ],
    )
    print(f"medical_source_discover: tasks={len(tasks)} candidates={len(candidate_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
