#!/usr/bin/env python3
"""Shared helpers for Drug Assistant build scripts."""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
PRIMARY_WORKBOOK = ROOT / "source_workbooks" / "Drug list for physician usage added -update 29022024.xlsx"

NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
RNS = {"rel": "http://schemas.openxmlformats.org/package/2006/relationships"}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if re.fullmatch(r"\d+\.0", text):
        return text[:-2]
    return re.sub(r"\s+", " ", text)


def norm_key(value: Any) -> str:
    text = clean(value).lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = text.replace("μg", "mcg")
    text = re.sub(r"[^a-z0-9ก-๙+.%/ ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def stable_id(prefix: str, value: Any) -> str:
    slug = re.sub(r"[^A-Z0-9]+", "_", clean(value).upper()).strip("_")
    return f"{prefix}_{slug[:80]}" if slug else f"{prefix}_UNSPECIFIED"


def ensure_dirs(*paths: str) -> None:
    for path in paths:
        (ROOT / path).mkdir(parents=True, exist_ok=True)


def write_json(path: str | Path, payload: Any) -> None:
    target = ROOT / path if isinstance(path, str) else path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: str | Path, default: Any = None) -> Any:
    target = ROOT / path if isinstance(path, str) else path
    if not target.exists():
        return default
    return json.loads(target.read_text(encoding="utf-8"))


def write_report(path: str, title: str, sections: list[tuple[str, str]]) -> None:
    body = [f"# {title}", "", f"Generated: {now_iso()}", ""]
    for heading, content in sections:
        body.extend([f"## {heading}", "", content.strip(), ""])
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(body).rstrip() + "\n", encoding="utf-8")


def _target_path(target: str) -> str:
    target = target.lstrip("/")
    return target if target.startswith("xl/") else "xl/" + target


def _col_index(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha())
    idx = 0
    for ch in letters:
        idx = idx * 26 + ord(ch.upper()) - 64
    return idx - 1


