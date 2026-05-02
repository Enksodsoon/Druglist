import csv
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("source_workflow", ROOT / "scripts/source_workflow.py")
source_workflow = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(source_workflow)


def run_source_workflow(*args):
    return subprocess.run(
        ["python3", "scripts/source_workflow.py", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def test_export_gaps_creates_csv():
    result = run_source_workflow("export-gaps")
    assert result.returncode == 0, result.stderr
    path = ROOT / "reports/source_gap_worklist.csv"
    assert path.exists()
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert "gap_id" in rows[0]


def test_export_template_creates_expected_columns():
    result = run_source_workflow("export-template")
    assert result.returncode == 0, result.stderr
    path = ROOT / "reports/source_registry_template.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == source_workflow.SOURCE_COLUMNS


def test_import_sources_rejects_verified_row_without_required_evidence(tmp_path):
    path = tmp_path / "bad_sources.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=source_workflow.SOURCE_COLUMNS)
        writer.writeheader()
        writer.writerow({"source_id": "BAD_SOURCE", "status": "verified", "url": "https://example.org"})
    result = run_source_workflow("import-sources", str(path))
    assert result.returncode != 0
    assert "verified source missing" in result.stderr


def test_apply_links_preserves_unresolved_gap_status():
    row = {"gap_id": "GAP_TEST", "resolution_status": "unresolved", "source_ids": ""}
    normalized = source_workflow.normalize_gap(row)
    assert normalized["resolution_status"] == "unresolved"
    assert normalized["manual_review"] is True


def test_summary_report_is_generated():
    result = run_source_workflow("summary")
    assert result.returncode == 0, result.stderr
    path = ROOT / "reports/source_workflow_summary.md"
    assert path.exists()
    assert "Source Workflow Summary" in path.read_text(encoding="utf-8")
