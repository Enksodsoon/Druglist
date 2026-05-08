import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def load_evidence_score_module():
    path = ROOT / "scripts" / "evidence_score.py"
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("evidence_score", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def load_evidence_common_module():
    path = ROOT / "scripts" / "evidence_common.py"
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("evidence_common_for_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_evidence_pipeline_without_source_cache_creates_pending_tasks():
    tasks = load("data/evidence/source_search_tasks.json")
    summary = load("data/evidence/evidence_runtime_summary.json")
    assert tasks["meta"]["task_count"] > 0
    assert tasks["meta"]["pending_url_discovery_count"] > 0
    assert summary["evidence_status"] == "pending_source_collection"
    assert summary["auto_verified_claim_count"] == 0


def test_source_manifest_schema_validation_blocks_unsafe_review_statuses():
    module = load_evidence_common_module()
    errors = module.validate_source_manifest(
        {
            "sources": [
                {
                    "source_id": "SRC_BAD",
                    "title": "",
                    "organization": "",
                    "year": "",
                    "version": "",
                    "url_or_file": "",
                    "source_type": "guideline",
                    "access_status": "missing",
                    "review_status": "accepted",
                    "reviewer": "",
                }
            ]
        }
    )
    assert "source_manifest_reviewed_without_reviewer:SRC_BAD" in errors
    assert "source_manifest_accepted_missing_title:SRC_BAD" in errors
    assert "source_manifest_accepted_missing_organization:SRC_BAD" in errors
    assert "source_manifest_accepted_missing_url_or_file:SRC_BAD" in errors
    assert "source_manifest_accepted_missing_year_or_version:SRC_BAD" in errors


def test_no_claim_auto_verified_without_source_identity_and_location():
    claims = load("data/evidence/evidence_scores.json")["claims"]
    for claim in claims:
        if claim["evidence_status"] == "auto_verified":
            assert claim.get("source_id")
            assert claim.get("source_location") or claim.get("file_reference") or claim.get("url") or claim.get("snippet")


def test_scoring_blocks_claim_missing_source_location():
    module = load_evidence_score_module()
    scored = module.score_claim(
        {
            "claim_id": "CLAIM_NO_SOURCE",
            "claim_type": "indication",
            "claim_text": "Unsourced claim must not verify.",
            "source_id": "",
            "source_location": "",
            "structured_fields": {},
        }
    )
    assert scored["evidence_status"] == "blocked_missing_required_safety_field"
    assert "source_id" in scored["evidence_required_fields_missing"]
    assert "source_location" in scored["evidence_required_fields_missing"]


def test_cannot_auto_verify_without_accepted_manifest_source():
    module = load_evidence_score_module()
    scored = module.score_claim(
        {
            "claim_id": "CLAIM_UNREVIEWED_SOURCE",
            "claim_type": "indication",
            "claim_text": "A sourced but unaccepted claim must not verify.",
            "source_id": "thai_pediatric_society",
            "source_location": "source_cache/text/example.txt",
            "section": "Dosing",
            "structured_fields": {},
            "extraction_quality": "manual_reviewed",
        }
    )
    assert scored["evidence_status"] == "blocked_missing_required_safety_field"
    assert "accepted_source_review" in scored["evidence_required_fields_missing"]


def test_peds_verified_requires_complete_safety_fields():
    module = load_evidence_score_module()
    scored = module.score_claim(
        {
            "claim_id": "CLAIM_PEDS_INCOMPLETE",
            "claim_type": "peds dose",
            "claim_text": "Pediatric dose text without all structured safety gates.",
            "source_id": "thai_pediatric_society",
            "source_location": "source_cache/text/example.txt",
            "structured_fields": {"dose_basis": "mg/kg"},
        }
    )
    assert scored["evidence_status"] == "blocked_missing_required_safety_field"
    for field in ["age_weight_gate", "max_dose", "concentration", "route_form"]:
        assert field in scored["evidence_required_fields_missing"]


def test_antibiotic_verified_requires_source_backed_bacterial_rule():
    module = load_evidence_score_module()
    scored = module.score_claim(
        {
            "claim_id": "CLAIM_ABX_INCOMPLETE",
            "claim_type": "antibiotic criteria",
            "claim_text": "Antibiotic text without disease-specific bacterial criteria.",
            "source_id": "international_guidelines",
            "source_location": "source_cache/text/example.txt",
            "structured_fields": {},
        }
    )
    assert scored["evidence_status"] == "blocked_missing_required_safety_field"
    assert "disease_key" in scored["evidence_required_fields_missing"]
    assert "bacterial_criteria" in scored["evidence_required_fields_missing"]


def test_low_confidence_and_conflict_counts_remain_blocking():
    summary = load("data/evidence/evidence_runtime_summary.json")
    assert summary["blocked_conflict_count"] == 0
    assert summary["blocked_low_confidence_count"] >= 0
    assert summary["auto_resolved_gap_count"] == 0
    queue = load("data/evidence/manual_review_queue.json")
    assert queue["meta"]["pending_gap_count"] >= 36
    assert all(item["status"] == "pending_source_collection" for item in queue["items"])


def test_accepted_source_resolution_still_requires_traceable_location(monkeypatch):
    module = load_evidence_score_module()
    monkeypatch.setattr(module, "source_is_accepted", lambda source_id: source_id == "SRC_ACCEPTED")
    monkeypatch.setattr(module, "source_authority_map", lambda: {"SRC_ACCEPTED": 1})
    unresolved_claim = {
        "claim_id": "CLAIM_NO_TRACE",
        "claim_type": "indication",
        "claim_text": "Accepted source without traceable section/page/location.",
        "source_id": "SRC_ACCEPTED",
        "source_location": "",
        "file_reference": "",
        "url": "",
        "snippet": "",
        "structured_fields": {},
        "extraction_quality": "manual_reviewed",
    }
    scored = module.score_claim(unresolved_claim)
    assert scored["evidence_status"] == "blocked_missing_required_safety_field"
    assert "source_location" in scored["evidence_required_fields_missing"]
    reviewed_claim = {
        **unresolved_claim,
        "claim_id": "CLAIM_TRACEABLE",
        "source_location": "source_cache/text/source.txt",
        "section": "Treatment",
        "generic_name": "example",
        "disease_key": "example",
    }
    scored_reviewed = module.score_claim(reviewed_claim)
    assert scored_reviewed["evidence_status"] == "auto_verified"
    assert scored_reviewed["evidence_required_fields_missing"] == []


def test_runtime_seed_contains_evidence_status_fields():
    seed = load("data/core/app_seed_runtime.json")
    assert seed["m"]["evidence_status"] == "pending_source_collection"
    assert "evidence_auto_verified_count" in seed["m"]
    assert seed["dr"]
    first = seed["dr"][0]
    for field in [
        "evidence_status",
        "evidence_score",
        "evidence_confidence",
        "evidence_source_ids",
        "evidence_required_fields_missing",
        "auto_resolution_status",
    ]:
        assert field in first
