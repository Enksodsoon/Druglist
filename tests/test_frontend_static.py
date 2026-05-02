from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_frontend_sections_and_runtime_loader():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    for section in ["main", "peds", "catalog", "compare", "validation", "inventory", "admin", "rules"]:
        assert f'id="section-{section}"' in html
    assert "loadRuntimeSeed" in html
    assert "data/core/app_seed_runtime.json" in html
    assert "renderAdminRuntimeMeta" in html


def test_rules_tab_visible_once_tabs_rendered():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert "data-tab=\"rules\"" in html
    assert html.count("function tabs(") == 1
