#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
import pandas as pd
import requests
from tqdm import tqdm

DAILYMED_SPLS = "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json?drug_name={name}"
DAILYMED_XML = "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/{setid}.xml"


def first_nonempty(row, candidates):
    for c in candidates:
        if c in row and str(row[c]).strip():
            return str(row[c]).strip()
    return ""


def collect_names(xlsx):
    out = []
    xls = pd.ExcelFile(xlsx)
    for sheet in ["Drug_Label_Links", "Product_Label_Links"]:
        if sheet not in xls.sheet_names:
            continue
        df = pd.read_excel(xlsx, sheet_name=sheet, dtype=str).fillna("")
        for idx, row in df.iterrows():
            d = row.to_dict()
            name = first_nonempty(d, ["Drug", "Generic", "Generic_Name", "Composition", "Product_Name", "Product", "Brand"])
            if not name:
                continue
            out.append({
                "sheet": sheet,
                "row_number": idx + 2,
                "record_id": first_nonempty(d, ["Drug_Key", "Product_Code", "Product", "Product_Name", "Drug", "Generic"]),
                "query_name": name,
            })
    # deduplicate by query name but keep record id in output
    seen = set()
    dedup = []
    for r in out:
        key = r["query_name"].lower()
        if key in seen:
            continue
        seen.add(key)
        dedup.append(r)
    return dedup


def slugify(value: str, fallback="drug") -> str:
    value = str(value or "").strip().lower()
    value = re.sub(r"[^a-z0-9ก-๙]+", "-", value).strip("-")
    return value[:80] or fallback


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--links-xlsx", required=True)
    parser.add_argument("--download-first", action="store_true", help="Deprecated: candidates for ranks 1-3 are always downloaded.")
    parser.add_argument("--candidate-ranks", type=int, default=3)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--out", default="reports/evidence_acquisition/dailymed_candidates.csv")
    args = parser.parse_args()

    rows = collect_names(args.links_xlsx)
    if args.limit:
        rows = rows[:args.limit]

    session = requests.Session()
    session.headers.update({"User-Agent": "DruglistDailyMedResolver/1.0"})
    results = []

    for row in tqdm(rows, desc="DailyMed query"):
        name = row["query_name"]
        try:
            url = DAILYMED_SPLS.format(name=quote(name))
            res = session.get(url, timeout=30)
            res.raise_for_status()
            data = res.json()
            spls = data.get("data") or []
            if not isinstance(spls, list):
                spls = []
            for rank, item in enumerate(spls[: max(args.candidate_ranks, 1)], start=1):
                setid = item.get("setid") or item.get("setId") or ""
                title = item.get("title") or item.get("published_date") or ""
                local_path = ""
                status = "candidate"
                notes = "Candidate only. Do not assume this SPL matches the local drug/product row."
                if setid:
                    cache = Path("imports/accepted_evidence/drug") / slugify(name, "drug")
                    cache.mkdir(parents=True, exist_ok=True)
                    xml = session.get(DAILYMED_XML.format(setid=setid), timeout=30)
                    xml.raise_for_status()
                    xml_url = DAILYMED_XML.format(setid=setid)
                    path = cache / f"dailymed_rank_{rank}_{setid}.xml"
                    path.write_bytes(xml.content)
                    sha = sha256_bytes(xml.content)
                    meta = {
                        "source_id": row.get("record_id"),
                        "task_id": f"DAILYMED_{rank}_{setid}",
                        "source_url": xml_url,
                        "local_path": str(path),
                        "sha256": sha,
                        "downloaded_at": datetime.now(timezone.utc).isoformat(),
                        "http_status": xml.status_code,
                        "content_type": xml.headers.get("content-type", ""),
                        "method": "dailymed_candidate",
                        "source_type": row.get("sheet", ""),
                        "query_name": name,
                        "rank": rank,
                        "setid": setid,
                        "title": title,
                        "notes": notes,
                    }
                    (path.with_suffix(path.suffix + ".meta.json")).write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
                    local_path = str(path)
                results.append({**row, "rank": rank, "setid": setid, "title": title, "spl_version": json.dumps(item, ensure_ascii=False), "xml_url": DAILYMED_XML.format(setid=setid) if setid else "", "local_path": local_path, "status": status, "notes": notes})
            if not spls:
                results.append({**row, "rank": "", "setid": "", "title": "", "spl_version": "", "xml_url": "", "local_path": "", "status": "no_candidate"})
        except Exception as e:
            results.append({**row, "rank": "", "setid": "", "title": "", "spl_version": "", "xml_url": "", "local_path": "", "status": "failed", "notes": str(e)[:500]})

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(results).to_csv(out, index=False)
    pd.DataFrame(results).to_csv("reports/dailymed_candidates.csv", index=False)
    print(f"Wrote: {out}")

if __name__ == "__main__":
    main()
