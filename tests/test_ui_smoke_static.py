from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_ui_smoke_does_not_hide_functional_failures_behind_browser_deps():
    source = (ROOT / "scripts" / "ui_smoke_test.py").read_text(encoding="utf-8")
    assert "functional_failures = []" in source
    assert "functional_failures.append" in source
    assert "if functional_failures:" in source
    assert "SKIP due to environment/browser dependencies" in source


def test_ui_smoke_waits_for_dynamic_rule_checkpoint_controls():
    source = (ROOT / "scripts" / "ui_smoke_test.py").read_text(encoding="utf-8")
    assert "page.wait_for_selector('[data-rchkdiff]'" in source
    assert "page.wait_for_selector('[data-rchkrestore]'" in source
