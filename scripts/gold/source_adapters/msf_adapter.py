#!/usr/bin/env python3
from .common import AdapterOutput


def run(candidate_rows):
    return AdapterOutput(search_tasks=[{"adapter": "msf", "status": "query_manifest_only", "reason": "Phase 2 does not scrape MSF pages automatically"}])
