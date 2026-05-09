#!/usr/bin/env python3
from gold_common import REPORT_GOLD, ensure_dirs, evidence_claims, write_csv

if __name__ == "__main__":
    ensure_dirs()
    rows = []
    for claim in evidence_claims():
        score = float(claim.get("confidence") or 0)
        rows.append({**claim, "quality_score": score, "quality_band": "high" if score >= 0.85 else "review"})
    write_csv(REPORT_GOLD / "source_quality_scores.csv", rows)
    print(f"gold source quality scores: {len(rows)}")
