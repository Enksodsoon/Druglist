#!/usr/bin/env python3
"""Write the clinical verification master report."""
from __future__ import annotations

import json
from pathlib import Path

from engine_common import now_iso, read_json


def count(path: str, key: str) -> int:
    return len(read_json(path, {key: []}).get(key, []))


def main() -> int:
    seed = read_json("data/core/app_seed_runtime.json", {"dr": [], "cp": [], "m": {}})
    regimens = read_json("data/core/fast_regimen_master.json", {"regimens": []}).get("regimens", [])
    validation = read_json("reports/validation_report.json", {"counts": {}, "warnings": []})
    clinical = read_json("data/meta/clinical_regimen_quality_issues.json", {"issues": []}).get("issues", [])
    antiviral = read_json("data/meta/antiviral_regimen_quality_issues.json", {"issues": []}).get("issues", [])
    peds = read_json("data/pediatric/pediatric_source_gap_priority.json", {"items": []}).get("items", [])
    abx = read_json("data/meta/antibiotic_rdu_quality_issues.json", {"issues": []}).get("issues", [])
    safety = read_json("data/safety/regimen_safety_rules.json", {"items": []}).get("items", [])
    workbook = read_json("data/meta/workbook_quality_issues.json", {"issues": []}).get("issues", [])
    corrections = read_json("data/meta/correction_overlay_applied.json", {"items": []}).get("items", [])
    source_todo = read_json("data/evidence/source_manifest.todo.json", {"items": []}).get("items", [])
    top_blockers = [issue for issue in clinical + antiviral + abx if issue.get("severity") == "blocker"][:20]
    lines = [
        "# Clinical Verification Master Report",
        "",
        f"Generated: {now_iso()}",
        "",
        f"- Product count: {len(seed.get('dr', []))}",
        f"- Complaint count: {len(seed.get('cp', []))}",
        f"- Regimen count: {len(regimens)}",
        f"- Source coverage: {validation.get('counts', {}).get('source_coverage', 0)}",
        f"- Verified source count: {validation.get('counts', {}).get('verified_sources', 0)}",
        f"- Evidence claims: {validation.get('counts', {}).get('evidence_claims', 0)}",
        f"- Auto verified claims: {validation.get('counts', {}).get('evidence_auto_verified', 0)}",
        f"- Source manifest accepted count: {count('data/evidence/source_manifest.json', 'sources')}",
        f"- Acyclovir/antiviral findings: {len(antiviral)}",
        f"- Pediatric source gap findings: {len(peds)}",
        f"- Antibiotic/RDU findings: {len(abx)}",
        f"- Regimen safety findings: {sum(1 for row in safety if row.get('regimen_safety_status') in {'blocked', 'warning'})}",
        f"- Workbook QA findings: {len(workbook)}",
        f"- Correction overlay applied: {len(corrections)}",
        f"- Source manifest TODO count: {len(source_todo)}",
        "",
        "## What Is Safer Now",
        "- Suspicious source-gap antiviral/herpes/zoster rows are audited and correction-gated.",
        "- Pediatric candidates remain visible but calculated dosing remains blocked without source/concentration/age-BW gates.",
        "- Antibiotic/RDU rows are audited for source-backed disease criteria.",
        "- Correction overlays can block or downgrade unsafe runtime rows without fabricating replacement doses.",
        "",
        "## Top 20 Blocker Issues",
    ]
    if top_blockers:
        for issue in top_blockers:
            lines.append(f"- `{issue.get('issue_id')}` {issue.get('disease_key')} {issue.get('product_id')}: {issue.get('recommended_action')}")
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Next Source Files Or URLs Needed",
            "- Acyclovir/herpes zoster/shingles adult treatment guideline with dose/frequency/duration/timing window/red flags.",
            "- Herpes labialis treatment guideline separating topical and oral antiviral use.",
            "- Pediatric paracetamol/ibuprofen/ORS/antihistamine dose sources with age/BW, max dose, frequency, and concentration rules.",
            "- Antibiotic/RDU sources for no-antibiotic viral URI/simple diarrhea defaults and disease-specific bacterial criteria.",
            "- Red-eye, dehydration, dyspnea, petechiae, GI bleed, pregnancy/renal/hepatic red-flag sources.",
        ]
    )
    Path("reports/clinical_verification_master_report.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"clinical_verification_report: blockers={len(top_blockers)} source_todo={len(source_todo)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
