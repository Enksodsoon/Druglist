import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_regimen_safety_rules_generated():
    payload = load("data/safety/regimen_safety_rules.json")
    assert payload["items"]
    runtime_regimens = load("data/core/fast_regimen_master.json")["regimens"]
    assert payload["meta"]["regimen_count"] == len(runtime_regimens)


def test_duplicate_or_blocked_regimen_safety_findings_exist():
    rows = load("data/safety/regimen_safety_rules.json")["items"]
    assert any(row["regimen_safety_status"] in {"blocked", "warning"} for row in rows)


def test_runtime_seed_exposes_regimen_safety_gate_count():
    seed = load("data/core/app_seed_runtime.json")
    assert "regimen_safety_blocker_count" in seed["m"]
