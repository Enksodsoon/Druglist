import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import import_guideline_patch_workbook as importer


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def patch_workbook_or_skip():
    try:
        return importer.workbook_path()
    except FileNotFoundError as exc:
        pytest.skip(str(exc))


def test_importer_is_idempotent():
    patch_workbook_or_skip()
    cmd = [sys.executable, "scripts/import_guideline_patch_workbook.py"]
    first = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=True)
    first_manifest = json.loads(first.stdout)
    second = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=True)
    second_manifest = json.loads(second.stdout)
    assert first_manifest["copy_sheet_counts"] == second_manifest["copy_sheet_counts"]
    assert first_manifest["regimen_count"] == second_manifest["regimen_count"] == 282
    imported_reviews = load("data/meta/guideline_patch_manual_review_queue.json")["items"]
    assert len(imported_reviews) == 400


def test_expected_copy_sheets_and_counts_are_imported():
    manifest = load("data/imported_guideline_patch/import_manifest.json")
    counts = manifest["copy_sheet_counts"]
    assert set(importer.IMPORT_SHEETS).issubset(counts)
    assert counts["COPY_Fast_Regimen_Master"] == 282
    assert counts["COPY_Complaint_Index"] == 750
    assert counts["COPY_Drug_Rules"] == 775
    assert counts["COPY_Drug_Master_Lookup"] == 289
    assert counts["COPY_Manual_Review"] == 400
    assert counts["COPY_Peds_Dose_Shortcuts"] == 30
    assert counts["COPY_Action_Summary"] == 436


@pytest.mark.parametrize(
    ("path", "items_key", "id_key"),
    [
        ("data/imported_guideline_patch/fast_regimen_patch.json", "items", "Regimen_ID"),
        ("data/imported_guideline_patch/complaint_index_patch.json", "items", "Map_ID"),
        ("data/imported_guideline_patch/drug_rules_patch.json", "items", "Rule_ID"),
        ("data/imported_guideline_patch/peds_dose_shortcuts_patch.json", "items", "Shortcut_ID"),
        ("data/imported_guideline_patch/drug_master_lookup_patch.json", "items", "Drug_Key"),
    ],
)
def test_normalized_outputs_have_no_duplicate_stable_ids(path, items_key, id_key):
    ids = [row[id_key] for row in load(path)[items_key]]
    assert all(ids)
    assert len(ids) == len(set(ids))


def test_not_in_workbook_and_bds_review_rows_stay_locked():
    lines = [
        line
        for regimen in load("data/core/fast_regimen_master.json")["regimens"]
        if regimen.get("import_source") == "guideline_patch_20260516"
        for line in regimen["lines"]
    ]
    not_in_workbook = [line for line in lines if line.get("bds") == "NOT_IN_WORKBOOK"]
    bds_review = [line for line in lines if line.get("bds") == "BDS_REVIEW"]
    assert not_in_workbook
    assert bds_review
    assert all(not line["fast_mode_allowed"] for line in not_in_workbook + bds_review)
    assert all(line["manual_review_required"] for line in not_in_workbook + bds_review)


def test_pediatric_and_antibiotic_rows_remain_gated():
    regimens = [
        regimen
        for regimen in load("data/core/fast_regimen_master.json")["regimens"]
        if regimen.get("import_source") == "guideline_patch_20260516"
    ]
    peds_lines = [line for regimen in regimens if regimen.get("needs_peds_calc") == "Y" for line in regimen["lines"]]
    antibiotic_lines = [
        line
        for regimen in regimens
        if str(regimen.get("antibiotic_indicated", "")).upper() in {"Y", "CONDITIONAL"}
        for line in regimen["lines"]
    ]
    assert peds_lines
    assert antibiotic_lines
    assert all(not line["fast_mode_allowed"] for line in peds_lines)
    assert all(not line["fast_mode_allowed"] for line in antibiotic_lines)


def test_non_drug_actions_are_not_medication_orders():
    lines = [
        line
        for regimen in load("data/core/fast_regimen_master.json")["regimens"]
        if regimen.get("import_source") == "guideline_patch_20260516"
        for line in regimen["lines"]
    ]
    non_drug = [line for line in lines if line.get("non_drug_action")]
    assert non_drug
    assert all(not line.get("product_id") for line in non_drug if line.get("bds") in {"", "NOT_IN_WORKBOOK", "NO_BDS", "BDS_REVIEW"})
    assert all(line["line_type"] in {"RX_NOW", "SWAP"} for line in non_drug)
    assert all(not line["fast_mode_allowed"] for line in non_drug)


def test_representative_disease_keys_exist_after_import():
    imported_diseases = {row["Disease_Key"] for row in load("data/imported_guideline_patch/fast_regimen_patch.json")["items"]}
    present = [key for key in importer.REQUIRED_DISEASE_KEYS if key in imported_diseases or any(key in disease for disease in imported_diseases)]
    assert present
    coverage = (ROOT / "reports/guideline_patch_runtime_coverage.md").read_text(encoding="utf-8")
    assert "Representative Disease Keys Not Found Exactly" in coverage


def test_runtime_excludes_imported_protocols_without_druglist_medication_lines():
    regimens = [
        regimen
        for regimen in load("data/core/fast_regimen_master.json")["regimens"]
        if regimen.get("import_source") == "guideline_patch_20260516"
    ]
    assert regimens
    assert all(any(line.get("product_id") and not line.get("non_drug_action") for line in regimen.get("lines", [])) for regimen in regimens)
    pruned = load("data/imported_guideline_patch/runtime_pruned_protocols.json")
    assert pruned["meta"]["pruned_regimen_count"] > 0


def test_frontend_seed_exposes_imported_complaints_and_non_drug_status():
    seed = load("data/core/app_seed_runtime.json")
    imported = [row for row in seed["cp"] if row.get("src") == "guideline_patch_20260516"]
    assert imported
    lines = [line for complaint in imported for regimen in complaint.get("r", []) for line in regimen.get("m", [])]
    assert lines
    assert any(line.get("non_drug_action") and line.get("t") == "NON DRUG ACTION" for line in lines)
    assert all(not line["fast_mode_allowed"] for line in lines if line.get("clinical_readiness") == "manual_review_required")
