#!/usr/bin/env python3
"""Adapter for user-reviewed local evidence snippets.

Files under imports/accepted_evidence may be CSV or JSON and must contain short,
accepted snippets only. The adapter never treats workbook rows as evidence.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .common import AdapterOutput


ROOT = Path(__file__).resolve().parents[3]
ACCEPTED = ROOT / "imports/accepted_evidence"
REQUIRED = {
    "source_id",
    "source_title",
    "source_org",
    "source_url",
    "source_type",
    "generic_name",
    "disease_key",
    "evidence_field",
    "evidence_value",
    "evidence_snippet",
    "access_date",
    "confidence",
}


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _rows_from_json(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    return payload.get("items") or payload.get("claims") or []


def _rows_from_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _candidate_match(row: dict[str, Any], candidates: list[dict[str, str]]) -> dict[str, str] | None:
    product_id = str(row.get("product_id") or row.get("linked_product_id") or "")
    disease_key = str(row.get("disease_key") or "")
    generic = str(row.get("generic_name") or "").lower()
    for candidate in candidates:
        if product_id and candidate.get("product_id") != product_id:
            continue
        if disease_key and candidate.get("disease_key") != disease_key:
            continue
        blob = (candidate.get("composition", "") + " " + candidate.get("drug_name", "")).lower()
        if generic and generic not in blob:
            continue
        return candidate
    return None


def run(candidate_rows: list[dict[str, str]]) -> AdapterOutput:
    out = AdapterOutput()
    ACCEPTED.mkdir(parents=True, exist_ok=True)
    files = sorted([*ACCEPTED.glob("*.csv"), *ACCEPTED.glob("*.json")])
    if not files:
        out.search_tasks.append({"adapter": "local_evidence_cache", "status": "no_accepted_evidence_files", "path": str(ACCEPTED.relative_to(ROOT))})
        return out

    seen_sources: set[str] = set()
    for path in files:
        try:
            rows = _rows_from_csv(path) if path.suffix.lower() == ".csv" else _rows_from_json(path)
        except Exception as exc:
            out.rejected_sources.append({"adapter": "local_evidence_cache", "file": str(path), "status": "unreadable", "reason": str(exc)})
            continue
        for row in rows:
            missing = [key for key in REQUIRED if not row.get(key)]
            match = _candidate_match(row, candidate_rows)
            if missing or not match:
                out.rejected_sources.append(
                    {
                        "adapter": "local_evidence_cache",
                        "file": _display_path(path),
                        "status": "rejected_missing_required_or_no_row_match",
                        "missing": "; ".join(missing),
                        "source_id": row.get("source_id", ""),
                    }
                )
                continue
            source_id = str(row["source_id"])
            if source_id not in seen_sources:
                seen_sources.add(source_id)
                out.accepted_sources.append(
                    {
                        "source_id": source_id,
                        "source_title": row["source_title"],
                        "source_org": row["source_org"],
                        "source_url": row["source_url"],
                        "access_date": row["access_date"],
                        "source_type": row["source_type"],
                        "source_country_or_region": row.get("source_country_or_region") or row.get("country") or "",
                        "adapter_name": "local_evidence_cache_adapter",
                        "retrieval_status": "accepted_local_cache",
                        "extraction_status": "field_snippet_provided",
                    }
                )
            out.evidence_claims.append(
                {
                    "claim_id": row.get("claim_id") or f"claim_{source_id}_{match.get('product_id')}_{match.get('disease_key')}_{row['evidence_field']}",
                    "source_id": source_id,
                    "source_title": row["source_title"],
                    "source_org": row["source_org"],
                    "source_url": row["source_url"],
                    "source_type": row["source_type"],
                    "source_country_or_region": row.get("source_country_or_region") or row.get("country") or "",
                    "evidence_field": row["evidence_field"],
                    "evidence_value": row["evidence_value"],
                    "evidence_snippet": row["evidence_snippet"][:700],
                    "confidence": row["confidence"],
                    "linked_product_id": match.get("product_id", ""),
                    "linked_regimen_id": match.get("regimen_id", ""),
                    "linked_disease_key": match.get("disease_key", ""),
                    "linked_generic_name": row["generic_name"],
                    "adapter_name": "local_evidence_cache_adapter",
                    "product_match_status": "local_cache_row_match",
                }
            )
    return out
