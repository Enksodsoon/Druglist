#!/usr/bin/env python3
from gold_common import REPORT_GOLD, ensure_dirs, evidence_claims, write_csv

if __name__ == "__main__":
    ensure_dirs()
    rows = evidence_claims()
    write_csv(REPORT_GOLD / "evidence_extraction_report.csv", rows)
    print(f"gold evidence fields: {len(rows)}")
