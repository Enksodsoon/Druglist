#!/usr/bin/env python3
"""Run the full conservative Gold source-acquisition pipeline."""

from __future__ import annotations

from gold_common import run_pipeline


if __name__ == "__main__":
    result = run_pipeline()
    print(
        "gold_pipeline: "
        f"products={result['counts']['products']} "
        f"regimens={result['counts']['regimens']} "
        f"queries={result['query_count']} "
        f"rx_ready={result['rx_counts']['rx_now_ready']} "
        f"bundle={result['bundle']}"
    )
