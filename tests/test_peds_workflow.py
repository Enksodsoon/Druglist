import csv
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("peds_workflow", ROOT / "scripts/peds_workflow.py")
peds_workflow = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(peds_workflow)


def run_peds_workflow(*args):
    return subprocess.run(
        ["python3", "scripts/peds_workflow.py", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def test_peds_review_csv_export_exists():
    result = run_peds_workflow("export-review")
    assert result.returncode == 0, result.stderr
    path = ROOT / "reports/peds_dose_review_worklist.csv"
    assert path.exists()
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    assert reader.fieldnames == peds_workflow.PEDS_COLUMNS
    assert rows


def test_verified_pediatric_rows_require_source_ids():
    row = {
        "peds_dose_rule_id": "PEDS_TEST",
        "generic_name": "test",
        "disease_key": "test",
        "indication_text": "test",
        "dose_basis": "fixed_dose",
        "fixed_dose": "1",
        "frequency": "test",
        "duration": "test",
        "route": "oral",
        "reviewer_status": "verified",
        "source_ids": "",
    }
    assert "requires source_ids" in peds_workflow.validate_row(row, 2)


def test_auto_calculable_reviewed_rows_require_verified_status_and_sources():
    row = {
        "peds_dose_rule_id": "PEDS_TEST",
        "generic_name": "test",
        "disease_key": "test",
        "indication_text": "test",
        "dose_basis": "mg_per_kg_per_dose",
        "dose_mg_per_kg_per_dose": "10",
        "frequency": "test",
        "duration": "test",
        "route": "oral",
        "reviewer_status": "pending_source",
        "source_ids": "",
    }
    normalized = peds_workflow.normalize(row)
    assert normalized["auto_calculable"] is False
    assert normalized["fast_mode_allowed"] is False


def test_label_reference_only_is_not_fast_mode_allowed():
    normalized = peds_workflow.normalize(
        {
            "peds_dose_rule_id": "PEDS_LABEL_ONLY",
            "reviewer_status": "label_reference_only",
            "source_ids": "LABEL_SOURCE",
        }
    )
    assert normalized["fast_mode_allowed"] is False
    assert normalized["manual_review"] is True
