#!/usr/bin/env python3
from gold_common import discover_workbook, ensure_dirs, repo_mapping, workbook_extraction_report

if __name__ == "__main__":
    ensure_dirs()
    selected = discover_workbook()
    repo_mapping()
    workbook_extraction_report(selected)
    print("gold extraction reports written")
