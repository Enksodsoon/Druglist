#!/usr/bin/env python3
from gold_common import ensure_dirs, source_records, write_csv, REPORT_GOLD

if __name__ == "__main__":
    ensure_dirs()
    rows = source_records()
    write_csv(REPORT_GOLD / "accepted_source_metadata.csv", rows)
    print(f"gold accredited sources metadata: {len(rows)}")
