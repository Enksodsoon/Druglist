#!/usr/bin/env python3
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

SKIP_EXTS = {".jsonl"}


def sha256_file(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="imports/accepted_evidence")
    parser.add_argument("--out", default="reports/evidence_acquisition/evidence_manifest.jsonl")
    args = parser.parse_args()

    root = Path(args.root)
    records = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.name.startswith(".") or p.suffix in SKIP_EXTS or p.name.endswith(".meta.json"):
            continue
        meta_path = p.with_suffix(p.suffix + ".meta.json")
        meta = {}
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                meta = {}
        records.append({
            "source_id": meta.get("source_id") or p.parent.name,
            "task_id": meta.get("task_id", ""),
            "source_type": meta.get("method", "unknown"),
            "region": meta.get("region", ""),
            "source_url": meta.get("source_url", ""),
            "local_path": str(p),
            "sha256": sha256_file(p),
            "downloaded_at": meta.get("downloaded_at") or datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat(),
            "file_ext": p.suffix.lower(),
            "status": "cached",
            "notes": meta.get("notes", "")
        })

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    Path("reports/evidence_manifest.jsonl").write_text(out.read_text(encoding="utf-8"), encoding="utf-8")

    print(f"Manifest records: {len(records)}")
    print(f"Wrote: {out}")

if __name__ == "__main__":
    main()
