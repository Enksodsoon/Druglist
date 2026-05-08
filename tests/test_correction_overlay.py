import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_correction_overlay_blocks_but_does_not_fabricate_verified_dose():
    applied = load("data/meta/correction_overlay_applied.json")["items"]
    assert len(applied) >= 2
    regimens = {r["regimen_id"]: r for r in load("data/core/fast_regimen_master.json")["regimens"]}
    assert regimens["FRM0027"]["clinical_readiness"] == "blocked"
    for line in regimens["FRM0027"]["lines"]:
        assert line["source_status"] == "pending_manual_review"
        assert line["evidence_status"] == "blocked_missing_required_safety_field"
        assert not line.get("source_ids")


def test_correction_overlay_policy_visible():
    text = (ROOT / "docs" / "override_policy.md").read_text(encoding="utf-8")
    assert "must not create verified doses" in text
