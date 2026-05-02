#!/usr/bin/env python3
"""Build and validate a frontend-only dist folder for static hosting."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from engine_common import ROOT, now_iso, read_json

DIST = ROOT / "dist"
REQUIRED_FILES = [
    "index.html",
    "data/core/app_seed_runtime.json",
    "build_info.json",
]
FRONTEND_JSON = [
    "data/core/app_seed_runtime.json",
]
FORBIDDEN_PARTS = {
    "source_workbooks",
    "source_guidelines",
    "reports",
    "scripts",
    "tests",
    ".venv",
    ".git",
    "__pycache__",
}
FORBIDDEN_SUFFIXES = {".xlsx", ".xls", ".csv", ".sqlite", ".db", ".py", ".pyc"}


def source_commit() -> str:
    try:
        result = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=True)
    except Exception:
        return ""
    return result.stdout.strip()


def copy_file(src: str, dest: str | None = None) -> None:
    source = ROOT / src
    target = DIST / (dest or src)
    if not source.exists():
        raise FileNotFoundError(f"required frontend file missing: {src}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def build_info() -> dict[str, Any]:
    seed = read_json("data/core/app_seed_runtime.json", {"m": {}})
    meta = seed.get("m", {})
    return {
        "schema_version": "druglist-dist-v1",
        "build_version": meta.get("build_version") or "manual",
        "generated_at": now_iso(),
        "source_commit": source_commit(),
        "frontend_files": REQUIRED_FILES,
        "privacy_policy": "frontend-only static artifact; source workbooks, review CSVs, scripts, tests, reports, and databases are excluded",
    }


def build_dist(_: argparse.Namespace) -> int:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    copy_file("index.html")
    for path in FRONTEND_JSON:
        copy_file(path)
    (DIST / "build_info.json").write_text(json.dumps(build_info(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    validate_dist_files()
    print("built frontend dist: dist/")
    return 0


def validate_dist_files() -> None:
    if not DIST.exists():
        raise FileNotFoundError("dist/ does not exist")
    for path in REQUIRED_FILES:
        target = DIST / path
        if not target.exists() or target.stat().st_size == 0:
            raise RuntimeError(f"dist required file missing or empty: {path}")
    for path in DIST.rglob("*"):
        rel = path.relative_to(DIST)
        parts = set(rel.parts)
        if parts & FORBIDDEN_PARTS:
            raise RuntimeError(f"forbidden private path in dist: {rel}")
        if path.is_file() and path.suffix.lower() in FORBIDDEN_SUFFIXES:
            raise RuntimeError(f"forbidden private file type in dist: {rel}")
    seed = json.loads((DIST / "data/core/app_seed_runtime.json").read_text(encoding="utf-8"))
    if not seed.get("dr") or not seed.get("cp"):
        raise RuntimeError("dist runtime seed is missing drugs or complaints")


def validate_only(_: argparse.Namespace) -> int:
    validate_dist_files()
    print("validated frontend dist: dist/")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-only", action="store_true", help="validate existing dist/ without rebuilding")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return validate_only(args) if args.validate_only else build_dist(args)
    except Exception as exc:
        print(f"dist build failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
