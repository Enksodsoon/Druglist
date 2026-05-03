from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def html():
    return (ROOT / "index.html").read_text(encoding="utf-8")


def test_index_html_is_non_empty():
    assert (ROOT / "index.html").stat().st_size > 100_000


def test_frontend_sections_and_runtime_loader():
    source = html()
    for section in ["main", "peds", "catalog", "compare", "validation", "inventory", "admin", "rules"]:
        assert f'id="section-{section}"' in source
    assert "loadRuntimeSeed" in source
    assert "data/core/app_seed_runtime.json" in source
    assert "renderAdminRuntimeMeta" in source
    assert "reviewWorkflowStats" in source
    assert "Manual-review products" in source
    assert "Source Coverage Gate" in source


def test_rules_tab_visible_once_tabs_rendered():
    source = html()
    assert "data-tab=\"rules\"" in source
    assert source.count("function tabs(") == 1


def test_required_dom_contract_ids_exist():
    source = html()
    required_ids = [
        "tabs",
        "profileSelect",
        "mainSearch",
        "mainComplaints",
        "mainSelected",
        "mainBuilder",
        "pedsSearch",
        "pedsAge",
        "pedsWeight",
        "pedsTemplates",
        "pedsLibrary",
        "pedsBuilder",
        "catalogSearch",
        "catalogPanel",
        "compareSearch",
        "comparePanel",
        "validationPanel",
        "inventorySearch",
        "inventoryPanel",
        "adminSearch",
        "adminPanel",
        "drawer",
        "drawerTitle",
        "drawerSubtitle",
        "drawerBody",
        "closeDrawer",
        "newRecordAction",
        "pedsAgeMirror",
        "pedsWeightMirror",
    ]
    for element_id in required_ids:
        assert f'id="{element_id}"' in source


def test_safety_review_strings_remain_visible_in_frontend():
    source = html()
    for text in [
        "Source coverage",
        "source gap",
        "Manual-review products",
        "manual review",
        "Review reasons",
        "Next review action",
        "Pediatric auto-dose",
        "Evidence automation status",
        "Auto-verified evidence",
        "Evidence status",
    ]:
        assert text in source


def test_pediatric_mirror_controls_are_wired_bidirectionally():
    source = html()
    assert "pedsAgeMirror" in source
    assert "pedsWeightMirror" in source
    assert "$('pedsAge')) $('pedsAge').value=e.target.value" in source
    assert "$('pedsWeight')) $('pedsWeight').value=e.target.value" in source


def test_dist_deploy_entry_is_non_empty_when_present():
    dist_index = ROOT / "dist" / "index.html"
    if dist_index.exists():
        assert dist_index.stat().st_size > 100_000
