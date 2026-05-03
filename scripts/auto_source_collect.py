#!/usr/bin/env python3
"""Plan and cache source collection for unresolved Druglist evidence gaps."""
from __future__ import annotations

import argparse
import hashlib
import html
import re
import urllib.request
from pathlib import Path
from typing import Any

from engine_common import clean, now_iso, read_json, write_json
from evidence_common import (
    EVIDENCE_DIR,
    HTML_CACHE_DIR,
    PDF_CACHE_DIR,
    REPORT_DIR,
    TEXT_CACHE_DIR,
    ensure_evidence_dirs,
    make_gap_task,
)


def load_tasks() -> list[dict[str, Any]]:
    return read_json("data/evidence/source_search_tasks.json", {"tasks": []}).get("tasks", [])


def write_markdown_report(path: Path, title: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([f"# {title}", "", f"Generated: {now_iso()}", "", *lines]).rstrip() + "\n", encoding="utf-8")


def plan() -> dict[str, Any]:
    ensure_evidence_dirs()
    gaps = read_json("data/guidelines/source_gap_list.json", {"items": []}).get("items", [])
    groups = read_json("data/evidence/source_allowlist.json", {"groups": []}).get("groups", [])
    tasks = [make_gap_task(gap, group) for gap in gaps for group in groups]
    summary = {
        "generated_at": now_iso(),
        "gap_count": len(gaps),
        "source_group_count": len(groups),
        "task_count": len(tasks),
        "ready_to_collect_count": sum(1 for task in tasks if task["status"] == "ready_to_collect"),
        "pending_url_discovery_count": sum(1 for task in tasks if task["status"] == "pending_url_discovery"),
    }
    write_json("data/evidence/source_search_tasks.json", {"meta": summary, "tasks": tasks})
    write_markdown_report(
        REPORT_DIR / "source_collection_plan.md",
        "Source Collection Plan",
        [
            f"- Source gaps: {summary['gap_count']}",
            f"- Allowlist groups: {summary['source_group_count']}",
            f"- Search tasks: {summary['task_count']}",
            f"- Ready to collect: {summary['ready_to_collect_count']}",
            f"- Pending URL discovery: {summary['pending_url_discovery_count']}",
            "",
            "No source is verified by planning alone.",
        ],
    )
    return summary


def cache_name(url: str) -> str:
    suffix = ".pdf" if url.lower().split("?")[0].endswith(".pdf") else ".html"
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16] + suffix


def collect() -> dict[str, Any]:
    ensure_evidence_dirs()
    if not (EVIDENCE_DIR / "source_search_tasks.json").exists():
        plan()
    manifest_entries: list[dict[str, Any]] = []
    for task in load_tasks():
        url = clean(task.get("url"))
        if not url:
            manifest_entries.append({**task, "collection_status": "pending_source_collection", "cache_path": ""})
            continue
        name = cache_name(url)
        target = (PDF_CACHE_DIR if name.endswith(".pdf") else HTML_CACHE_DIR) / name
        try:
            with urllib.request.urlopen(url, timeout=20) as response:
                target.write_bytes(response.read())
            status = "cached"
        except Exception as exc:  # network is intentionally optional
            status = "pending_source_collection"
            task = {**task, "collection_error": str(exc)[:240]}
        manifest_entries.append({**task, "collection_status": status, "cache_path": str(target.relative_to(EVIDENCE_DIR)) if target.exists() else ""})
    summary = {
        "generated_at": now_iso(),
        "source_count": len(manifest_entries),
        "cached_count": sum(1 for entry in manifest_entries if entry.get("collection_status") == "cached"),
        "pending_source_collection_count": sum(1 for entry in manifest_entries if entry.get("collection_status") != "cached"),
    }
    write_json("data/evidence/source_cache_manifest.json", {"meta": summary, "sources": manifest_entries})
    return summary


def html_to_text(raw: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def extract_text() -> dict[str, Any]:
    ensure_evidence_dirs()
    manifest = read_json("data/evidence/source_cache_manifest.json", {"sources": []})
    sources = manifest.get("sources", [])
    extracted = 0
    for source in sources:
        cache_path = clean(source.get("cache_path"))
        if not cache_path:
            continue
        cached = EVIDENCE_DIR / cache_path
        if not cached.exists() or cached.suffix.lower() == ".pdf":
            continue
        text = html_to_text(cached.read_text(encoding="utf-8", errors="ignore"))
        if not text:
            continue
        out = TEXT_CACHE_DIR / (cached.stem + ".txt")
        out.write_text(text + "\n", encoding="utf-8")
        source["text_cache_path"] = str(out.relative_to(EVIDENCE_DIR))
        source["extraction_status"] = "text_extracted"
        extracted += 1
    summary = {
        "generated_at": now_iso(),
        "source_count": len(sources),
        "text_extracted_count": extracted,
        "pending_extraction_count": len(sources) - extracted,
    }
    write_json("data/evidence/source_cache_manifest.json", {"meta": summary, "sources": sources})
    return summary


def summarize_cache() -> dict[str, Any]:
    if not (EVIDENCE_DIR / "source_cache_manifest.json").exists():
        collect()
    manifest = read_json("data/evidence/source_cache_manifest.json", {"meta": {}, "sources": []})
    meta = manifest.get("meta", {})
    write_markdown_report(
        REPORT_DIR / "source_cache_summary.md",
        "Source Cache Summary",
        [
            f"- Sources tracked: {meta.get('source_count', 0)}",
            f"- Cached: {meta.get('cached_count', 0)}",
            f"- Text extracted: {meta.get('text_extracted_count', 0)}",
            f"- Pending source collection: {meta.get('pending_source_collection_count', 0)}",
            f"- Pending extraction: {meta.get('pending_extraction_count', 0)}",
        ],
    )
    return meta


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", default="summarize-cache", choices=["plan", "collect", "extract-text", "summarize-cache"])
    args = parser.parse_args()
    if args.command == "plan":
        summary = plan()
    elif args.command == "collect":
        summary = collect()
    elif args.command == "extract-text":
        summary = extract_text()
    else:
        summary = summarize_cache()
    print(f"auto_source_collect {args.command}: " + ", ".join(f"{k}={v}" for k, v in summary.items() if k.endswith("_count")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
