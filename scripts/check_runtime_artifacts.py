#!/usr/bin/env python3
"""Lightweight checks for runtime/deploy artifacts."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MIN_HTML_BYTES = 1000
REQUIRED_HTML = ["index.html", "dist/index.html"]
REQUIRED_SEEDS = ["data/core/app_seed_runtime.json", "dist/data/core/app_seed_runtime.json"]
FORBIDDEN_DIST_PARTS = {"source_workbooks", "source_guidelines", "reports", "scripts", "tests", ".venv"}
FORBIDDEN_DIST_SUFFIXES = {".xlsx", ".xls", ".sqlite", ".db", ".csv", ".py"}


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def load_json(path: Path, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        fail(errors, f"missing_json:{path.relative_to(ROOT)}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(errors, f"invalid_json:{path.relative_to(ROOT)}:{exc}")
        return {}


def seed_rows(seed: dict[str, Any]) -> tuple[list[Any], list[Any]]:
    drugs = seed.get("dr") or seed.get("products") or seed.get("data", {}).get("dr") or []
    complaints = seed.get("cp") or seed.get("complaints") or seed.get("data", {}).get("cp") or []
    return drugs, complaints


def check_html(errors: list[str]) -> None:
    for name in REQUIRED_HTML:
        path = ROOT / name
        if not path.exists():
            fail(errors, f"missing_html:{name}")
            continue
        size = path.stat().st_size
        if size <= MIN_HTML_BYTES:
            fail(errors, f"suspiciously_tiny_html:{name}:{size}")


def check_seed(errors: list[str]) -> None:
    for name in REQUIRED_SEEDS:
        seed = load_json(ROOT / name, errors)
        if not seed:
            continue
        drugs, complaints = seed_rows(seed)
        meta = seed.get("m") or seed.get("meta") or {}
        if not drugs:
            fail(errors, f"runtime_seed_has_zero_drugs:{name}")
        if not complaints:
            fail(errors, f"runtime_seed_has_zero_complaints:{name}")
        if not (meta.get("generated_at") and meta.get("build_version")):
            fail(errors, f"runtime_seed_missing_metadata:{name}")


def check_dist_metadata(errors: list[str]) -> None:
    info = load_json(ROOT / "dist/build_info.json", errors)
    if info and not all(info.get(key) for key in ["generated_at", "build_version", "source_commit"]):
        fail(errors, "dist_build_info_missing_generated_at_build_version_or_source_commit")


def check_dist_privacy(errors: list[str]) -> None:
    dist = ROOT / "dist"
    if not dist.exists():
        fail(errors, "missing_dist_directory")
        return
    for path in dist.rglob("*"):
        rel = path.relative_to(dist)
        if set(rel.parts) & FORBIDDEN_DIST_PARTS:
            fail(errors, f"forbidden_private_path_in_dist:{rel}")
        if path.is_file() and path.suffix.lower() in FORBIDDEN_DIST_SUFFIXES:
            fail(errors, f"forbidden_private_file_in_dist:{rel}")


def main() -> int:
    errors: list[str] = []
    check_html(errors)
    check_seed(errors)
    check_dist_metadata(errors)
    check_dist_privacy(errors)
    if errors:
        print("runtime_artifact_check: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("runtime_artifact_check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
