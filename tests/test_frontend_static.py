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
        "Clinical audit gates",
        "antiviral issues",
        "pediatric source gaps",
        "Antibiotic/RDU issues",
        "Correction overlay applied",
        "source manifest TODO",
        "Drug SWAPS",
    ]:
        assert text in source


def test_frontend_has_device_responsive_guardrails():
    source = html()
    for token in [
        "@media (max-width:1180px)",
        "@media (max-width:720px)",
        "@media (max-width:420px)",
        "grid-auto-flow:column",
        "height:min(92vh,760px)",
        "font-size:16px",
        ".layout-main.main-shell",
        "Compact workstation scaling",
        "transform:scale(.5)",
        ".layout-peds{grid-template-columns:minmax(0,1.12fr) 286px 286px!important",
        ".peds-hero-grid{grid-template-columns:minmax(340px,1.2fr) 290px!important",
        ".rule-studio{grid-template-columns:minmax(0,1fr) 328px!important",
    ]:
        assert token in source


def test_main_builder_swap_action_contract_is_present():
    source = html()
    assert "data-mswap" in source
    assert "activateMainSwap" in source
    assert "mainSwapPanelHtml" in source
    assert "data-testid=\"main-swap-panel\"" in source
    assert "mainClassifySwaps" in source
    assert "isTherapeuticSwapLine" in source
    assert "same_generic_brand_alternative" in source
    assert "same active ingredient" in source
    assert "not a therapeutic Drug SWAP" in source


def test_retain_design_behavior_fixes_are_present():
    source = html()
    for token in [
        "retainDesignSaveMainDraft",
        "retainDesignPreviewMain",
        "retainDesignIngredientKeys",
        "retainDesignQuickCurrentDrugs",
        "retainDesignDashboardReport",
        "retainDesignSmartAddsOriginal",
        "retainDesignRenderDashboardOriginal",
        "querySelector('.dashboard-rail')",
        "rail.remove()",
    ]:
        assert token in source


def test_topbar_global_search_removed_but_dashboard_search_remains():
    source = html()
    assert 'id="globalSearch"' not in source
    assert "dashboardCommandSearch" in source
    assert "$('globalSearch')" in source  # optional legacy sync path stays null-safe


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
