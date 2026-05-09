#!/usr/bin/env python3
"""Select high-priority Phase 2 Gold candidates from defaults/common OPD rows."""

from __future__ import annotations

from gold_common import phase2_candidate_rows


if __name__ == "__main__":
    rows = phase2_candidate_rows()
    print(f"phase2_candidates: {len(rows)}")
