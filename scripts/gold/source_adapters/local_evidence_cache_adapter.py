#!/usr/bin/env python3
"""Adapter that exposes existing source-refresh claims to the Gold pipeline."""

from __future__ import annotations

from .common import AdapterOutput


def run(candidate_rows: list[dict[str, str]]) -> AdapterOutput:
    out = AdapterOutput()
    out.search_tasks.append({"adapter": "local_evidence_cache", "status": "existing_source_refresh_claims_loaded_by_gold_common"})
    return out
