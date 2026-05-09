#!/usr/bin/env python3
from gold_common import build_queries, ensure_dirs

if __name__ == "__main__":
    ensure_dirs()
    rows = build_queries()
    print(f"gold source queries: {len(rows)}")
