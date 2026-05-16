#!/usr/bin/env python3
import argparse
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
import pandas as pd

URL_RE = re.compile(r"https?://[^\s;|,]+")
TARGET_SHEETS = {
    "Source_Download_Links",
    "Bulk_Source_Tasks",
    "Disease_Download_Map",
    "Drug_Label_Links",
    "Product_Label_Links",
}

MANUAL_DOMAINS = [
    "mims.com",
    "ndi.fda.moph.go.th",
]

DYNAMIC_HINTS = ["search", "query", "q=", "keyword", "medicine", "browse"]


def slugify(value: str, fallback="item") -> str:
    value = str(value or "").strip().lower()
    value = re.sub(r"[^a-z0-9ก-๙]+", "-", value)
    value = value.strip("-")
    return value[:80] or fallback


def extract_urls(*values):
    urls = []
    for v in values:
        if pd.isna(v):
            continue
        urls.extend(URL_RE.findall(str(v)))
    return list(dict.fromkeys(urls))


def normalize_url(url: str) -> str:
    parsed = urlparse(str(url).strip())
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or parsed.path
    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)), doseq=True)
    return urlunparse((scheme, netloc, path, "", query, ""))


def classify_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if any(d in host for d in MANUAL_DOMAINS):
        return "manual_review"
    lower = url.lower()
    if lower.endswith((".pdf", ".xml", ".zip", ".json", ".csv", ".xlsx", ".xls")):
        return "direct_download"
    if any(h in lower for h in DYNAMIC_HINTS):
        return "download_html_or_manual"
    return "download_html"


def cache_dir_for(sheet, row):
    if sheet == "Disease_Download_Map":
        key = row.get("Disease_Key") or row.get("Disease") or row.get("Disease_Bundle") or "disease"
        return f"imports/accepted_evidence/disease/{slugify(key, 'disease')}"
    if sheet == "Drug_Label_Links":
        key = row.get("Drug") or row.get("Generic") or row.get("Generic_Name") or row.get("Drug_Key") or "drug"
        return f"imports/accepted_evidence/drug/{slugify(key, 'drug')}"
    if sheet == "Product_Label_Links":
        key = row.get("Product_Code") or row.get("Product") or row.get("Brand") or row.get("Product_Name") or "product"
        return f"imports/accepted_evidence/product/{slugify(key, 'product')}"
    if sheet == "Bulk_Source_Tasks":
        key = row.get("Source_ID") or row.get("Task") or row.get("Source") or "bulk"
        return f"imports/accepted_evidence/bulk/{slugify(key, 'bulk')}"
    return "imports/accepted_evidence/bulk"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--links-xlsx", required=True)
    parser.add_argument("--out", default="reports/evidence_acquisition/source_download_queue.csv")
    parser.add_argument("--manual-out", default="reports/evidence_acquisition/manual_download_todo.csv")
    args = parser.parse_args()

    xls = pd.ExcelFile(args.links_xlsx)
    queue = []
    by_url = {}

    for sheet in xls.sheet_names:
        if sheet not in TARGET_SHEETS:
            continue
        df = pd.read_excel(args.links_xlsx, sheet_name=sheet, dtype=str).fillna("")
        for idx, row in df.iterrows():
            data = row.to_dict()
            urls = extract_urls(*data.values())
            if not urls:
                continue
            label = data.get("Source_ID") or data.get("Disease_Key") or data.get("Drug") or data.get("Product") or data.get("Product_Code") or f"{sheet}_{idx+2}"
            name = data.get("Title") or data.get("Disease") or data.get("Generic") or data.get("Product_Name") or label
            for u in urls:
                normalized = normalize_url(u)
                linked_ref = f"{sheet}:{idx + 2}:{label}"
                if normalized in by_url:
                    existing = by_url[normalized]
                    refs = existing["linked_rows"].split("|") if existing["linked_rows"] else []
                    if linked_ref not in refs:
                        refs.append(linked_ref)
                    ids = existing["record_ids"].split("|") if existing["record_ids"] else []
                    if str(label) not in ids:
                        ids.append(str(label))
                    existing["linked_rows"] = "|".join(refs)
                    existing["record_ids"] = "|".join(ids)
                    continue
                record = {
                    "task_id": f"T{len(queue)+1:05d}",
                    "sheet": sheet,
                    "row_number": idx + 2,
                    "record_id": str(label),
                    "record_ids": str(label),
                    "name": str(name),
                    "url": u,
                    "normalized_url": normalized,
                    "method": classify_url(u),
                    "cache_dir": cache_dir_for(sheet, data),
                    "linked_rows": linked_ref,
                    "status": "queued",
                    "notes": ""
                }
                by_url[normalized] = record
                queue.append(record)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(queue).to_csv(out, index=False)

    manual = [r for r in queue if r["method"] in ["manual_review"]]
    manual_out = Path(args.manual_out)
    manual_out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(manual).to_csv(manual_out, index=False)
    Path("reports").mkdir(exist_ok=True)
    pd.DataFrame(queue).to_csv("reports/source_download_queue.csv", index=False)
    pd.DataFrame(manual).to_csv("reports/manual_download_todo.csv", index=False)

    print(f"Queue rows: {len(queue)}")
    print(f"Manual rows: {len(manual)}")
    print(f"Wrote: {out}")
    print(f"Wrote: {manual_out}")

if __name__ == "__main__":
    main()