def _shared_strings(zf: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    return ["".join(t.text or "" for t in si.findall(".//a:t", NS)) for si in root.findall("a:si", NS)]


def _sheet_paths(zf: ZipFile) -> list[tuple[str, str]]:
    wb = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rid_map = {rel.attrib["Id"]: _target_path(rel.attrib["Target"]) for rel in rels.findall("rel:Relationship", RNS)}
    out: list[tuple[str, str]] = []
    for sheet in wb.findall("a:sheets/a:sheet", NS):
        rid = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        out.append((sheet.attrib["name"], rid_map[rid]))
    return out


def read_xlsx_sheet(path: Path, sheet_name: str | None = None) -> list[list[str]]:
    """Read a worksheet with stdlib-only XML parsing."""
    with ZipFile(path) as zf:
        shared = _shared_strings(zf)
        sheets = _sheet_paths(zf)
        if sheet_name:
            selected = next((p for name, p in sheets if name == sheet_name or name.strip() == sheet_name.strip()), None)
            if not selected:
                raise FileNotFoundError(f"Sheet {sheet_name!r} not found in {path.name}")
        else:
            selected = sheets[0][1]
        root = ET.fromstring(zf.read(selected))
        rows: list[list[str]] = []
        for row in root.findall(".//a:sheetData/a:row", NS):
            values: list[str] = []
            for cell in row.findall("a:c", NS):
                idx = _col_index(cell.attrib.get("r", "A1"))
                while len(values) < idx:
                    values.append("")
                cell_type = cell.attrib.get("t")
                raw = cell.find("a:v", NS)
                if cell_type == "inlineStr":
                    value = "".join(t.text or "" for t in cell.findall(".//a:t", NS))
                elif raw is None:
                    value = ""
                elif cell_type == "s":
                    pos = int(raw.text or "0")
                    value = shared[pos] if 0 <= pos < len(shared) else ""
                else:
                    value = raw.text or ""
                values.append(clean(value))
            rows.append(values)
        return rows


def primary_workbook_rows() -> tuple[list[str], list[dict[str, str]]]:
    rows = read_xlsx_sheet(PRIMARY_WORKBOOK, "Final approved")
    if len(rows) < 4:
        raise RuntimeError("Primary workbook has no product rows")
    raw_headers = rows[2]
    seen: dict[str, int] = {}
    headers: list[str] = []
    for idx, header in enumerate(raw_headers, start=1):
        name = clean(header) or f"col_{idx}"
        seen[name] = seen.get(name, 0) + 1
        headers.append(name if seen[name] == 1 else f"{name}.{seen[name] - 1}")
    records: list[dict[str, str]] = []
    for excel_row, row in enumerate(rows[3:], start=4):
        if not any(clean(v) for v in row):
            continue
        record = {headers[i] if i < len(headers) else f"col_{i+1}": clean(row[i]) if i < len(row) else "" for i in range(len(headers))}
        record["_excel_row"] = str(excel_row)
        records.append(record)
    return headers, records


def infer_form(name: str, pack: str, composition: str = "") -> str:
    text = norm_key(f"{name} {pack} {composition}")
    checks = [
        ("tablet", [" tab", "tabs", "tablet", "เม็ด"]),
        ("capsule", [" cap", "capsule", "แคปซูล"]),
        ("syrup", ["syrup", "ซิรัป"]),
        ("suspension", ["susp", "suspension"]),
        ("drops", ["drop", "drops"]),
        ("spray", ["spray"]),
        ("cream", ["cream", "ครีม"]),
        ("ointment", ["ointment", "ขี้ผึ้ง"]),
        ("gel", [" gel", "เจล"]),
        ("solution", ["solution", "soln", "น้ำยา"]),
        ("injection", ["inj", "injection", "vial", "amp"]),
        ("powder", ["sachet", "powder", "ผง"]),
    ]
    for form, keys in checks:
        if any(key in text for key in keys):
            return form
    return "other"


def infer_route(form: str, name: str, composition: str = "") -> str:
    text = norm_key(f"{form} {name} {composition}")
    if any(k in text for k in ["eye", "oph", "ตา"]):
        return "ophthalmic"
    if any(k in text for k in ["ear", "otic", "หู"]):
        return "otic"
    if form in {"cream", "ointment", "gel", "solution", "spray"} and any(k in text for k in ["skin", "topical", "cream", "ointment", "gel"]):
        return "topical"
    if form == "injection":
        return "parenteral"
    if form in {"tablet", "capsule", "syrup", "suspension", "drops", "powder"}:
        return "oral"
    return ""


def category_from_subcategory(subcategory: str) -> str:
    text = norm_key(subcategory)
    rules = [
        ("antibiotic", ["ฆ่าเชื้อ", "antibiotic", "amoxicillin", "azithro"]),
        ("analgesic_antipyretic", ["ปวด", "ไข้", "analgesic", "nsaid"]),
        ("allergy_respiratory", ["แพ้", "antihistamine", "decongest"]),
        ("cough_cold", ["ไอ", "เสมหะ", "cough", "mucolytic"]),
        ("gastrointestinal", ["ท้อง", "กระเพาะ", "diarrhea", "gastro"]),
        ("eye_ear", ["ตา", "หู", "eye", "ear"]),
        ("dermatology", ["ผิว", "skin", "cream", "topical"]),
        ("vitamin_supplement", ["vitamin", "supplement", "วิตามิน"]),
    ]
    for category, keys in rules:
        if any(key in text for key in keys):
            return category
    return clean(subcategory) or "uncategorized"


def role_tags(category: str, generic: str, form: str, thai_sig: str) -> list[str]:
    text = norm_key(f"{category} {generic} {form} {thai_sig}")
    tags: set[str] = set()
    if "antibiotic" in category or any(k in text for k in ["amoxicillin", "azithromycin", "cephalexin", "clavulan"]):
        tags.add("antibiotic")
    if any(k in text for k in ["paracetamol", "ibuprofen", "diclofenac", "naproxen"]):
        tags.add("pain_fever")
    if any(k in text for k in ["cetirizine", "loratadine", "fexofenadine", "chlorpheniramine"]):
        tags.add("allergy")
    if any(k in text for k in ["cough", "ambroxol", "bromhexine", "dextromethorphan", "guaifenesin"]):
        tags.add("cough_cold")
    if any(k in text for k in ["eye", "ophthalmic", "ตา"]):
        tags.add("eye")
    if form in {"syrup", "suspension", "drops"}:
        tags.add("pediatric_candidate")
    return sorted(tags)


def extract_generic(composition: str, product_name: str = "") -> str:
    text = clean(composition)
    if not text:
        return clean(product_name)
    parts = re.split(r"\+|,", text)
    names: list[str] = []
    for part in parts:
        part = re.sub(r"\([^)]*\)", " ", part)
        part = re.sub(r"\b\d[\d,.]*\s*(?:mg|g|mcg|ml|unit|iu|%)\.?(?:/\d+\s*(?:ml|g))?", " ", part, flags=re.I)
        part = re.sub(r"\b(eq|to|acid|hcl)\b", lambda m: m.group(0), part, flags=re.I)
        name = clean(part.strip(" .;:/"))
        if name:
            names.append(name)
    return " + ".join(names[:4]) or clean(composition)


def display_name(product_name: str, composition: str) -> str:
    product = clean(product_name)
    comp = clean(composition)
    return f"{product} [{comp}]" if comp else product
