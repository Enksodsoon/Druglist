#!/usr/bin/env python3
from .common import AdapterOutput


def run(candidate_rows):
    return AdapterOutput(search_tasks=[{"adapter": "nice_bnf_query", "status": "query_manifest_only", "reason": "BNF access may require manual/licensed review"}])
