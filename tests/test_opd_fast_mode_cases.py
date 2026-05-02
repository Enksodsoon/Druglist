import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "test_opd_cases.py"


def load_script():
    spec = importlib.util.spec_from_file_location("test_opd_cases_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_opd_case_harness_runs_and_writes_report():
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)
    report = ROOT / "reports" / "opd_fast_mode_case_report.md"
    assert report.exists()
    text = report.read_text(encoding="utf-8")
    assert "Cases: 40" in text
    assert "Pass: True" in text


def test_harness_covers_red_flags_pediatric_and_antibiotics():
    module = load_script()
    assert any(case.red_flag for case in module.CASES)
    assert any(case.pediatric for case in module.CASES)
    assert any(case.antibiotic_allowed for case in module.CASES)


def test_opd_cases_preserve_safety_gates():
    module = load_script()
    results, failures = module.run_cases()
    assert len(results) == 40
    assert not failures
    assert any(row["red_flag_category"] for row in results)
    assert any(row["antibiotic_count"] for row in results)
