#!/usr/bin/env python3
"""Export current Druglist runtime data to an external medical refresh workbook.

The exporter is intentionally data-only: it preserves IDs and current values but
does not correct, infer, or verify clinical content.
"""

from __future__ import annotations

import csv
import json
import re
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = ROOT / "exports"
CSV_DIR = EXPORT_DIR / "refresh_csv"
WORKBOOK = EXPORT_DIR / "Druglist_Data_Refresh_Master.xlsx"
REPORT = ROOT / "reports/export_refresh_workbook_report.md"
GAP_REPORT = ROOT / "reports/export_data_gap_report.md"

SHEETS = [
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

PRODUCT_COLUMNS = [
    "product_id",
    "brand_name",
    "generic_name",
    "composition",
    "strength",
    "dosage_form",
    "route",
    "pack",
    "price",
    "BDS",
    "indication_text",
    "caution",
    "side_effect",
    "contraindication",
    "pregnancy_lactation",
    "pediatric_flag",
    "antibiotic_flag",
    "source_status",
    "clinical_readiness",
    "manual_review_required",
    "blocked_reason",
    "old_runtime_status",
    "source_runtime_path",
]

REGIMEN_COLUMNS = [
    "regimen_id",
    "disease_key",
    "disease_name",
    "ICD10",
    "complaint_key",
    "role",
    "tier",
    "default_row",
    "product_id",
    "drug_name",
    "composition",
    "BDS",
    "sig",
    "duration",
    "dispense",
    "caution",
    "side_effect",
    "clinical_readiness",
    "fast_mode_allowed",
    "evidence_status",
    "source_status",
    "blocked_reason",
    "missing_requirements",
    "next_action",
    "old_runtime_status",
    "source_runtime_path",
]


def load_json(path: str, default: Any) -> Any:
    target = ROOT / path
    if not target.exists():
        return default
    return json.loads(target.read_text(encoding="utf-8"))


def scalar(value: Any) -> str | int | float | bool | None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return "; ".join(str(scalar(item) or "") for item in value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def first_present(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and row.get(key) not in (None, "", []):
            return row.get(key)
    return ""


def product_rows(runtime: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for idx, item in enumerate(runtime.get("dr") or []):
        fa = item.get("fa") or {}
        product_id = item.get("i") or fa.get("medicine_code") or fa.get("product_code") or ""
        rows.append(
            {
                "product_id": product_id,
                "brand_name": item.get("n") or fa.get("product_name") or fa.get("medicine_name") or "",
                "generic_name": item.get("g") or "",
                "composition": item.get("c") or fa.get("composition") or "",
                "strength": first_present(item, "strength", "dose_strength"),
                "dosage_form": item.get("f") or "",
                "route": first_present(item, "route", "r"),
                "pack": item.get("p") or fa.get("pack_size") or "",
                "price": item.get("pr") if item.get("pr") is not None else "",
                "BDS": product_id,
                "indication_text": first_present(item, "indication_text", "indication"),
                "caution": first_present(item, "caution", "warnings"),
                "side_effect": first_present(item, "side_effect", "adverse_effects"),
                "contraindication": first_present(item, "contraindication", "contraindications"),
                "pregnancy_lactation": first_present(item, "pregnancy_lactation", "pregnancy", "lactation"),
                "pediatric_flag": bool(item.get("tl") and (item.get("tl") or {}).get("s") != "no_pediatric_target_found"),
                "antibiotic_flag": item.get("cc") == "antibiotic" or fa.get("category") == "antibiotic",
                "source_status": item.get("source_status") or fa.get("source_status") or "",
                "clinical_readiness": first_present(item, "clinical_readiness"),
                "manual_review_required": item.get("manual_review_required", ""),
                "blocked_reason": first_present(item, "blocked_reason", "manual_review_reasons"),
                "old_runtime_status": item.get("auto_resolution_status") or item.get("evidence_status") or "",
                "source_runtime_path": f"data/core/app_seed_runtime.json:dr[{idx}]",
            }
        )
    return rows


def flatten_regimens(runtime: dict[str, Any], product_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for c_idx, complaint in enumerate(runtime.get("cp") or []):
        for r_idx, regimen in enumerate(complaint.get("r") or []):
            for m_idx, line in enumerate(regimen.get("m") or []):
                product = product_by_id.get(line.get("i") or "", {})
                rows.append(
                    {
                        "regimen_id": regimen.get("i") or "",
                        "disease_key": complaint.get("d") or "",
                        "disease_name": regimen.get("d") or complaint.get("c") or "",
                        "ICD10": first_present(complaint, "icd10", "ICD10"),
                        "complaint_key": complaint.get("i") or "",
                        "role": line.get("t") or line.get("s") or "",
                        "tier": line.get("s") or "",
                        "default_row": bool(regimen.get("y")),
                        "product_id": line.get("i") or "",
                        "drug_name": line.get("n") or product.get("n") or "",
                        "composition": product.get("c") or "",
                        "BDS": line.get("i") or "",
                        "sig": line.get("o") or "",
                        "duration": line.get("u") or "",
                        "dispense": line.get("p") or "",
                        "caution": first_present(line, "caution", "warnings", "warning"),
                        "side_effect": first_present(line, "side_effect", "adverse_effects"),
                        "clinical_readiness": line.get("clinical_readiness") or "",
                        "fast_mode_allowed": line.get("fast_mode_allowed", ""),
                        "evidence_status": line.get("evidence_status") or "",
                        "source_status": line.get("source_status") or "",
                        "blocked_reason": line.get("blocked_reason") or "",
                        "missing_requirements": scalar(line.get("missing_requirements") or []),
                        "next_action": line.get("next_action") or "",
                        "old_runtime_status": line.get("auto_resolution_status") or "",
                        "source_runtime_path": f"data/core/app_seed_runtime.json:cp[{c_idx}].r[{r_idx}].m[{m_idx}]",
                    }
                )
    return rows


def complaint_rows(runtime: dict[str, Any], complaint_index: dict[str, Any], diseases: dict[str, Any]) -> list[dict[str, Any]]:
    index_by_disease = defaultdict(list)
    for item in complaint_index.get("items") or []:
        index_by_disease[item.get("disease_id")].append(item)
    disease_by_id = {d.get("disease_id"): d for d in diseases.get("diseases") or []}
    rows = []
    for idx, complaint in enumerate(runtime.get("cp") or []):
        disease_key = complaint.get("d") or ""
        disease = disease_by_id.get(disease_key, {})
        rows.append(
            {
                "complaint_key": complaint.get("i") or "",
                "complaint_text": complaint.get("c") or "",
                "disease_key": disease_key,
                "disease_name": disease.get("display_name") or disease_key,
                "category": complaint.get("g") or disease.get("category") or "",
                "age_group": complaint.get("a") or "",
                "match_type": complaint.get("mt") or "",
                "priority": complaint.get("p") or "",
                "regimen_ids": scalar([r.get("i") for r in complaint.get("r") or []]),
                "source_status": disease.get("source_status") or "",
                "manual_review": disease.get("manual_review", ""),
                "source_runtime_path": f"data/core/app_seed_runtime.json:cp[{idx}]",
                "complaint_index_matches": scalar([x.get("complaint_id") for x in index_by_disease.get(disease_key, [])]),
            }
        )
    return rows


def top_defaults(regimen_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in regimen_rows
        if row.get("default_row")
    ][:50]


def clinic_defaults(fast_master: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for r_idx, regimen in enumerate(fast_master.get("regimens") or []):
        for l_idx, line in enumerate(regimen.get("lines") or []):
            rows.append(
                {
                    "regimen_id": regimen.get("regimen_id") or "",
                    "disease_key": regimen.get("disease_id") or "",
                    "disease_name": regimen.get("display_name") or "",
                    "workflow_label": regimen.get("workflow_label") or "",
                    "default_row": regimen.get("is_default", ""),
                    "product_id": line.get("product_id") or "",
                    "line_id": line.get("line_id") or "",
                    "role": line.get("line_type") or "",
                    "drug_name": line.get("display_name") or "",
                    "sig": line.get("order_text") or "",
                    "duration": line.get("duration_label") or "",
                    "dispense": line.get("pack_label") or "",
                    "clinical_readiness": line.get("clinical_readiness") or "",
                    "fast_mode_allowed": line.get("fast_mode_allowed", ""),
                    "source_status": line.get("source_status") or "",
                    "next_action": line.get("next_action") or "",
                    "source_runtime_path": f"data/core/fast_regimen_master.json:regimens[{r_idx}].lines[{l_idx}]",
                }
            )
    return rows


def pediatric_rows(peds: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for idx, item in enumerate(peds.get("items") or []):
        row = {k: scalar(v) for k, v in item.items()}
        row["source_runtime_path"] = f"data/pediatric/peds_product_dose_output.json:items[{idx}]"
        rows.append(row)
    return rows


def antibiotic_rows(products: list[dict[str, Any]], regimen_rows: list[dict[str, Any]], antibiotic_issues: dict[str, Any]) -> list[dict[str, Any]]:
    antibiotic_ids = {
        p.get("product_id") or p.get("i")
        for p in products
        if p.get("antibiotic_flag") is True or p.get("cc") == "antibiotic"
    }
    rows = [dict(row, row_source="regimen") for row in regimen_rows if row.get("product_id") in antibiotic_ids or "antibiotic" in str(row).lower()]
    for idx, issue in enumerate(antibiotic_issues.get("issues") or []):
        rows.append(
            {
                "row_source": "antibiotic_audit_issue",
                "issue_id": issue.get("issue_id") or "",
                "severity": issue.get("severity") or "",
                "disease_key": issue.get("disease_key") or "",
                "regimen_id": issue.get("regimen_id") or "",
                "product_id": issue.get("product_id") or "",
                "drug_name": issue.get("display_name") or issue.get("generic_name") or "",
                "issue_type": issue.get("issue_type") or "",
                "recommended_action": issue.get("recommended_action") or "",
                "source_runtime_path": f"data/meta/antibiotic_rdu_quality_issues.json:issues[{idx}]",
            }
        )
    return rows


def source_queue_rows() -> list[dict[str, Any]]:
    sources = [
        ("source_gap", "data/guidelines/source_gap_list.json", load_json("data/guidelines/source_gap_list.json", {}).get("items") or []),
        ("source_todo", "data/evidence/source_manifest.todo.json", load_json("data/evidence/source_manifest.todo.json", {}).get("items") or []),
        ("source_manifest", "data/evidence/source_manifest.json", load_json("data/evidence/source_manifest.json", {}).get("sources") or []),
        ("evidence_manual_review", "data/evidence/manual_review_queue.json", load_json("data/evidence/manual_review_queue.json", {}).get("items") or []),
    ]
    rows = []
    for source_type, path, items in sources:
        for idx, item in enumerate(items):
            row = {k: scalar(v) for k, v in item.items()}
            row["queue_type"] = source_type
            row["source_file"] = path
            row["source_runtime_path"] = f"{path}:items[{idx}]"
            rows.append(row)
    return rows


def qc_rows() -> list[dict[str, Any]]:
    files = [
        "data/meta/clinical_regimen_quality_issues.json",
        "data/meta/antiviral_regimen_quality_issues.json",
        "data/meta/antibiotic_rdu_quality_issues.json",
        "data/meta/workbook_quality_issues.json",
        "data/meta/manual_review_queue.json",
        "data/meta/correction_overlay_applied.json",
    ]
    rows = []
    for path in files:
        data = load_json(path, {})
        items = data.get("issues") or data.get("items") or data.get("applied") or data.get("corrections") or []
        if isinstance(items, dict):
            items = list(items.values())
        for idx, item in enumerate(items):
            row = {k: scalar(v) for k, v in (item or {}).items()}
            row["source_file"] = path
            row["source_runtime_path"] = f"{path}:items[{idx}]"
            rows.append(row)
    return rows


def import_diff_template() -> list[dict[str, Any]]:
    return [
        {
            "change_id": "",
            "target_type": "product/regimen/source/pediatric/antibiotic",
            "stable_id": "",
            "field_name": "",
            "old_value": "",
            "new_value": "",
            "source_id": "",
            "reviewer": "",
            "review_status": "pending",
            "notes": "",
        }
    ]


def opd_fast_index_rows(opd: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for idx, item in enumerate(opd.get("index") or []):
        row = {k: scalar(v) for k, v in item.items()}
        row["source_runtime_path"] = f"data/core/opd_fast_index.json:index[{idx}]"
        rows.append(row)
    return rows


def drug_short_lookup_rows(short_lookup: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    lookup = short_lookup.get("lookup") or {}
    for idx, (product_id, item) in enumerate(lookup.items()):
        row = {"product_id": product_id}
        if isinstance(item, dict):
            row.update({k: scalar(v) for k, v in item.items()})
        else:
            row["value"] = scalar(item)
        row["source_runtime_path"] = f"data/core/drug_short_lookup.json:lookup.{product_id}"
        rows.append(row)
    return rows


def union_columns(rows: list[dict[str, Any]], preferred: list[str] | None = None) -> list[str]:
    preferred = preferred or []
    seen = list(preferred)
    for row in rows:
        for key in row:
            if key not in seen:
                seen.append(key)
    return seen or preferred


def write_csv(sheet_name: str, rows: list[dict[str, Any]], columns: list[str]) -> None:
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    path = CSV_DIR / f"{sheet_name}.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({col: scalar(row.get(col, "")) for col in columns})


def col_name(index: int) -> str:
    name = ""
    while index:
        index, rem = divmod(index - 1, 26)
        name = chr(65 + rem) + name
    return name


def xml_cell(value: Any, row: int, col: int) -> str:
    ref = f"{col_name(col)}{row}"
    value = scalar(value)
    if value is None or value == "":
        return f'<c r="{ref}"/>'
    if isinstance(value, bool):
        return f'<c r="{ref}" t="b"><v>{1 if value else 0}</v></c>'
    if isinstance(value, (int, float)):
        return f'<c r="{ref}"><v>{value}</v></c>'
    text = escape(str(value), {'"': "&quot;"})
    return f'<c r="{ref}" t="inlineStr"><is><t>{text}</t></is></c>'


def worksheet_xml(rows: list[dict[str, Any]], columns: list[str]) -> str:
    data_rows = []
    header = "".join(xml_cell(col, 1, idx + 1) for idx, col in enumerate(columns))
    data_rows.append(f'<row r="1">{header}</row>')
    for r_idx, row in enumerate(rows, start=2):
        cells = "".join(xml_cell(row.get(col, ""), r_idx, c_idx + 1) for c_idx, col in enumerate(columns))
        data_rows.append(f'<row r="{r_idx}">{cells}</row>')
    dim = f"A1:{col_name(max(1, len(columns)))}{max(1, len(rows) + 1)}"
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<dimension ref="{dim}"/><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        '<sheetData>'
        + "".join(data_rows)
        + '</sheetData><autoFilter ref="'
        + dim
        + '"/></worksheet>'
    )


def write_xlsx(sheet_data: dict[str, tuple[list[dict[str, Any]], list[str]]]) -> None:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    workbook_sheets = []
    workbook_rels = []
    content_overrides = [
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>',
    ]
    with zipfile.ZipFile(WORKBOOK, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            + "".join(content_overrides)
            + "".join(
                f'<Override PartName="/xl/worksheets/sheet{idx}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                for idx, _ in enumerate(sheet_data, start=1)
            )
            + "</Types>",
        )
        zf.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>",
        )
        zf.writestr(
            "xl/styles.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts><fills count="1"><fill><patternFill patternType="none"/></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs></styleSheet>',
        )
        for idx, (sheet_name, (rows, columns)) in enumerate(sheet_data.items(), start=1):
            workbook_sheets.append(f'<sheet name="{escape(sheet_name)}" sheetId="{idx}" r:id="rId{idx}"/>')
            workbook_rels.append(
                f'<Relationship Id="rId{idx}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{idx}.xml"/>'
            )
            zf.writestr(f"xl/worksheets/sheet{idx}.xml", worksheet_xml(rows, columns))
        zf.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
            + "".join(workbook_sheets)
            + "</sheets></workbook>",
        )
        zf.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(workbook_rels)
            + "</Relationships>",
        )


def high_risk_sample(regimen_rows: list[dict[str, Any]], products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    product_by_id = {p.get("product_id"): p for p in products}
    rows = []
    for row in regimen_rows:
        product = product_by_id.get(row.get("product_id"), {})
        hay = " ".join(str(x) for x in [row, product]).lower()
        if any(token in hay for token in ["acyclovir", "antibiotic", "pediatric", "child", "eye", "otic", "zoster", "shingles"]):
            rows.append(row)
        if len(rows) >= 20:
            break
    return rows


def write_reports(
    sheet_data: dict[str, tuple[list[dict[str, Any]], list[str]]],
    runtime: dict[str, Any],
    regimen_rows: list[dict[str, Any]],
    product_rows_: list[dict[str, Any]],
    fast_master: dict[str, Any],
) -> None:
    product_names = [str(row.get("brand_name") or "") for row in product_rows_ if row.get("brand_name")]
    regimen_ids = [str(row.get("regimen_id") or "") for row in regimen_rows if row.get("regimen_id")]
    fast_regimen_ids = [str(row.get("regimen_id") or "") for row in fast_master.get("regimens", []) if row.get("regimen_id")]
    runtime_fields = {
        "runtime_meta": sorted((runtime.get("m") or {}).keys()),
        "product_fields": sorted({k for row in runtime.get("dr", []) for k in row.keys()}),
        "complaint_fields": sorted({k for row in runtime.get("cp", []) for k in row.keys()}),
        "regimen_line_fields": sorted({k for c in runtime.get("cp", []) for r in c.get("r", []) for m in r.get("m", []) for k in m.keys()}),
    }
    desired = set(PRODUCT_COLUMNS + REGIMEN_COLUMNS)
    found = set(runtime_fields["product_fields"] + runtime_fields["complaint_fields"] + runtime_fields["regimen_line_fields"])
    missing_desired = sorted(desired - found - {"product_id", "brand_name", "generic_name", "dosage_form", "pack", "price", "BDS", "regimen_id", "disease_key", "disease_name", "complaint_key", "role", "tier", "sig", "duration", "dispense", "old_runtime_status", "source_runtime_path", "manual_review_required", "antibiotic_flag", "pediatric_flag", "pregnancy_lactation"})
    blocked_manual = [
        row
        for row in regimen_rows
        if row.get("clinical_readiness") in {"blocked", "manual_review_required"}
    ]
    missing_desired_lines = [f"- {field}" for field in missing_desired] or ["- None from mapped desired schema."]
    duplicate_product_lines = [
        f"- {name}: {count}"
        for name, count in Counter(product_names).most_common()
        if count > 1
    ][:50] or ["- None"]
    missing_source = [row for row in regimen_rows if row.get("source_status") != "source_verified"]
    high_risk = high_risk_sample(regimen_rows, product_rows_)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(
        "\n".join(
            [
                "# Export Refresh Workbook Report",
                "",
                f"- Generated at: {datetime.now(timezone.utc).isoformat()}",
                f"- Workbook: `exports/{WORKBOOK.name}`",
                f"- CSV directory: `exports/refresh_csv/`",
                f"- Total products: {len(product_rows_)}",
                f"- Total complaints: {len(runtime.get('cp') or [])}",
                f"- Total disease keys: {len({row.get('disease_key') for row in regimen_rows if row.get('disease_key')})}",
                f"- Total regimen rows: {len(regimen_rows)}",
                f"- Rows with missing product_id: {sum(1 for row in regimen_rows if not row.get('product_id'))}",
                f"- Rows with missing disease_key: {sum(1 for row in regimen_rows if not row.get('disease_key'))}",
                f"- Rows with missing source: {len(missing_source)}",
                f"- Rows with blocked/manual_review status: {len(blocked_manual)}",
                f"- Duplicate product names: {sum(1 for _name, count in Counter(product_names).items() if count > 1)}",
                f"- Duplicate regimen IDs in fast regimen master: {sum(1 for _rid, count in Counter(fast_regimen_ids).items() if count > 1)}",
                f"- Repeated regimen IDs across complaint aliases: {sum(1 for _rid, count in Counter(regimen_ids).items() if count > 1)}",
                "",
                "## Tabs",
                "",
                *[f"- {name}: {len(rows)} rows" for name, (rows, _columns) in sheet_data.items()],
                "",
                "## Sample 20 High-Risk Rows",
                "",
                "| regimen_id | disease_key | product_id | drug_name | readiness | source | next_action |",
                "|---|---|---|---|---|---|---|",
                *[
                    f"| {row.get('regimen_id','')} | {row.get('disease_key','')} | {row.get('product_id','')} | {str(row.get('drug_name',''))[:80]} | {row.get('clinical_readiness','')} | {row.get('source_status','')} | {str(row.get('next_action',''))[:80]} |"
                    for row in high_risk
                ],
                "",
                "## Runtime Schema Fields Found",
                "",
                "```json",
                json.dumps(runtime_fields, ensure_ascii=False, indent=2),
                "```",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    GAP_REPORT.write_text(
        "\n".join(
            [
                "# Export Data Gap Report",
                "",
                "## Exact Fields Missing From Desired Schema",
                "",
                *missing_desired_lines,
                "",
                "## Counts",
                "",
                f"- Missing product_id regimen rows: {sum(1 for row in regimen_rows if not row.get('product_id'))}",
                f"- Missing disease_key regimen rows: {sum(1 for row in regimen_rows if not row.get('disease_key'))}",
                f"- Source-unverified regimen rows: {len(missing_source)}",
                f"- Blocked/manual-review regimen rows: {len(blocked_manual)}",
                "",
                "## Duplicate Product Names",
                "",
                *duplicate_product_lines,
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    runtime = load_json("data/core/app_seed_runtime.json", {})
    product_rows_ = product_rows(runtime)
    product_by_id = {row["product_id"]: item for row, item in zip(product_rows_, runtime.get("dr") or [])}
    regimen_rows = flatten_regimens(runtime, product_by_id)
    complaints = load_json("data/core/complaint_index.json", {})
    diseases = load_json("data/core/disease_master.json", {})
    fast_master = load_json("data/core/fast_regimen_master.json", {})
    peds = load_json("data/pediatric/peds_product_dose_output.json", {})
    antibiotic_issues = load_json("data/meta/antibiotic_rdu_quality_issues.json", {})
    opd = load_json("data/core/opd_fast_index.json", {})
    short_lookup = load_json("data/core/drug_short_lookup.json", {})

    sheet_rows: dict[str, list[dict[str, Any]]] = {
        "1_Product_Master_Export": product_rows_,
        "2_Regimen_Master_Export": regimen_rows,
        "3_Complaint_Disease_Map": complaint_rows(runtime, complaints, diseases),
        "4_Top_50_Defaults": top_defaults(regimen_rows),
        "5_Clinic_Defaults": clinic_defaults(fast_master),
        "6_Pediatric_Dosing": pediatric_rows(peds),
        "7_Antibiotic_Rows": antibiotic_rows(product_rows_, regimen_rows, antibiotic_issues),
        "8_Source_Evidence_Queue": source_queue_rows(),
        "9_Clinical_QC": qc_rows(),
        "10_Import_Diff_Template": import_diff_template(),
        "11_OPD_Fast_Index_Template": opd_fast_index_rows(opd),
        "12_Drug_Short_Lookup_Template": drug_short_lookup_rows(short_lookup),
    }
    preferred = {
        "1_Product_Master_Export": PRODUCT_COLUMNS,
        "2_Regimen_Master_Export": REGIMEN_COLUMNS,
        "10_Import_Diff_Template": list(import_diff_template()[0].keys()),
    }
    sheet_data: dict[str, tuple[list[dict[str, Any]], list[str]]] = {}
    for name in SHEETS:
        rows = sheet_rows.get(name, [])
        columns = union_columns(rows, preferred.get(name))
        sheet_data[name] = (rows, columns)
        write_csv(name, rows, columns)
    write_xlsx(sheet_data)
    write_reports(sheet_data, runtime, regimen_rows, product_rows_, fast_master)
    print(f"export_refresh_workbook: workbook={WORKBOOK.relative_to(ROOT)}")
    print(f"products={len(product_rows_)} complaints={len(runtime.get('cp') or [])} regimen_rows={len(regimen_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
