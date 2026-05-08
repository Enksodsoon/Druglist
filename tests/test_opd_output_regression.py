import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def runtime_rows():
    data = json.loads((ROOT / "data/core/app_seed_runtime.json").read_text(encoding="utf-8"))
    return [
        (complaint, regimen, line)
        for complaint in data.get("cp", [])
        for regimen in complaint.get("r", [])
        for line in regimen.get("m", [])
    ]


def test_opd_runtime_never_blank_for_common_exported_regimens():
    rows = runtime_rows()
    assert rows
    assert any("allergic" in complaint.get("c", "") for complaint, _regimen, _line in rows)
    assert any("diarrhea" in complaint.get("c", "") for complaint, _regimen, _line in rows)


def test_acyclovir_zoster_not_ready_without_source():
    hits = []
    for complaint, regimen, line in runtime_rows():
        disease_blob = " ".join(str(v).lower() for v in [complaint, regimen])
        line_blob = " ".join(str(v).lower() for v in [line.get("n"), line.get("dg"), line.get("i")])
        if "acyclovir" in line_blob and ("zoster" in disease_blob or "shingles" in disease_blob):
            hits.append(line)
    assert hits
    assert all(line.get("clinical_readiness") != "ready" for line in hits)
    assert all(line.get("fast_mode_allowed") is False for line in hits)


def test_no_source_gap_row_marked_ready():
    for _complaint, _regimen, line in runtime_rows():
        if line.get("source_status") != "source_verified":
            assert line.get("clinical_readiness") != "ready"


def test_pediatric_runtime_dose_gates_still_block_auto_calculation():
    peds = json.loads((ROOT / "data/pediatric/peds_product_dose_output.json").read_text(encoding="utf-8"))
    assert peds.get("items")
    assert all(not item.get("auto_dose_enabled") for item in peds["items"] if not item.get("source_ids"))
