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
    assert any(row["pediatric_formula_ready"] for row in peds)
    assert all(row["final_pediatric_status"] in {"source_missing_hide_from_rx", "gold_ready_pediatric"} for row in peds)
    assert all(row["source_ids"] for row in peds if row["pediatric_formula_ready"])
    assert all(not row["antibiotic_gate_ready"] for row in antibiotics)


def test_pediatric_formula_templates_need_matching_product_labels():
    peds = load("data/gold/pediatric_dose_engine.json")["items"]
    templates = [row for row in peds if row.get("formula_template_ready")]
    ready_templates = [row for row in templates if row.get("pediatric_formula_ready")]
    blocked_templates = [row for row in templates if not row.get("pediatric_formula_ready")]
    assert templates
    assert ready_templates
    assert blocked_templates
    assert any("paracetamol" in row["generic_name"] for row in templates)
    assert any("ibuprofen" in row["generic_name"] for row in templates)
    assert all(row["source_ids"] for row in templates)
    assert all(row.get("pediatric_product_label_verified") for row in ready_templates)
    assert all("product concentration/formulation label" in row.get("pediatric_formula_block_reason", "") for row in blocked_templates)


def test_targeted_pediatric_product_labels_unlock_matching_concentrations_only():
    peds = load("data/gold/pediatric_dose_engine.json")["items"]
    ready_by_product = {row["product_id"]: row for row in peds if row.get("pediatric_formula_ready")}
    expected_ready = {"BDS003763", "BDS001665", "BDS007151", "BDS002845"}
    assert expected_ready.issubset(ready_by_product)
    assert all(
        "generic_strength_form_route_match_not_thai_brand_registered" == ready_by_product[pid]["product_match_status"]
        for pid in expected_ready
    )
    assert all("dailymed_" in ";".join(ready_by_product[pid]["source_ids"]) for pid in expected_ready)
    unmatched_paracetamol = [
        row for row in peds
        if "paracetamol" in row["generic_name"].lower()
        and row["product_id"] not in expected_ready
    ]
    assert unmatched_paracetamol
    assert all(not row.get("pediatric_formula_ready") for row in unmatched_paracetamol)


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


def test_all_drug_accredited_sweep_has_no_inventory_gaps():
    import csv

    products = load("data/gold/product_master_gold.json")["items"]
    regimens = load("data/gold/disease_regimen_gold.json")["items"]
    with (ROOT / "reports/gold/all_drug_accredited_product_sweep.csv").open(encoding="utf-8-sig") as handle:
        product_rows = list(csv.DictReader(handle))
    with (ROOT / "reports/gold/all_regimen_accredited_sweep.csv").open(encoding="utf-8-sig") as handle:
        regimen_rows = list(csv.DictReader(handle))
    assert len(product_rows) == len(products)
    assert len(regimen_rows) == len(regimens)
    assert {row["product_id"] for row in product_rows} == {row["product_id"] for row in products}
    assert all(row["gold_inventory_status"] == "in_gold_inventory" for row in product_rows)
    assert all(row["accredited_source_status"] for row in product_rows)


