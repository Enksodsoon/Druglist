import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "antibiotic_workflow.py"


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_antibiotic_export_review_creates_csv():
    subprocess.run([sys.executable, str(SCRIPT), "export-review"], cwd=ROOT, check=True)
    target = ROOT / "reports" / "antibiotic_review_worklist.csv"
    assert target.exists()
    with target.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert {"antibiotic_rule_id", "disease_key", "generic_name", "reviewer_status", "source_ids"} <= set(rows[0])
    assert any(row["disease_key"] == "viral_uri" and row["no_antibiotic_criteria"] for row in rows)


def test_verified_antibiotic_import_requires_source_ids(tmp_path):
    reviewed = tmp_path / "antibiotic_reviewed.csv"
    columns = [
        "antibiotic_rule_id",
        "disease_key",
        "generic_name",
        "product_links",
        "bacterial_criteria",
        "no_antibiotic_criteria",
        "first_line_flag",
        "alternative_flag",
        "allergy_alternative",
        "adult_dose_rule_id",
        "peds_dose_rule_id",
        "duration",
        "red_flags",
        "referral_criteria",
        "source_ids",
        "reviewer_status",
        "reviewer_note",
    ]
    with reviewed.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerow(
            {
                "antibiotic_rule_id": "ABX_TEST",
                "disease_key": "bacterial_conjunctivitis",
                "generic_name": "chloramphenicol",
                "bacterial_criteria": "purulent discharge",
                "adult_dose_rule_id": "ADULT_TEST",
                "duration": "reviewed duration",
                "reviewer_status": "verified",
            }
        )
    result = subprocess.run([sys.executable, str(SCRIPT), "import-reviewed", str(reviewed)], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 2
    assert "requires source_ids" in result.stderr


def test_no_routine_antibiotic_conditions_have_no_rx_now_antibiotics():
    products = {product["id"]: product for product in load("data/core/drug_master_rebuilt.json")["products"]}
    forbidden = {"allergic_rhinitis", "simple_diarrhea", "dry_eye", "allergic_conjunctivitis"}
    regimens = load("data/core/fast_regimen_master.json")["regimens"]
    for regimen in regimens:
        disease_id = regimen.get("disease_id", "")
        if not any(key in disease_id for key in forbidden):
            continue
        for line in regimen.get("lines", []):
            product = products.get(line.get("product_id"), {})
            assert not (line.get("line_type") == "RX NOW" and product.get("category") == "antibiotic")


def test_bacterial_conjunctivitis_antibiotics_remain_disease_gated_and_manual_review():
    products = {product["id"]: product for product in load("data/core/drug_master_rebuilt.json")["products"]}
    regimens = [
        regimen
        for regimen in load("data/core/fast_regimen_master.json")["regimens"]
        if "bacterial_conjunctivitis" in regimen.get("disease_id", "")
    ]
    antibiotic_lines = [
        line
        for regimen in regimens
        for line in regimen.get("lines", [])
        if products.get(line.get("product_id"), {}).get("category") == "antibiotic"
    ]
    assert antibiotic_lines
    assert all(line["clinical_readiness"] == "manual_review_required" for line in antibiotic_lines)
    assert all(not line["fast_mode_allowed"] for line in antibiotic_lines)


def test_antibiotic_product_without_rule_is_not_fast_mode_allowed():
    products = {product["id"]: product for product in load("data/core/drug_master_rebuilt.json")["products"]}
    lines = [
        line
        for regimen in load("data/core/fast_regimen_master.json")["regimens"]
        for line in regimen.get("lines", [])
    ]
    antibiotic_lines = [line for line in lines if products.get(line.get("product_id"), {}).get("category") == "antibiotic"]
    assert antibiotic_lines
    assert all(not line["fast_mode_allowed"] for line in antibiotic_lines)
