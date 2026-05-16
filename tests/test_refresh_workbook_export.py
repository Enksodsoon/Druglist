import csv
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "exports" / "Druglist_Data_Refresh_Master.xlsx"
CSV_DIR = ROOT / "exports" / "refresh_csv"

REQUIRED_TABS = [
    "1_Product_Master_Export",
    "2_Regimen_Master_Export",
    "3_Complaint_Disease_Map",
    "4_Top_50_Defaults",
    "5_Clinic_Defaults",
    "6_Pediatric_Dosing",
    "7_Antibiotic_Rows",
    "8_Source_Evidence_Queue",
    "9_Clinical_QC",
    "10_Import_Diff_Template",
    "11_OPD_Fast_Index_Template",
    "12_Drug_Short_Lookup_Template",
]


def runtime():
    return json.loads((ROOT / "data/core/app_seed_runtime.json").read_text(encoding="utf-8"))


def csv_rows(name):
    with (CSV_DIR / f"{name}.csv").open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_refresh_workbook_is_created_with_required_tabs():
    assert WORKBOOK.exists()
    assert WORKBOOK.stat().st_size > 100_000
    with zipfile.ZipFile(WORKBOOK) as zf:
        workbook_xml = zf.read("xl/workbook.xml").decode("utf-8")
    names = re.findall(r'<sheet name="([^"]+)"', workbook_xml)
    assert names == REQUIRED_TABS


def test_csv_copies_are_created_for_all_tabs():
    for tab in REQUIRED_TABS:
        path = CSV_DIR / f"{tab}.csv"
        assert path.exists(), tab
        assert path.stat().st_size > 0, tab


def test_product_ids_are_preserved_and_no_product_row_dropped():
    source_ids = {row["i"] for row in runtime().get("dr", [])}
    exported = csv_rows("1_Product_Master_Export")
    exported_ids = {row["product_id"] for row in exported}
    assert len(exported) == len(source_ids) == 910
    assert source_ids <= exported_ids


def test_regimen_ids_are_preserved_and_no_regimen_row_dropped():
    data = runtime()
    source_rows = [
        line
        for complaint in data.get("cp", [])
        for regimen in complaint.get("r", [])
        for line in regimen.get("m", [])
    ]
    source_regimen_ids = {
        regimen.get("i")
        for complaint in data.get("cp", [])
        for regimen in complaint.get("r", [])
        if regimen.get("i") and regimen.get("m")
    }
    exported = csv_rows("2_Regimen_Master_Export")
    exported_regimen_ids = {row["regimen_id"] for row in exported}
    assert len(exported) == len(source_rows)
    assert len(source_rows) >= 987
    assert source_regimen_ids <= exported_regimen_ids


def test_export_reports_are_created():
    for path in [
        ROOT / "reports" / "export_refresh_workbook_report.md",
        ROOT / "reports" / "export_data_gap_report.md",
    ]:
        assert path.exists()
        text = path.read_text(encoding="utf-8")
        assert "Total products" in text or "Counts" in text
