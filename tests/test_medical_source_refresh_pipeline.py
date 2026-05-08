import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_source_discovery_outputs_tasks_and_candidates():
    tasks = load("data/source_refresh/source_discovery_tasks.json")["tasks"]
    candidates = load("data/source_refresh/source_url_candidates.json")["candidates"]
    assert tasks
    assert candidates
    assert all(candidate["status"] != "accepted" for candidate in candidates)


def test_accepted_sources_require_text_and_identity():
    sources = load("data/source_refresh/source_manifest.accepted.json")["sources"]
    for source in sources:
        assert source["source_id"]
        assert source["source_title"]
        assert source["organization"]
        assert source["source_url"] or source["local_file_reference"]
        assert source["text_extracted"] is True
        assert source["review_status"] == "accepted"


def test_claims_have_snippets_and_do_not_auto_ready_without_required_fields():
    claims = load("data/source_refresh/evidence_claims.json")["claims"]
    for claim in claims:
        assert claim["source_id"]
        assert claim["short_snippet"]
        assert claim["claim_type"]
        assert claim["status"] != "auto_verified" or not claim["missing_required_fields"]


def test_refreshed_workbook_and_citation_exports_exist():
    for path in [
        ROOT / "exports" / "Druglist_Data_Refresh_Master_SOURCE_REFRESHED.xlsx",
        ROOT / "exports" / "Druglist_Source_Citations.xlsx",
        ROOT / "exports" / "source_citations.csv",
    ]:
        assert path.exists()
        assert path.stat().st_size > 0
    with zipfile.ZipFile(ROOT / "exports" / "Druglist_Data_Refresh_Master_SOURCE_REFRESHED.xlsx") as zf:
        workbook_xml = zf.read("xl/workbook.xml").decode("utf-8")
    assert "2_Regimen_Master_Export" in workbook_xml


def test_raw_source_cache_is_not_in_dist():
    dist = ROOT / "dist"
    assert not (dist / "data" / "source_refresh").exists()
    assert not any(dist.rglob("*.pdf")) if dist.exists() else True
