#!/usr/bin/env python3
from .common import AdapterOutput


def run(candidate_rows):
    return AdapterOutput(search_tasks=[{"adapter": "nice_guideline", "status": "query_manifest_only", "reason": "NICE snippets are consumed from existing source-refresh claims where exact"}])
