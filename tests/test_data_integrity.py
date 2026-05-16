import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_product_layer_has_unique_ids_and_display_format():
    products = load("data/core/drug_master_rebuilt.json")["products"]
    ids = [p["id"] for p in products]
    assert len(products) == 910
    assert len(ids) == len(set(ids))
    assert all("[" in p["display_name"] and p["display_name"].endswith("]") for p in products if p["composition"])


def test_manual_review_queue_matches_flagged_products():
    products = load("data/core/drug_master_rebuilt.json")["products"]
    queue = load("data/meta/manual_review_queue.json")["items"]
    flagged = [p for p in products if p["manual_review"]["required"]]
    assert len(queue) == len(flagged)


def test_source_registry_is_pending_not_fabricated():
    sources = load("data/guidelines/source_registry.json")["sources"]
    assert sources
    assert all(source["access_status"] == "pending_access" for source in sources)
    assert all(source["manual_review"] for source in sources)


def test_frontend_seed_exposes_review_workflow_counts():
    seed_meta = load("data/core/app_seed_runtime.json")["m"]
    queue = load("data/meta/manual_review_queue.json")["items"]
    gaps = load("data/guidelines/source_gap_list.json")["items"]
    peds = load("data/pediatric/peds_product_dose_output.json")["items"]
    patch_manual = load("data/meta/guideline_patch_manual_review_queue.json")["items"]
    patch_peds = load("data/pediatric/imported_guideline_peds_shortcuts.json")["items"]
    assert seed_meta["manual_review_product_count"] == len(queue)
    assert seed_meta["source_gap_count"] == len(gaps)
    assert seed_meta["pediatric_review_count"] == len(peds)
    assert seed_meta["guideline_patch_manual_review_count"] == len(patch_manual)
    assert seed_meta["guideline_patch_pediatric_shortcut_count"] == len(patch_peds)
    assert seed_meta["manual_review_count"] == len(queue) + len(gaps) + len(peds) + len(patch_manual) + len(patch_peds)
    assert seed_meta["manual_review_reason_counts"]
