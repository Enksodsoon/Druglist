import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def regimen(regimen_id):
    return next(r for r in load("data/core/fast_regimen_master.json")["regimens"] if r["regimen_id"] == regimen_id)


def test_shingles_zoster_row_cannot_be_ready_without_source_backed_dose_frequency_duration():
    row = regimen("FRM0027")
    assert row["clinical_readiness"] == "blocked"
    assert row["correction_status"] == "blocked_by_overlay"
    for line in row["lines"]:
        assert line["fast_mode_allowed"] is False
        assert line["clinical_readiness"] == "blocked"
        assert "source" in " ".join(line["missing_requirements"]).lower()


def test_herpes_labialis_and_zoster_are_separate_disease_keys():
    assert regimen("FRM0026")["disease_id"] == "herpes_labialis_adult"
    assert regimen("FRM0027")["disease_id"] == "herpes_zoster_adult"


def test_topical_antiviral_cannot_satisfy_oral_zoster_regimen():
    issues = load("data/meta/antiviral_regimen_quality_issues.json")["issues"]
    assert any(issue["issue_type"] == "unsupported_antiviral_regimen" for issue in issues)
    zoster = regimen("FRM0027")
    assert all("cream" not in line["display_name"].lower() for line in zoster["lines"] if "acyclovir" in line["display_name"].lower())


def test_acyclovir_400_product_does_not_auto_verify_zoster_by_availability_alone():
    products = load("data/core/drug_master_rebuilt.json")["products"]
    assert any("Acyclovir 400" in product["display_name"] for product in products)
    zoster = regimen("FRM0027")
    assert zoster["clinical_readiness"] == "blocked"
    assert not any(line["fast_mode_allowed"] for line in zoster["lines"] if "Acyclovir" in line["display_name"])


def test_unsupported_antiviral_regimen_appears_in_audit_report():
    report = (ROOT / "reports" / "antiviral_regimen_audit_report.md").read_text(encoding="utf-8")
    assert "Antiviral Regimen Audit Report" in report
    assert "unsupported_antiviral_regimen" in report
