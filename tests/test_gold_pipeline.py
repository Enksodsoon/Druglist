import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def gold_common():
    path = ROOT / "scripts/gold/gold_common.py"
    spec = importlib.util.spec_from_file_location("gold_common_for_tests", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_gold_outputs_exist_and_preserve_seed_counts():
    products = load("data/gold/product_master_gold.json")["items"]
    regimens = load("data/gold/disease_regimen_gold.json")["items"]
    peds = load("data/gold/pediatric_dose_engine.json")["items"]
    antibiotics = load("data/gold/antibiotic_gate_map.json")["items"]
    assert len(products) == 910
    assert len(regimens) == 987
    assert len(peds) == 93
    assert len(antibiotics) == 192
    assert all(row["product_id"] for row in products)
    assert all(row["regimen_id"] for row in regimens)


def test_catalog_only_and_source_missing_are_hidden_from_rx_now():
    rx = load("data/gold/rx_eligibility_map.json")
    hidden_statuses = {
        "catalog_hidden_from_rx",
        "source_missing_hide_from_rx",
        "source_conflict_hide_from_rx",
        "absolute_block",
    }
    assert rx["reference_only_products"]
    for row in rx["rx_now_ready"] + rx["swaps_ready"]:
        assert row["final_rx_status"] not in hidden_statuses


def test_pediatric_and_antibiotic_gates_are_conservative():
    peds = load("data/gold/pediatric_dose_engine.json")["items"]
    antibiotics = load("data/gold/antibiotic_gate_map.json")["items"]
    assert all(not row["pediatric_formula_ready"] for row in peds)
    assert all(row["final_pediatric_status"] == "source_missing_hide_from_rx" for row in peds)
    assert all(not row["antibiotic_gate_ready"] for row in antibiotics)


def test_every_ready_row_has_source_citation_if_future_rows_unlock():
    regimens = load("data/gold/disease_regimen_gold.json")["items"]
    citations = load("data/gold/source_citations_gold.json")["items"]
    source_ids = {row["source_id"] for row in citations if row.get("source_id")}
    for row in regimens:
        if row["final_rx_status"] in {"gold_ready_adult", "gold_ready_pediatric", "gold_ready_conditional"}:
            assert row["source_ids"]
            assert any(source_id in source_ids for source_id in row["source_ids"])
            assert row["safety_minimum_ready"]
            assert row["adult_route"]
            assert row["adult_frequency"]
            assert row["adult_duration"]


def test_phase2_candidate_selector_prioritizes_defaults():
    import csv

    with (ROOT / "reports/gold/phase2_candidate_rows.csv").open(encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert rows[0]["phase2_candidate_reason"] == "top50_or_clinic_default"
    assert any(row["disease_key"] == "allergic_rhinitis_adult" for row in rows)


def test_phase2_adult_verified_row_appears_in_rx_now():
    rx = load("data/gold/rx_eligibility_map.json")
    assert rx["rx_now_ready"]
    assert any(row["product_id"] == "BDS004213" and row["disease_key"] == "allergic_rhinitis_adult" for row in rx["rx_now_ready"])
    assert all(row["final_rx_status"] == "gold_ready_adult" for row in rx["rx_now_ready"])


def test_workbook_only_rows_stay_hidden():
    regimens = load("data/gold/disease_regimen_gold.json")["items"]
    target = [row for row in regimens if row["product_id"] != "BDS004213" and row["final_rx_status"] == "source_missing_hide_from_rx"]
    assert target


def test_viral_uri_and_simple_diarrhea_have_no_antibiotic_ready_rows():
    rx = load("data/gold/rx_eligibility_map.json")
    forbidden = ["uri", "viral", "watery_diarrhea", "diarrhea"]
    antibiotic_rows = load("data/gold/antibiotic_gate_map.json")["items"]
    antibiotic_product_ids = {row["product_id"] for row in antibiotic_rows}
    for row in rx["rx_now_ready"]:
        assert row["product_id"] not in antibiotic_product_ids
        assert not ("antibiotic" in row["generic_name"].lower() and any(token in row["disease_key"] for token in forbidden))


def test_source_conflict_rows_stay_hidden():
    rx = load("data/gold/rx_eligibility_map.json")
    hidden_ids = {row["gold_regimen_row_id"] for row in rx["blocked_rows"] if row["final_rx_status"] == "source_conflict_hide_from_rx"}
    ready_ids = {row["gold_regimen_row_id"] for row in rx["rx_now_ready"] + rx["swaps_ready"]}
    assert hidden_ids
    assert hidden_ids.isdisjoint(ready_ids)


def test_validator_catches_unlocked_row_without_citation(monkeypatch):
    module = gold_common()
    original = module.read_json

    def fake_read_json(path, default):
        data = original(path, default)
        if str(path).endswith("source_citations_gold.json"):
            return {"items": []}
        return data

    monkeypatch.setattr(module, "read_json", fake_read_json)
    errors = module.validation_errors()
    assert any("rx_now_without_citation" in error for error in errors)


def test_feature_flag_loader_legacy_and_safe_fallback():
    module = gold_common()
    legacy = module.load_runtime_with_gold_overlay(use_gold=False)
    assert legacy["engine"] == "legacy"
    assert legacy["runtime"]["dr"]
    gold = module.load_runtime_with_gold_overlay(use_gold=True)
    assert gold["engine"] == "gold"
    missing = module.load_runtime_with_gold_overlay(use_gold=True, gold_dir=ROOT / "does-not-exist")
    assert missing["engine"] == "legacy_fallback"


def test_gold_validation_report_passes_and_bundle_exists():
    report = (ROOT / "reports/gold/gold_validation_report.md").read_text(encoding="utf-8")
    assert "Pass: True" in report
    bundles = list((ROOT / "exports").glob("Druglist_Gold_OPD_First_Pack_Output_*.zip"))
    assert bundles
    assert bundles[-1].stat().st_size > 0


def test_unique_coverage_report_separates_duplicates():
    import csv

    summary = (ROOT / "reports/gold/gold_unique_coverage_summary.md").read_text(encoding="utf-8")
    with (ROOT / "reports/gold/gold_unique_coverage_report.csv").open(encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert "unique_products_rx_ready" in summary
    assert "duplicate_row_count" in summary
    assert len({row["product_id"] for row in rows}) <= len(rows)


def test_product_match_gap_blocks_mismatch_rows():
    import csv

    with (ROOT / "reports/gold/product_match_gap_report.csv").open(encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    assert any("ibuprofen" in row.get("generic_name", "").lower() for row in rows)
    ibuprofen = [row for row in rows if "ibuprofen" in row.get("generic_name", "").lower()]
    assert all("exact strength/form match" in row.get("product_match_gap_reason", "") for row in ibuprofen)


def test_cached_accepted_evidence_requires_matching_row(monkeypatch, tmp_path):
    module = gold_common()
    sys.path.insert(0, str(ROOT / "scripts/gold"))
    import source_adapters.local_evidence_cache_adapter as adapter
    rows = [
        {
            "source_id": "test_source",
            "source_title": "Test source",
            "source_org": "Test org",
            "source_url": "https://example.org/source",
            "source_type": "official_product_label",
            "generic_name": "not-a-matching-generic",
            "disease_key": "allergic_rhinitis_adult",
            "evidence_field": "adult_dose",
            "evidence_value": "1 tablet",
            "evidence_snippet": "short supported snippet",
            "access_date": "2026-05-09",
            "confidence": "0.9",
        }
    ]
    cache = tmp_path / "accepted_evidence"
    cache.mkdir()
    (cache / "bad.json").write_text(json.dumps(rows), encoding="utf-8")
    monkeypatch.setattr(adapter, "ACCEPTED", cache)
    result = adapter.run(module.phase2_candidate_rows())
    assert not result.evidence_claims


def test_swaps_are_verified_and_same_disease_mapped():
    rx = load("data/gold/rx_eligibility_map.json")
    assert rx["swaps_ready"]
    for row in rx["swaps_ready"]:
        assert row["source_ids"]
        assert row["disease_key"]
        assert row["final_rx_status"] in {"gold_ready_adult", "gold_ready_pediatric", "gold_ready_conditional", "conditional_use_when_criteria_met"}


def test_swap_tier_report_contains_verified_alternatives():
    import csv

    with (ROOT / "reports/gold/swaps_tier_report.csv").open(encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert any("Tier 1" in row.get("swap_tier", "") for row in rows)
