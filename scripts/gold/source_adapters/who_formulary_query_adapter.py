#!/usr/bin/env python3
from .common import AdapterOutput


def run(candidate_rows):
    return AdapterOutput(search_tasks=[{"adapter": "who_formulary_query", "status": "query_manifest_only", "reason": "WHO formulary tasks generated; no row unlocked without exact snippets"}])
