import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_peds_source_priority_file_generated():
    payload = load("data/pediatric/pediatric_source_gap_priority.json")
    assert payload["items"]
    assert payload["meta"]["item_count"] == 93
    assert payload["meta"]["tier1_count"] > 0


def test_peds_calculated_dose_blocked_without_source():
    rows = load("data/pediatric/pediatric_source_gap_priority.json")["items"]
    assert any("pediatric source" in row["missing_requirements"] for row in rows)
    assert all(row["can_calculate_dose"] is False for row in rows)


def test_peds_calculated_dose_blocked_without_concentration_and_age_bw():
    rows = load("data/pediatric/pediatric_source_gap_priority.json")["items"]
    assert any("age/BW rule" in row["missing_requirements"] for row in rows)
    script = (ROOT / "scripts" / "pediatric_source_gap_audit.py").read_text(encoding="utf-8")
    assert '"concentration"' in script
    assert all(row["can_calculate_dose"] is False for row in rows)


def test_peds_page_static_contract_still_renders_products_and_gaps():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert 'id="section-peds"' in html
    assert 'id="pedsLibrary"' in html
    seed = load("data/core/app_seed_runtime.json")
    assert seed["m"]["pediatric_source_gap_count"] == 93


def test_peds_templates_are_generated_without_auto_dose_unlock():
    seed = load("data/core/app_seed_runtime.json")
    templates = seed["pd"]
    assert templates
    assert seed["m"]["pedsCount"] == len(templates)
    assert sum(len(template.get("r", [])) for template in templates) > 0
    peds_outputs = load("data/pediatric/peds_product_dose_output.json")["items"]
    assert all(item["auto_dose_enabled"] is False for item in peds_outputs)
