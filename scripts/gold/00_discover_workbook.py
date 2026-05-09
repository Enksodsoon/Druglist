#!/usr/bin/env python3
from gold_common import discover_workbook, ensure_dirs

if __name__ == "__main__":
    ensure_dirs()
    print(discover_workbook())
