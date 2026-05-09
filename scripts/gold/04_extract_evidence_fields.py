#!/usr/bin/env python3
from gold_common import REPORT_GOLD, ensure_dirs, evidence_claims, phase2_candidate_rows, run_phase2_adapters, write_csv

if __name__ == "__main__":
    ensure_dirs()
    run_phase2_adapters(phase2_candidate_rows())
    rows = evidence_claims()
    write_csv(REPORT_GOLD / "evidence_extraction_report.csv", rows)
    print(f"gold evidence fields: {len(rows)}")
