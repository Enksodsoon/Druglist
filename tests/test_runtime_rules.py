import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_runtime_links_complaints_to_diseases():
    diseases = {d["disease_id"] for d in load("data/core/disease_master.json")["diseases"]}
    complaints = load("data/core/complaint_index.json")["items"]
    assert complaints
    assert all(c["disease_id"] in diseases for c in complaints)


def test_antibiotic_and_peds_gates_exist():
    antibiotic_rules = load("data/safety/antibiotic_stewardship.json")["rules"]
    peds_gates = load("data/pediatric/peds_age_gate_library.json")["gates"]
    assert any("indication" in r["message"].lower() for r in antibiotic_rules)
    assert peds_gates
    assert all(not gate["active"] and gate["manual_review"] for gate in peds_gates)


def test_no_pediatric_auto_dose_without_sources():
    peds_outputs = load("data/pediatric/peds_product_dose_output.json")["items"]
    assert all(not item["auto_dose_enabled"] for item in peds_outputs)
    assert all(item["dose_output_status"] == "manual_review" for item in peds_outputs)


def test_all_opd_rows_have_source_gated_readiness_fields():
    lines = [
        line
        for regimen in load("data/core/fast_regimen_master.json")["regimens"]
        for line in regimen["lines"]
    ]
    assert lines
    for line in lines:
        assert line["source_status"] in {
            "source_verified",
            "source_gap",
            "pending_manual_review",
            "local_rule_only",
            "not_applicable",
        }
        assert line["clinical_readiness"] in {
            "ready",
            "usable_with_warning",
            "manual_review_required",
            "blocked",
        }
        assert isinstance(line["missing_requirements"], list)
        assert isinstance(line["fast_mode_allowed"], bool)


def test_no_runtime_row_is_source_verified_without_source_ids():
    lines = [
        line
        for regimen in load("data/core/fast_regimen_master.json")["regimens"]
        for line in regimen["lines"]
    ]
    assert all(line["source_status"] != "source_verified" or line.get("source_ids") for line in lines)


def test_antibiotic_rows_are_not_fast_mode_allowed_without_verified_gate():
    products = {p["id"]: p for p in load("data/core/drug_master_rebuilt.json")["products"]}
    lines = [
        line
        for regimen in load("data/core/fast_regimen_master.json")["regimens"]
        for line in regimen["lines"]
    ]
    antibiotic_lines = [line for line in lines if products.get(line["product_id"], {}).get("category") == "antibiotic"]
    assert antibiotic_lines
    assert all(not line["fast_mode_allowed"] for line in antibiotic_lines)


def test_app_seed_medication_rows_include_readiness_badges_data():
    meds = [
        med
        for complaint in load("data/core/app_seed_runtime.json")["cp"]
        for regimen in complaint.get("r", [])
        for med in regimen.get("m", [])
    ]
    assert meds
    assert all("clinical_readiness" in med and "fast_mode_allowed" in med for med in meds)
