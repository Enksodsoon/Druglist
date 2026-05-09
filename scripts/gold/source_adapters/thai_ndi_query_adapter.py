#!/usr/bin/env python3
from .common import AdapterOutput


def run(candidate_rows):
    return AdapterOutput(search_tasks=[{"adapter": "thai_ndi_query", "status": "query_manifest_only", "reason": "Thai NDI/NLEM tasks generated without automatic acceptance"}])
