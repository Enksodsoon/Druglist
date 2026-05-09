#!/usr/bin/env python3
from gold_common import REPORT_GOLD, build_gold_tables, ensure_dirs, gap_reports

if __name__ == "__main__":
    ensure_dirs()
    build_gold_tables()
    gap_reports()
    print(f"gold conflict report: {REPORT_GOLD / 'conflict_report.csv'}")
