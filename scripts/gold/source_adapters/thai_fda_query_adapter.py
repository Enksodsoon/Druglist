#!/usr/bin/env python3
from .common import AdapterOutput


def run(candidate_rows):
    return AdapterOutput(search_tasks=[{"adapter": "thai_fda_query", "status": "query_manifest_only", "reason": "Thai FDA product verification needs targeted/manual accession in this phase"}])
