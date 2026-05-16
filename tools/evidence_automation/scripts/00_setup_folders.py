#!/usr/bin/env python3
from pathlib import Path

ROOTS = [
    "imports/accepted_evidence/bulk",
    "imports/accepted_evidence/disease",
    "imports/accepted_evidence/drug",
    "imports/accepted_evidence/product",
    "imports/accepted_evidence/manifest",
    "reports/evidence_acquisition",
    "batches/evidence_extraction/batch_001",
]

for root in ROOTS:
    Path(root).mkdir(parents=True, exist_ok=True)

print("Created evidence folders:")
for root in ROOTS:
    print(f"- {root}")
