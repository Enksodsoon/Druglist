import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_workbook_qa_detects_product_quality_issues():
    payload = load("data/meta/workbook_quality_issues.json")
    assert payload["issues"]
    assert payload["meta"]["issue_count"] == len(payload["issues"])


def test_workbook_qa_detects_missing_concentration_or_metadata():
    issues = load("data/meta/workbook_quality_issues.json")["issues"]
    text = " ".join(" ".join(issue["issues"]) for issue in issues)
    assert "missing concentration" in text or "missing generic" in text or "missing route/form" in text
