#!/usr/bin/env python3
"""Shared helpers for automated evidence pipeline scripts."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from engine_common import ROOT, clean, norm_key, read_json, stable_id

EVIDENCE_DIR = ROOT / "data" / "evidence"
REPORT_DIR = ROOT / "reports" / "evidence"
SOURCE_CACHE_DIR = EVIDENCE_DIR / "source_cache"
TEXT_CACHE_DIR = SOURCE_CACHE_DIR / "text"
HTML_CACHE_DIR = SOURCE_CACHE_DIR / "html"
PDF_CACHE_DIR = SOURCE_CACHE_DIR / "pdf"

ALLOWED_EVIDENCE_STATUSES = {
    "auto_verified",
    "auto_resolved",
    "pending_source_collection",
    "pending_extraction",
    "blocked_low_confidence",
    "blocked_conflict",
    "blocked_missing_required_safety_field",
    "human_review_optional",
}

CLAIM_TYPES = {
    "indication",
    "adult dose",
    "peds dose",
    "max dose",
    "frequency",
    "duration",
    "age/weight gate",
    "contraindication",
    "caution",
    "antibiotic criteria",
    "no-antibiotic criteria",
    "red flags",
    "referral",
}

PEDS_REQUIRED_FIELDS = {
    "source_id",
    "source_location",
    "age_weight_gate",
    "dose_basis",
    "max_dose",
    "concentration",
    "route_form",
}

ANTIBIOTIC_REQUIRED_FIELDS = {
    "source_id",
    "source_location",
    "disease_key",
    "bacterial_criteria",
}


def ensure_evidence_dirs() -> None:
    for path in [EVIDENCE_DIR, REPORT_DIR, TEXT_CACHE_DIR, HTML_CACHE_DIR, PDF_CACHE_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def evidence_path(name: str) -> Path:
    return EVIDENCE_DIR / name


def evidence_report_path(name: str) -> Path:
    return REPORT_DIR / name


def slug(value: Any) -> str:
    text = norm_key(value)
    return re.sub(r"[^a-z0-9ก-๙]+", "_", text).strip("_") or "unspecified"


def source_location(claim: dict[str, Any]) -> str:
    return clean(claim.get("source_location") or claim.get("file_reference") or claim.get("url") or claim.get("snippet"))


def has_source_location(claim: dict[str, Any]) -> bool:
    return bool(clean(claim.get("source_id")) and source_location(claim))


def source_authority_map() -> dict[str, int]:
    allowlist = read_json("data/evidence/source_allowlist.json", {"groups": []})
    return {
        clean(group.get("group_id")): int(group.get("authority_level") or 9)
        for group in allowlist.get("groups", [])
    }


def make_gap_task(gap: dict[str, Any], group: dict[str, Any]) -> dict[str, Any]:
    gap_id = clean(gap.get("gap_id")) or stable_id("GAP", gap)
    group_id = clean(group.get("group_id"))
    return {
        "task_id": stable_id("SRC_TASK", f"{gap_id}_{group_id}"),
        "gap_id": gap_id,
        "entity_type": clean(gap.get("entity_type")),
        "entity_id": clean(gap.get("entity_id")),
        "source_group_id": group_id,
        "source_group_name": clean(group.get("name")),
        "authority_level": int(group.get("authority_level") or 9),
        "url": clean(group.get("url")),
        "status": "ready_to_collect" if clean(group.get("url")) else "pending_url_discovery",
        "notes": "No evidence can be verified until an exact URL or local file is registered.",
    }