def test_all_drug_sweep_keeps_pending_rows_hidden():
    import csv

    rx = load("data/gold/rx_eligibility_map.json")
    ready_pairs = {(row["product_id"], row["disease_key"]) for row in rx["rx_now_ready"] + rx["swaps_ready"]}
    with (ROOT / "reports/gold/all_regimen_accredited_sweep.csv").open(encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    pending = [row for row in rows if row["accredited_source_status"] == "pending_exact_accredited_evidence"]
    assert pending
    assert all((row["product_id"], row["disease_key"]) not in ready_pairs for row in pending)


def test_all_drug_sweep_summary_reports_full_processing():
    summary = (ROOT / "reports/gold/all_drug_accredited_sweep_summary.md").read_text(encoding="utf-8")
    assert "products_processed: 910" in summary
    assert "regimen_rows_processed: 987" in summary
    assert "pediatric_rows_processed: 93" in summary
    assert "antibiotic_rows_processed: 192" in summary


def test_pediatric_gold_calculator_exact_ml_outputs():
    sys.path.insert(0, str(ROOT / "scripts/gold"))
    import pediatric_gold_calculator as calc

    para = calc.calculate("paracetamol", age_months=24, weight_kg=12, concentration_mg_per_ml=24)
    assert para["dose_mg_per_dose"] == 180
    assert para["dose_ml_per_dose"] == 7.5
    assert para["max_mg_per_day"] == 720

    ibu = calc.calculate("ibuprofen", age_months=24, weight_kg=12, concentration_mg_per_ml=20)
    assert ibu["dose_min_mg_per_dose"] == 60
    assert ibu["dose_max_mg_per_dose"] == 120
    assert ibu["dose_min_ml_per_dose"] == 3
    assert ibu["dose_max_ml_per_dose"] == 6

    ors = calc.calculate("ORS", age_months=36, weight_kg=14)
    assert ors["plan_a_after_each_loose_stool"] == "100-200 mL after each loose stool"
    assert ors["plan_b_total_ml_over_4_hours"] == 1050


def test_full_accredited_source_sweep_does_not_unlock_label_only_rows():
    products = load("data/gold/product_master_gold.json")["items"]
    regimens = load("data/gold/disease_regimen_gold.json")["items"]
    sources = load("data/gold/accredited_source_sweep_sources.json")["items"]

    assert sources
    linked_products = {source["linked_product_id"] for source in sources}
    assert any(row["product_id"] in linked_products for row in products)

    label_only_regimens = [
        row for row in regimens
        if row.get("product_id") in linked_products
        and row.get("final_rx_status") == "source_missing_hide_from_rx"
    ]
    assert label_only_regimens
    assert all(not row.get("indication_verified") for row in label_only_regimens)


def test_long_accredited_source_queue_covers_all_row_families():
    import csv

    with (ROOT / "reports/gold/long_accredited_source_acquisition_queue.csv").open(encoding="utf-8-sig") as handle:
        queue = list(csv.DictReader(handle))
    with (ROOT / "reports/gold/long_accredited_source_gap_matrix.csv").open(encoding="utf-8-sig") as handle:
        gaps = list(csv.DictReader(handle))
    assert queue
    assert gaps
    row_types = {row["row_type"] for row in queue}
    assert {"product", "regimen", "pediatric", "antibiotic"}.issubset(row_types)
    targets = {row["source_target_id"] for row in queue}
    assert {"thai_fda_smpc_pil", "thai_ndi_nlem", "thai_rdu_moph", "thai_pediatric", "thai_rdu_antibiotic"}.issubset(targets)
    assert any("line_of_treatment" in row.get("missing_fields", "") for row in gaps if row["row_type"] == "regimen")
    assert any("product concentration" in row.get("missing_fields", "") for row in gaps if row["row_type"] == "pediatric")


def test_guideline_proof_marks_no_antibiotic_and_partial_antibiotic_criteria():
    import csv

    regimens = load("data/gold/disease_regimen_gold.json")["items"]
    antibiotics = load("data/gold/antibiotic_gate_map.json")["items"]
    with (ROOT / "reports/gold/disease_guideline_proof_report.csv").open(encoding="utf-8-sig") as handle:
        proof_rows = list(csv.DictReader(handle))

    assert proof_rows
    common_cold = [row for row in regimens if row["disease_key"] == "common_cold_adult"]
    assert any("no_antibiotic_criteria" in row.get("disease_guideline_claim_types", "") for row in common_cold)

    conjunctivitis = [row for row in antibiotics if row["disease_key"] == "bacterial_conjunctivitis_adult"]
    assert conjunctivitis
    assert any(row.get("antibiotic_criteria_source_ready") for row in conjunctivitis)
    assert all(not row.get("antibiotic_gate_ready") for row in conjunctivitis)


def test_full_coverage_gap_ledger_accounts_for_all_gold_rows():
    import csv

    regimens = load("data/gold/disease_regimen_gold.json")["items"]
    peds = load("data/gold/pediatric_dose_engine.json")["items"]
    antibiotics = load("data/gold/antibiotic_gate_map.json")["items"]
    ledger = load("data/gold/gold_100_percent_coverage_gap_ledger.json")
    with (ROOT / "reports/gold/gold_100_percent_coverage_gap_ledger.csv").open(encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))

    expected = len(regimens) + len(peds) + len(antibiotics)
    assert ledger["summary"]["total_coverage_rows"] == expected
    assert len(rows) == expected
    assert ledger["summary"]["not_fully_verified_rows"] > 0
    assert all(row["next_action"] for row in rows)
