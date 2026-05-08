#!/usr/bin/env python3
"""Inspect Main Builder complaint-to-regimen data without dumping runtime JSON."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "data/core/app_seed_runtime.json"
FAST_MASTER = ROOT / "data/core/fast_regimen_master.json"
OPD_INDEX = ROOT / "data/core/opd_fast_index.json"
AUDIT = ROOT / "data/meta/clinical_regimen_quality_issues.json"
CORRECTIONS = ROOT / "data/overrides/regimen_corrections.json"
REPORT = ROOT / "reports/main_builder_data_debug_report.md"


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def regimen_lines(complaints: list[dict]):
    for complaint in complaints:
        for regimen in complaint.get("r") or []:
            for line in regimen.get("m") or []:
                yield complaint, regimen, line


def label_complaint(item: tuple[dict, dict, dict] | None) -> str:
    if not item:
        return "none"
    complaint, regimen, line = item
    return (
        f"{complaint.get('i')} | {complaint.get('c')} | {regimen.get('i')} "
        f"| {regimen.get('d')} | {line.get('n') or line.get('i')}"
    )


def main() -> int:
    runtime = load_json(RUNTIME, {})
    complaints = runtime.get("cp") or []
    fast_master = load_json(FAST_MASTER, {})
    opd_index = load_json(OPD_INDEX, {})
    audit = load_json(AUDIT, [])
    corrections = load_json(CORRECTIONS, [])

    rows = list(regimen_lines(complaints))
    readiness = Counter((line.get("clinical_readiness") or "missing") for _, _, line in rows)
    source = Counter((line.get("source_status") or "missing") for _, _, line in rows)
    evidence = Counter((line.get("evidence_status") or "missing") for _, _, line in rows)
    linked_complaints = {
        complaint.get("i")
        for complaint, regimen, _line in rows
        if complaint.get("i") and regimen.get("i")
    }
    disease_keys = {
        str(regimen.get("i") or regimen.get("d") or "").strip()
        for complaint in complaints
        for regimen in (complaint.get("r") or [])
        if regimen.get("i") or regimen.get("d")
    }
    rows_by_complaint = defaultdict(list)
    for complaint, regimen, line in rows:
        rows_by_complaint[complaint.get("i")].append((complaint, regimen, line))

    with_rows = next((items[0] for items in rows_by_complaint.values() if items), None)
    only_blocked_manual = next(
        (
            items[0]
            for items in rows_by_complaint.values()
            if items
            and all(
                (line.get("clinical_readiness") or "manual_review_required")
                in {"blocked", "manual_review_required"}
                for _, _, line in items
            )
        ),
        None,
    )
    no_rows = next(
        (
            complaint
            for complaint in complaints
            if not any((regimen.get("m") or []) for regimen in (complaint.get("r") or []))
        ),
        None,
    )

    report = [
        "# Main Builder Data Debug Report",
        "",
        f"- Runtime path: `{RUNTIME.relative_to(ROOT)}`",
        f"- Complaint count: {len(complaints)}",
        f"- Disease/regimen key count: {len(disease_keys)}",
        f"- Runtime regimen rows: {len(rows)}",
        f"- Complaints linked to regimen rows: {len(linked_complaints)}",
        f"- Rows hidden by `fast_mode_allowed=false`: {sum(1 for _, _, line in rows if line.get('fast_mode_allowed') is False)}",
        f"- Fast regimen master rows: {len(fast_master.get('regimens', [])) if isinstance(fast_master, dict) else len(fast_master) if isinstance(fast_master, list) else 'unknown'}",
        f"- OPD fast index entries: {len(opd_index) if isinstance(opd_index, dict) else 'unknown'}",
        f"- Clinical audit issues: {len(audit.get('issues', [])) if isinstance(audit, dict) else len(audit) if isinstance(audit, list) else 'unknown'}",
        f"- Regimen corrections configured: {len(corrections.get('corrections', [])) if isinstance(corrections, dict) else len(corrections) if isinstance(corrections, list) else 'unknown'}",
        "",
        "## Readiness",
        "",
        *[f"- {key}: {value}" for key, value in sorted(readiness.items())],
        "",
        "## Source Status",
        "",
        *[f"- {key}: {value}" for key, value in sorted(source.items())],
        "",
        "## Evidence Status",
        "",
        *[f"- {key}: {value}" for key, value in sorted(evidence.items())],
        "",
        "## Samples",
        "",
        f"- Linked rows sample: {label_complaint(with_rows)}",
        f"- Only blocked/manual rows sample: {label_complaint(only_blocked_manual)}",
        f"- No linked regimen sample: {no_rows.get('i') if no_rows else 'none'} | {no_rows.get('c') if no_rows else ''}",
        "",
        "## Frontend Contract Fields",
        "",
        "- complaint: `i`, `c`, `r`",
        "- regimen: `i`, `d`, `m`, `y`, `w`",
        "- row: `i`, `n`, `t`, `o`, `u`, `p`, `clinical_readiness`, `fast_mode_allowed`, `source_status`, `evidence_status`, `blocked_reason`, `missing_requirements`, `next_action`",
    ]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"main_builder_data_debug: rows={len(rows)} linked_complaints={len(linked_complaints)}")
    print(f"report: {REPORT.relative_to(ROOT)}")
    return 0 if rows and linked_complaints else 1


if __name__ == "__main__":
    raise SystemExit(main())
