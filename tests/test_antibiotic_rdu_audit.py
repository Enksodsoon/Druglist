import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_antibiotic_audit_outputs_source_gaps_and_issues():
    issues = load("data/meta/antibiotic_rdu_quality_issues.json")["issues"]
    gaps = load("data/guidelines/antibiotic_source_gap_priority.json")["items"]
    assert issues
    assert gaps


def test_viral_uri_and_simple_diarrhea_have_no_fast_allowed_antibiotic_rx_now():
    regimens = load("data/core/fast_regimen_master.json")["regimens"]
    for regimen in regimens:
        disease = regimen["disease_id"].lower()
        if any(key in disease for key in ["viral", "uri", "simple_diarrhea", "diarrhea_adult", "diarrhea_child"]):
            for line in regimen["lines"]:
                text = (line.get("display_name", "") + " " + line.get("line_type", "")).lower()
                if any(term in text for term in ["amoxicillin", "clavulan", "azithromycin", "ofloxacin", "chloramphenicol"]):
                    assert line["fast_mode_allowed"] is False


def test_bacterial_conjunctivitis_antibiotic_remains_source_gated():
    issues = load("data/meta/antibiotic_rdu_quality_issues.json")["issues"]
    assert any("bacterial_conjunctivitis" in issue["disease_key"] for issue in issues)


def test_antibiotic_product_without_rule_is_not_ready():
    issues = load("data/meta/antibiotic_rdu_quality_issues.json")["issues"]
    assert any(issue["recommended_action"] == "require_antibiotic_criteria" for issue in issues)
