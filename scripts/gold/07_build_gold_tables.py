#!/usr/bin/env python3
from gold_common import build_gold_tables, ensure_dirs

if __name__ == "__main__":
    ensure_dirs()
    print(build_gold_tables())
