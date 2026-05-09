#!/usr/bin/env python3
from gold_common import ensure_dirs, validate_gold

if __name__ == "__main__":
    ensure_dirs()
    raise SystemExit(validate_gold())
