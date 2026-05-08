#!/usr/bin/env python3
"""Shared helpers for conservative medical source refresh automation."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import urllib.request
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = ROOT / "exports"
CSV_DIR = EXPORT_DIR / "refresh_csv"
SOURCE_DIR = ROOT / "data/source_refresh"
REPORT_DIR = ROOT / "reports/source_refresh"
CACHE_DIR = SOURCE_DIR / "cache"
TEXT_DIR = SOURCE_DIR / "source_text"
BASE_WORKBOOK = EXPORT_DIR / "Druglist_Data_Refresh_Master.xlsx"
REFRESHED_WORKBOOK = EXPORT_DIR / "Druglist_Data_Refresh_Master_SOURCE_REFRESHED.xlsx"

TRUSTED_DOMAINS = [
    "ndi.fda.moph.go.th",
    "ndp.fda.moph.go.th",
    "fda.moph.go.th",
    "dms.moph.go.th",
    "moph.go.th",
    "who.int",
    "cdc.gov",
    "nice.org.uk",
    "idsociety.org",
    "ginasthma.org",
    "goldcopd.org",
    "aap.org",
    "aao.org",
    "eau.org",
]

OFFICIAL_SOURCE_SEEDS = [
    {
        "task_hint": "acyclovir herpes zoster adult antiviral timing",
        "source_id": "cdc_shingles_clinical_overview",
        "url": "https://www.cdc.gov/shingles/hcp/clinical-overview/index.html",
        "title": "Clinical Overview of Shingles (Herpes Zoster)",
        "organization": "Centers for Disease Control and Prevention",
        "country": "United States",
        "source_type": "guideline",
        "domain": "antiviral",
        "year": "2024",
        "expected_claims": ["disease_strategy", "timing_window", "red_flags"],
    },
    {
        "task_hint": "genital herpes acyclovir antiviral regimen",
        "source_id": "cdc_sti_herpes_guideline",
        "url": "https://www.cdc.gov/std/treatment-guidelines/herpes.htm",
        "title": "Sexually Transmitted Infections Treatment Guidelines: Herpes",
        "organization": "Centers for Disease Control and Prevention",
        "country": "United States",
        "source_type": "guideline",
        "domain": "antiviral",
        "year": "2021",
        "expected_claims": ["disease_indication", "adult_dose", "duration"],
    },
    {
        "task_hint": "WHO essential medicines children paracetamol ibuprofen ORS",
        "source_id": "who_eml_emlc_lists",
        "url": "https://www.who.int/groups/expert-committee-on-selection-and-use-of-essential-medicines/essential-medicines-lists",
        "title": "WHO Model Lists of Essential Medicines",
        "organization": "World Health Organization",
        "country": "International",
        "source_type": "formulary",
        "domain": "pediatric",
        "year": "2025",
        "expected_claims": ["product_label_composition", "product_label_concentration"],
    },
    {
        "task_hint": "WHO AWaRe no antibiotic viral URI simple diarrhea primary care",
        "source_id": "who_aware_antibiotic_book",
        "url": "https://iris.who.int/bitstream/handle/10665/365237/9789240062382-eng.pdf",
        "title": "The WHO AWaRe Antibiotic Book",
        "organization": "World Health Organization",
        "country": "International",
        "source_type": "guideline",
        "domain": "antibiotic_rdu",
        "year": "2022",
        "expected_claims": ["no_antibiotic_criteria", "antibiotic_use_criteria"],
    },
    {
        "task_hint": "NICE sore throat antimicrobial prescribing no antibiotic",
        "source_id": "nice_sore_throat_antimicrobial",
        "url": "https://www.nice.org.uk/guidance/ng84",
        "title": "Sore throat (acute): antimicrobial prescribing",
        "organization": "National Institute for Health and Care Excellence",
        "country": "United Kingdom",
        "source_type": "guideline",
        "domain": "antibiotic_rdu",
        "year": "2018",
        "expected_claims": ["no_antibiotic_criteria", "antibiotic_use_criteria"],
    },
]


def ensure_dirs() -> None:
    for path in [SOURCE_DIR, REPORT_DIR, CACHE_DIR, TEXT_DIR, EXPORT_DIR, EXPORT_DIR / "source_refresh_csv"]:
        path.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def access_date() -> str:
    return date.today().isoformat()


def read_json(path: str | Path, default: Any) -> Any:
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(path: str | Path, payload: Any) -> None:
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_report(path: str | Path, title: str, lines: list[str]) -> None:
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# " + title + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")


def read_csv_sheet(sheet_name: str) -> list[dict[str, str]]:
    path = CSV_DIR / f"{sheet_name}.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if columns is None:
        columns = []
        for row in rows:
            for key in row:
                if key not in columns:
                    columns.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: serialize(row.get(key, "")) for key in columns})


def serialize(value: Any) -> str | int | float | bool:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return "; ".join(str(serialize(v)) for v in value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(part or "") for part in parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def lower_blob(row: dict[str, Any]) -> str:
    return " ".join(str(v) for v in row.values()).lower()


def official_domain(url: str) -> bool:
    return any(domain in url.lower() for domain in TRUSTED_DOMAINS)


class TextHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip = False

    def handle_starttag(self, tag: str, attrs):
        if tag.lower() in {"script", "style", "nav", "footer"}:
            self.skip = True

    def handle_endtag(self, tag: str):
        if tag.lower() in {"script", "style", "nav", "footer"}:
            self.skip = False

    def handle_data(self, data: str):
        text = data.strip()
        if text and not self.skip:
            self.parts.append(text)


def html_to_text(raw: bytes) -> str:
    parser = TextHTMLParser()
    parser.feed(raw.decode("utf-8", errors="ignore"))
    text = "\n".join(parser.parts)
    return re.sub(r"\n{3,}", "\n\n", text)


def fetch_url(url: str, timeout: int = 20) -> tuple[str, bytes | None, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "DruglistSourceRefresh/1.0 (+https://github.com/Enksodsoon/Druglist)"
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            ctype = response.headers.get("content-type", "")
            return ctype, response.read(4_000_000), ""
    except Exception as exc:
        return "", None, str(exc)


def text_window(text: str, keywords: list[str], width: int = 420) -> str:
    low = text.lower()
    for keyword in keywords:
        idx = low.find(keyword.lower())
        if idx >= 0:
            start = max(0, idx - width // 2)
            end = min(len(text), idx + width // 2)
            return re.sub(r"\s+", " ", text[start:end]).strip()
    return ""


def high_risk_rows() -> dict[str, list[dict[str, str]]]:
    regimen = read_csv_sheet("2_Regimen_Master_Export")
    pediatric = read_csv_sheet("6_Pediatric_Dosing")
    antibiotic = read_csv_sheet("7_Antibiotic_Rows")
    qc = read_csv_sheet("9_Clinical_QC")
    high = []
    for row in regimen:
        blob = lower_blob(row)
        if any(token in blob for token in ["acyclovir", "zoster", "shingles", "herpes", "antibiotic", "child", "pediatric", "eye", "ophthalm", "nsaid", "steroid", "cough", "cold"]):
            high.append(row)
    return {"regimen": regimen, "high": high, "pediatric": pediatric, "antibiotic": antibiotic, "qc": qc}
