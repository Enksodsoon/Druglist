#!/usr/bin/env python3
"""Resolve first-unlock targets from exact claims without fabricating changes."""

from __future__ import annotations

import re

from export_refresh_workbook import union_columns, write_xlsx
from medical_refresh_common import EXPORT_DIR, read_csv_sheet, read_json, stable_id, write_csv, write_json, write_report

OUT_JSON = "data/source_refresh/first_unlock_results.json"
OUT_XLSX = EXPORT_DIR / "First_Unlock_Matrix.xlsx"


def norm(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def duration_days(value: str) -> int | None:
    m = re.search(r"(\d+)\s*day", norm(value))
    return int(m.group(1)) if m else None


def zoster_results(claims: list[dict[str, object]]) -> list[dict[str, object]]:
    rows = [
        row for row in read_csv_sheet("2_Regimen_Master_Export")
        if "zoster" in (row.get("disease_key", "") + " " + row.get("disease_name", "")).lower()
        and "acyclovir" in (row.get("composition", "") + " " + row.get("drug_name", "")).lower()
    ]
    zoster_claims = [claim for claim in claims if claim.get("disease_key") == "herpes_zoster_adult" and claim.get("claim_type") == "adult_dose"]
    results = []
    for row in rows:
        row_duration = duration_days(row.get("duration", ""))
        claim = zoster_claims[0] if zoster_claims else {}
        claim_duration = duration_days((claim.get("dose_struct") or {}).get("duration", "") if claim else "")
        has_exact = bool(claim)
        duration_match = bool(row_duration and claim_duration and row_duration == claim_duration)
        sig_match = "5x/day" in norm(row.get("sig", "")) or "5 times" in norm(row.get("sig", ""))
        if has_exact and duration_match and sig_match:
            status = "ready_source_verified"
            readiness = "ready"
            fast_allowed = "true"
            reason = "exact zoster acyclovir dose/frequency/duration matched accepted source"
            missing = ""
        elif has_exact and not duration_match:
            status = "blocked_conflict"
            readiness = "blocked"
            fast_allowed = "false"
            reason = f"accepted source supports {claim_duration} days but workbook row duration is {row.get('duration') or 'missing'}"
            missing = "resolve duration conflict before clinical unlock"
        else:
            status = "blocked_source_missing"
            readiness = "blocked"
            fast_allowed = "false"
            reason = "no exact accepted source-backed zoster acyclovir dose/frequency/duration claim"
            missing = "adult zoster acyclovir dose, frequency, duration"
        results.append(
            {
                "unlock_id": stable_id("unlock", row.get("regimen_id"), row.get("product_id"), "zoster"),
                "target": "acyclovir_zoster",
                "regimen_id": row.get("regimen_id", ""),
                "product_id": row.get("product_id", ""),
                "disease_key": row.get("disease_key", ""),
                "drug_name": row.get("drug_name", ""),
                "current_sig": row.get("sig", ""),
                "current_duration": row.get("duration", ""),
                "final_verification_status": status,
                "final_clinical_readiness": readiness,
                "final_fast_mode_allowed": fast_allowed,
                "evidence_claim_ids": claim.get("claim_id", "") if claim else "",
                "source_ids": claim.get("source_id", "") if claim else "",
                "source_titles": claim.get("source_title", "") if claim else "",
                "source_urls": claim.get("url_or_file", "") if claim else "",
                "source_snippets_short": claim.get("short_snippet", "") if claim else "",
                "exact_evidence_missing": missing,
                "exact_block_reason": reason,
                "exact_next_action": "update only after clinician/source review confirms whether workbook duration should change to the cited source duration",
                "can_show_in_main_builder": "true",
                "can_show_in_peds_page": "false",
                "can_show_in_swaps": "false",
                "antiviral_unlock_status": status,
            }
        )
    return results


def uri_results(claims: list[dict[str, object]]) -> list[dict[str, object]]:
    claims = [claim for claim in claims if claim.get("claim_type") == "no_antibiotic_criteria" and claim.get("disease_key") == "uri_wet_cough_adult"]
    rows = [row for row in read_csv_sheet("2_Regimen_Master_Export") if row.get("disease_key") == "uri_wet_cough_adult"]
    results = []
    if not rows:
        return results
    claim_ids = "; ".join(claim.get("claim_id", "") for claim in claims)
    source_ids = "; ".join(sorted({claim.get("source_id", "") for claim in claims if claim.get("source_id")}))
    snippets = " | ".join(claim.get("short_snippet", "")[:240] for claim in claims[:2])
    for row in rows:
        results.append(
            {
                "unlock_id": stable_id("unlock", row.get("regimen_id"), row.get("product_id"), "uri_no_antibiotic"),
                "target": "viral_uri_no_antibiotic",
                "regimen_id": row.get("regimen_id", ""),
                "product_id": row.get("product_id", ""),
                "disease_key": row.get("disease_key", ""),
                "drug_name": row.get("drug_name", ""),
                "current_sig": row.get("sig", ""),
                "current_duration": row.get("duration", ""),
                "final_verification_status": "usable_with_warning_source_partial" if claims else "blocked_source_missing",
                "final_clinical_readiness": row.get("clinical_readiness") or "usable_with_warning",
                "final_fast_mode_allowed": str(row.get("fast_mode_allowed", "")).lower(),
                "evidence_claim_ids": claim_ids,
                "source_ids": source_ids,
                "source_titles": "; ".join(sorted({claim.get("source_title", "") for claim in claims if claim.get("source_title")})),
                "source_urls": "; ".join(sorted({claim.get("url_or_file", "") for claim in claims if claim.get("url_or_file")})),
                "source_snippets_short": snippets,
                "exact_evidence_missing": "" if claims else "no-antibiotic source",
                "exact_block_reason": "" if claims else "no source-backed URI no-antibiotic rule",
                "exact_next_action": "keep symptomatic rows source-gated; do not add antibiotic without bacterial criteria",
                "can_show_in_main_builder": "true",
                "can_show_in_peds_page": "false",
                "can_show_in_swaps": "true",
                "antibiotic_unlock_status": "no_antibiotic_rule_source_backed" if claims else "blocked_antibiotic_missing_criteria",
            }
        )
    return results


def main() -> int:
    claims = read_json("data/source_refresh/exact_evidence_claims.json", {"claims": []}).get("claims", [])
    results = zoster_results(claims) + uri_results(claims)
    write_json(OUT_JSON, {"results": results})
    columns = union_columns(results, [])
    write_csv(EXPORT_DIR / "first_unlock_matrix.csv", results, columns)
    base = EXPORT_DIR / "Druglist_Data_Refresh_Master.xlsx"
    original = base.read_bytes() if base.exists() else None
    write_xlsx({"First_Unlock_Matrix": (results, columns)})
    base.replace(OUT_XLSX)
    if original is not None:
        base.write_bytes(original)
    ready = sum(1 for row in results if row.get("final_verification_status") == "ready_source_verified")
    warning = sum(1 for row in results if row.get("final_verification_status") == "usable_with_warning_source_partial")
    conflict = sum(1 for row in results if row.get("final_verification_status") == "blocked_conflict")
    write_report(
        "reports/source_refresh/first_unlock_report.md",
        "First Unlock Report",
        [
            f"- First-unlock rows processed: {len(results)}",
            f"- Ready source-verified rows: {ready}",
            f"- Usable with warning/source-partial rows: {warning}",
            f"- Blocked conflict rows: {conflict}",
            "- Acyclovir/zoster was not unlocked when cited duration conflicted with the workbook row.",
        ],
    )
    print(f"first_unlock_resolver: rows={len(results)} ready={ready} warning={warning} conflict={conflict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
