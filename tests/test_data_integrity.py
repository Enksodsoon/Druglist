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
