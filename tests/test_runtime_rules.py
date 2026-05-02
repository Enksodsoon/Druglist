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
