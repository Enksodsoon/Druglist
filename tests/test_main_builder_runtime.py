import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def runtime():
    return json.loads((ROOT / "data/core/app_seed_runtime.json").read_text(encoding="utf-8"))


def all_main_rows():
    for complaint in runtime().get("cp") or []:
        for regimen in complaint.get("r") or []:
            for line in regimen.get("m") or []:
                yield complaint, regimen, line


def test_main_builder_runtime_has_linked_regimen_rows():
    rows = list(all_main_rows())
    linked_complaints = {complaint.get("i") for complaint, _regimen, _line in rows}
    assert len(rows) > 0
    assert len(linked_complaints) > 0


def test_main_builder_rows_include_safe_display_contract_fields():
    rows = [line for _complaint, _regimen, line in all_main_rows()]
    required = {"clinical_readiness", "fast_mode_allowed", "source_status", "evidence_status", "next_action"}
    assert rows
    assert all(required.issubset(line.keys()) for line in rows)
    assert all(line.get("clinical_readiness") != "ready" or line.get("source_status") == "source_verified" for line in rows)


def test_blocked_or_manual_rows_remain_available_for_display():
    rows = [line for _complaint, _regimen, line in all_main_rows()]
    blocked_or_manual = [
        line
        for line in rows
        if line.get("clinical_readiness") in {"blocked", "manual_review_required"}
    ]
    assert blocked_or_manual
    assert all(line.get("fast_mode_allowed") is False for line in blocked_or_manual)
    assert any(line.get("blocked_reason") or line.get("missing_requirements") for line in blocked_or_manual)


def test_acyclovir_zoster_rows_blocked_but_visible_in_runtime():
    hits = []
    for complaint, regimen, line in all_main_rows():
        hay = " ".join(
            str(value)
            for value in [
                complaint.get("c"),
                regimen.get("d"),
                line.get("n"),
                line.get("dg"),
            ]
        ).lower()
        if "zoster" in hay or "shingles" in hay:
            hits.append(line)
    assert hits
    antiviral_hits = [line for line in hits if "acyclovir" in str(line.get("n", "")).lower()]
    assert antiviral_hits
    assert all(line.get("clinical_readiness") == "blocked" for line in antiviral_hits)
    assert all(line.get("fast_mode_allowed") is False for line in antiviral_hits)


def test_frontend_main_builder_preserves_status_rendering_contract():
    source = (ROOT / "index.html").read_text(encoding="utf-8")
    for token in [
        "function mainLineGroupsHtml",
        "function mainLineCard",
        "Blocked / Not for routine prescribing",
        "Manual review required",
        "Status:",
        "No regimen linked for this disease yet",
    ]:
        assert token in source
