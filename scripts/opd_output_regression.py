#!/usr/bin/env python3
"""Deterministic OPD output regression over exported runtime rows."""

from __future__ import annotations

from medical_refresh_common import read_csv_sheet, write_report

CASES = [
    ("shingles adult", ["zoster", "shingles"], "blocked_or_source_needed"),
    ("herpes labialis", ["herpes", "labialis", "cold sore"], "source_needed"),
    ("allergic rhinitis", ["allergic_rhinitis"], "no_antibiotic"),
    ("URI wet cough", ["uri_wet_cough"], "no_antibiotic"),
    ("sore throat", ["sore", "pharyngitis"], "source_needed"),
    ("acute diarrhea adult", ["diarrhea"], "no_antibiotic"),
    ("dry eye", ["dry_eye"], "no_antibiotic"),
    ("bacterial conjunctivitis", ["bacterial", "conjunctivitis"], "source_needed"),
    ("red eye pain photophobia", ["red_eye", "photophobia", "eye_pain"], "blocked_or_source_needed"),
    ("tinea cruris", ["tinea"], "source_needed"),
    ("UTI symptoms", ["uti", "dysuria"], "source_needed"),
]


def matches(row: dict[str, str], terms: list[str]) -> bool:
    blob = " ".join(str(v).lower() for v in row.values())
    return any(term in blob for term in terms)


def main() -> int:
    rows = read_csv_sheet("2_Regimen_Master_Export")
    failures = []
    result_rows = []
    for name, terms, expectation in CASES:
        found = [row for row in rows if matches(row, terms)]
        if not found:
            failures.append(f"{name}: no matching exported rows")
            result_rows.append((name, 0, "FAIL", "blank output risk"))
            continue
        antibiotic_ready = [
            row for row in found
            if "antibiotic" in " ".join(str(v).lower() for v in row.values())
            and str(row.get("fast_mode_allowed")).lower() == "true"
            and row.get("source_status") != "source_verified"
        ]
        zoster_ready = [
            row for row in found
            if ("zoster" in " ".join(str(v).lower() for v in row.values()) or "shingles" in " ".join(str(v).lower() for v in row.values()))
            and "acyclovir" in " ".join(str(v).lower() for v in row.values())
            and row.get("clinical_readiness") == "ready"
        ]
        if antibiotic_ready:
            failures.append(f"{name}: antibiotic ready without verified source")
        if zoster_ready:
            failures.append(f"{name}: acyclovir/zoster ready without verified source")
        visible_reasons = any(row.get("blocked_reason") or row.get("next_action") or row.get("clinical_readiness") for row in found)
        if not visible_reasons:
            failures.append(f"{name}: no visible reason/status")
        status = "PASS" if not antibiotic_ready and not zoster_ready and visible_reasons else "FAIL"
        result_rows.append((name, len(found), status, expectation))
    lines = [
        f"- Cases: {len(CASES)}",
        f"- Failures: {len(failures)}",
        "",
        "| Case | Matched rows | Status | Expectation |",
        "|---|---:|---|---|",
    ]
    lines.extend(f"| {name} | {count} | {status} | {expectation} |" for name, count, status, expectation in result_rows)
    if failures:
        lines.extend(["", "## Failures", *[f"- {failure}" for failure in failures]])
    write_report("reports/opd_output_regression_report.md", "OPD Output Regression Report", lines)
    print(f"opd_output_regression: failures={len(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
