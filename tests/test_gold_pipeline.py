import importlib.util
import json
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
    assert not rx["swaps_ready"]
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
    assert all(row["product_id"] == "BDS004213" for row in rx["rx_now_ready"])
    assert all(row["disease_key"] == "allergic_rhinitis_adult" for row in rx["rx_now_ready"])
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
    bundles = list((ROOT / "exports").glob("Druglist_Gold_Source_Acquisition_Phase2_Output_*.zip"))
    assert bundles
    assert bundles[-1].stat().st_size > 0
