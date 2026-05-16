#!/usr/bin/env python3
import argparse
import hashlib
import json
import mimetypes
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
import pandas as pd
import requests
from tqdm import tqdm

SKIP_METHODS = {"manual_review"}
USER_AGENT = "DruglistEvidenceDownloader/1.0 (+manual evidence cache; contact: local user)"
MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024


def safe_name(value: str, max_len=100):
    import re
    value = str(value or "source").strip()
    value = re.sub(r"[^A-Za-z0-9ก-๙._-]+", "_", value)
    return value[:max_len].strip("._-") or "source"


def ext_from_response(url, response):
    path_ext = Path(urlparse(url).path).suffix
    if path_ext:
        return path_ext[:10]
    ctype = response.headers.get("content-type", "").split(";")[0].strip().lower()
    return mimetypes.guess_extension(ctype) or ".html"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_alias(src: Path, alias: Path):
    alias.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() != alias.resolve():
        alias.write_bytes(src.read_bytes())


def download_one(row, timeout):
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    method = row.get("method", "")
    result = dict(row)
    if method in SKIP_METHODS:
        result.update({"status": "skipped_manual", "local_path": "", "sha256": ""})
        return result

    url = row.get("url")
    cache_dir = Path(row.get("cache_dir") or "imports/accepted_evidence/bulk")
    cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        for attempt in range(3):
            try:
                resp = session.get(url, timeout=timeout, allow_redirects=True, stream=True)
                resp.raise_for_status()
                length = int(resp.headers.get("content-length") or 0)
                if length > MAX_DOWNLOAD_BYTES:
                    raise RuntimeError(f"skipped_large_file content_length={length}")
                content = b""
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    content += chunk
                    if len(content) > MAX_DOWNLOAD_BYTES:
                        raise RuntimeError(f"skipped_large_file over {MAX_DOWNLOAD_BYTES} bytes")
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(1 + attempt)
        ext = ext_from_response(url, resp)
        fname = f"{safe_name(row.get('task_id'))}_{safe_name(row.get('record_id'))}{ext}"
        path = cache_dir / fname
        path.write_bytes(content)
        sha = sha256_bytes(content)

        meta = {
            "source_id": row.get("record_id"),
            "task_id": row.get("task_id"),
            "source_url": url,
            "local_path": str(path),
            "sha256": sha,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
            "http_status": resp.status_code,
            "content_type": resp.headers.get("content-type", ""),
            "method": method,
            "source_type": row.get("sheet", ""),
            "linked_rows": row.get("linked_rows", ""),
            "notes": "Auto-downloaded. Review content before using for Gold verification."
        }
        (path.with_suffix(path.suffix + ".meta.json")).write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        result.update({"status": "downloaded", "local_path": str(path), "sha256": sha, "http_status": resp.status_code, "content_type": resp.headers.get("content-type", ""), "notes": ""})
    except Exception as e:
        result.update({"status": "failed", "local_path": "", "sha256": "", "notes": str(e)[:500]})
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", required=True)
    parser.add_argument("--limit", type=int, default=0, help="0 = no limit")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--out", default="reports/evidence_acquisition/source_download_results.csv")
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()

    df = pd.read_csv(args.queue).fillna("")
    rows = df.to_dict("records")
    if args.limit:
        rows = rows[:args.limit]

    results = []
    with ThreadPoolExecutor(max_workers=max(args.workers, 1)) as pool:
        futures = [pool.submit(download_one, row, args.timeout) for row in rows]
        for future in tqdm(as_completed(futures), total=len(futures), desc="Downloading"):
            results.append(future.result())

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(results).to_csv(out, index=False)
    pd.DataFrame(results).to_csv("reports/source_download_results.csv", index=False)
    print(f"Wrote: {out}")

if __name__ == "__main__":
    main()
