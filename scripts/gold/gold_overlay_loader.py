#!/usr/bin/env python3
"""Feature-flagged gold overlay loader used by tests and future app wiring."""

from __future__ import annotations

from gold_common import load_runtime_with_gold_overlay


if __name__ == "__main__":
    loaded = load_runtime_with_gold_overlay()
    print(loaded["engine"])
