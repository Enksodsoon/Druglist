import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def csv_rows(path):
    with (ROOT / path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_source_acquisition_priority_has_high_risk_needs():
    needs = load_json("data/source_refresh/source_acquisition_priority.json")["source_needs"]
    packs = {need["source_pack_id"] for need in needs}
    assert "acyclovir_herpes_zoster_adult" in packs
    assert "viral_uri_no_antibiotic" in packs
    assert all(need["exact_missing_evidence_fields"] for need in needs)


def test_source_candidates_are_text_checked_before_claims():
    candidates = load_json("data/source_refresh/source_acquisition_candidates.json")["candidates"]
    assert candidates
    assert any(candidate["candidate_status"] == "text_check_ready" for candidate in candidates)
    for candidate in candidates:
        assert candidate["candidate_status"] != "accepted"
        assert candidate["source_title"]
        assert candidate["organization"]


def test_exact_claims_are_snippet_backed_and_row_mapped():
    claims = load_json("data/source_refresh/exact_evidence_claims.json")["claims"]
    assert claims
    for claim in claims:
        assert claim["source_id"]
        assert claim["short_snippet"]
        assert claim["rows_matched"]
        if claim["claim_type"] == "adult_dose":
            dose = claim["dose_struct"]
            assert dose["dose_value"]
            assert dose["dose_unit"]
            assert dose["frequency"]


def test_zoster_conflict_stays_blocked_not_ready():
    results = load_json("data/source_refresh/first_unlock_results.json")["results"]
    zoster = [row for row in results if row["target"] == "acyclovir_zoster"]
    assert zoster
    assert all(row["final_verification_status"] != "ready_source_verified" for row in zoster)
    assert any(row["final_verification_status"] == "blocked_conflict" for row in zoster)
    assert all(row["can_show_in_main_builder"] == "true" for row in zoster)


def test_refreshed_rows_have_no_duplicate_headers_and_ready_has_citation():
    path = ROOT / "exports/source_refresh_csv/2_Regimen_Master_Export.csv"
    headers = path.read_text(encoding="utf-8-sig").splitlines()[0].split(",")
    assert len(headers) == len(set(headers))
    rows = csv_rows("exports/source_refresh_csv/2_Regimen_Master_Export.csv")
    ready = [row for row in rows if row.get("final_verification_status") == "ready_source_verified"]
    for row in ready:
        assert row["source_ids"]
        assert row["evidence_claim_ids"]
        assert row["source_snippets_short"]


def test_quality_gate_reports_real_progress_or_clear_block():
    report = (ROOT / "reports/source_refresh/source_coverage_quality_gate.md").read_text(encoding="utf-8")
    assert "Gate status:" in report
    assert "Exact acquisition claims after PR25:" in report
    assert "Acyclovir/zoster remains blocked" in report
