#!/usr/bin/env python3
from gold_common import REPORT_GOLD, ensure_dirs, phase2_candidate_rows, run_phase2_adapters, source_records, write_csv

if __name__ == "__main__":
    ensure_dirs()
    result = run_phase2_adapters(phase2_candidate_rows())
    rows = source_records()
    write_csv(REPORT_GOLD / "accepted_source_metadata.csv", rows)
    print(f"gold accredited sources metadata: {len(rows)} phase2_accepted={result['accepted']}")
