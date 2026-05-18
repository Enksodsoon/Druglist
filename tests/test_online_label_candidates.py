import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    path = ROOT / "scripts" / "collect_online_label_candidates.py"
    spec = importlib.util.spec_from_file_location("collect_online_label_candidates", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


SAMPLE_OTC_XML = b"""<?xml version="1.0"?>
<document xmlns="urn:hl7-org:v3">
  <component><structuredBody>
    <component><section>
      <code displayName="INDICATIONS &amp; USAGE SECTION"/>
      <text>Uses temporarily reduces fever and relieves minor aches.</text>
    </section></component>
    <component><section>
      <code displayName="WARNINGS SECTION"/>
      <text>Warnings ask a doctor before use if liver disease is present.</text>
    </section></component>
    <component><section>
      <code displayName="DOSAGE &amp; ADMINISTRATION SECTION"/>
      <text>Directions children 2 to 3 years: 5 mL every 4 hours. Do not give more than 5 doses in 24 hours.</text>
    </section></component>
  </structuredBody></component>
</document>
"""


def test_extract_label_sections_keeps_dosing_warnings_and_indications():
    module = load_module()
    sections = module.extract_label_sections(SAMPLE_OTC_XML)
    assert "temporarily reduces fever" in sections["indications"]
    assert "liver disease" in sections["warnings"]
    assert "children 2 to 3 years" in sections["dosage"]


def test_candidate_never_unlocks_fast_mode_for_online_label():
    module = load_module()
    sections = module.extract_label_sections(SAMPLE_OTC_XML)
    candidate = module.build_candidate(
        {
            "id": "BDS001665",
            "display_name": "Duran Suspension [Ibuprofen 100 mg./5 ml.]",
            "generic_key": "ibuprofen",
            "route": "oral",
            "form": "suspension",
            "category": "analgesic_antipyretic",
            "flags": {},
        },
        {"setid": "abc", "title": "IBUPROFEN SUSPENSION", "spl_version": 1, "published_date": "May 01, 2026"},
        sections,
        pediatric_target=True,
    )
    assert candidate["candidate_status"] == "source_matched_candidate"
    assert candidate["fast_mode_allowed"] is False
    assert candidate["manual_review_required"] is True
    assert candidate["pediatric_target"] is True
    assert candidate["source"]["url"].endswith("setid=abc")


def test_pediatric_candidate_blocks_when_age_or_weight_bounds_missing():
    module = load_module()
    status, missing = module.candidate_status(
        {"flags": {}},
        {"dosage": "Adults take one tablet daily.", "warnings": "Warnings.", "indications": "Uses."},
        pediatric_target=True,
    )
    assert status == "blocked_missing_required_safety_field"
    assert "pediatric_age_or_weight_bounds" in missing


def test_antibiotic_candidate_remains_gate_controlled():
    module = load_module()
    status, missing = module.candidate_status(
        {"flags": {"antibiotic": True}},
        {"dosage": "Directions.", "warnings": "Warnings.", "indications": "Uses."},
        pediatric_target=False,
    )
    assert status == "blocked_missing_required_safety_field"
    assert "antibiotic_gate_required" in missing
