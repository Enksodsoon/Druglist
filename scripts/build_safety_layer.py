#!/usr/bin/env python3
"""Build safety, RDU, antibiotic stewardship, and red-flag frameworks."""
from __future__ import annotations

from engine_common import ensure_dirs, now_iso, write_json


def rule(rule_id: str, title: str, category: str, triggers: list[str], message: str, active: bool = False) -> dict[str, object]:
    return {
        "rule_id": rule_id,
        "title": title,
        "category": category,
        "triggers": triggers,
        "message": message,
        "severity": "review",
        "active": active,
        "source_ids": [],
        "source_status": "missing_verified_source",
        "manual_review": True,
    }


def build() -> dict[str, int]:
    ensure_dirs("data/safety")
    generated_at = now_iso()

    validation_rules = {
        "meta": {"generated_at": generated_at, "manual_review": True},
        "rules": [
            rule("DUP_PARACETAMOL", "Duplicate paracetamol ingredient warning", "duplicate_ingredient", ["paracetamol", "acetaminophen"], "Review duplicate paracetamol exposure before dispensing.", True),
            rule("DUP_NSAID", "Duplicate NSAID warning", "duplicate_class", ["ibuprofen", "diclofenac", "naproxen", "mefenamic"], "Review duplicate NSAID exposure before dispensing.", True),
            rule("ALLERGY_FRAMEWORK", "Allergy check framework", "allergy", ["allergy", "แพ้ยา"], "Medication allergy must be checked and documented.", True),
            rule("PEDS_AGE_BW_GATE", "Pediatric age/body-weight gate", "pediatric", ["age", "weight", "pediatric"], "Pediatric output requires age, body weight, verified dose rule, and source.", True),
            rule("CONCENTRATION_MISSING", "Pediatric concentration missing warning", "pediatric", ["missing_concentration"], "Pediatric liquid dose output requires a verified concentration.", True),
            rule("PREGNANCY_CAUTION_FRAMEWORK", "Pregnancy caution framework", "special_population", ["pregnancy"], "Pregnancy status requires product-specific review.", False),
            rule("RENAL_CAUTION_FRAMEWORK", "Renal caution framework", "special_population", ["renal"], "Renal impairment requires product-specific review.", False),
            rule("HEPATIC_CAUTION_FRAMEWORK", "Hepatic caution framework", "special_population", ["hepatic"], "Hepatic impairment requires product-specific review.", False),
            rule("STEROID_EYE_CAUTION", "Steroid eye caution framework", "ophthalmic", ["steroid_eye", "dexamethasone", "prednisolone"], "Eye steroid products require clinician review and red-flag screening.", False),
        ],
    }

    viral_conditions = ["viral_uri", "simple_diarrhea", "allergic_rhinitis", "dry_eye", "likely_viral_conjunctivitis"]
    antibiotic_stewardship = {
        "meta": {"generated_at": generated_at, "manual_review": True},
        "rules": [
            rule(
                "NO_ROUTINE_ABX_FRAMEWORK",
                "No routine antibiotics framework",
                "antibiotic_stewardship",
                viral_conditions,
                "No routine antibiotics for viral URI, simple diarrhea, allergic rhinitis, dry eye, or likely viral conjunctivitis unless a verified indication is documented.",
                False,
            ),
            rule(
                "ABX_INDICATION_DURATION_SOURCE_REQUIRED",
                "Antibiotic indication/duration/source required",
                "antibiotic_stewardship",
                ["antibiotic"],
                "Antibiotic selection requires disease-specific indication, dose, duration, and source.",
                True,
            ),
        ],
    }

    rdu_rules = {
        "meta": {"generated_at": generated_at, "manual_review": True},
        "rules": [
            rule("RDU_ANTIBIOTIC_REVIEW", "RDU antibiotic review framework", "rdu", ["antibiotic"], "Check RDU eligibility and documented indication before antibiotic use.", False),
            rule("RDU_DUPLICATE_THERAPY", "RDU duplicate therapy framework", "rdu", ["duplicate"], "Review duplicate therapy before finalizing regimen.", True),
            rule("RDU_LOCAL_PREFERENCE_ONLY", "Local preference is not evidence", "rdu", ["local_preference"], "Local clinic preference alone is insufficient for source-linked clinical rules.", True),
        ],
    }

    red_flags = {
        "meta": {"generated_at": generated_at, "manual_review": True},
        "red_flags": [
            rule("EYE_RED_FLAGS", "Eye red flags framework", "red_flag_eye", ["eye_pain", "vision_change", "photophobia", "trauma", "contact_lens"], "Eye red flags require urgent clinician review.", False),
            rule("DEHYDRATION_RED_FLAGS", "Dehydration red flags framework", "red_flag_dehydration", ["lethargy", "poor_intake", "reduced_urine", "blood_stool"], "Dehydration red flags require urgent clinician review.", False),
            rule("DYSPNEA_RED_FLAGS", "Dyspnea red flags framework", "red_flag_dyspnea", ["dyspnea", "wheeze", "cyanosis", "chest_pain"], "Dyspnea red flags require urgent clinician review.", False),
            rule("ANIMAL_BITE_RED_FLAGS", "Animal bite red flags framework", "red_flag_wound", ["animal_bite", "deep_wound", "face_hand_genital", "immunocompromised"], "Animal bite red flags require clinician review and source-linked protocol.", False),
        ],
    }

    write_json("data/safety/validation_rules.json", validation_rules)
    write_json("data/safety/rdu_rules.json", rdu_rules)
    write_json("data/safety/antibiotic_stewardship.json", antibiotic_stewardship)
    write_json("data/safety/red_flags.json", red_flags)
    return {
        "validation_rules": len(validation_rules["rules"]),
        "rdu_rules": len(rdu_rules["rules"]),
        "antibiotic_rules": len(antibiotic_stewardship["rules"]),
        "red_flags": len(red_flags["red_flags"]),
    }


def main() -> int:
    meta = build()
    print(
        "built safety layer: "
        f"validation={meta['validation_rules']} rdu={meta['rdu_rules']} "
        f"antibiotic={meta['antibiotic_rules']} red_flags={meta['red_flags']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
