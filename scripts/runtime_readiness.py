"""Source-gated runtime readiness helpers for OPD FAST MODE rows."""
from __future__ import annotations

from typing import Any

NO_ROUTINE_ANTIBIOTIC_KEYS = [
    "viral",
    "uri",
    "allergic_rhinitis",
    "dry_eye",
    "allergic_conjunctivitis",
    "simple_diarrhea",
    "diarrhea_adult",
    "diarrhea_child",
]

BACTERIAL_KEYS = ["bacterial", "uti", "dysuria", "animal_bite", "minor_wound"]


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def is_antibiotic(product: dict[str, Any], med: dict[str, Any] | None = None) -> bool:
    text = " ".join(
        [
            clean(product.get("category")),
            clean(product.get("generic")),
            clean(product.get("display_name")),
            clean(product.get("composition")),
            clean((med or {}).get("display_name") or (med or {}).get("n")),
        ]
    ).lower()
    return any(key in text for key in ["antibiotic", "amoxicillin", "azithromycin", "cephalexin", "clavulan", "ofloxacin", "chloramphenicol"])


def is_pediatric_calculated(med: dict[str, Any]) -> bool:
    text = " ".join(clean(med.get(key)) for key in ["order_text", "o", "dose_mode", "calculation"]).lower()
    return any(key in text for key in ["mg/kg", "ml/kg", "kg ×", "weight"])


def disease_allows_antibiotic(disease_id: str, med: dict[str, Any]) -> bool:
    text = f"{disease_id} {clean(med.get('line_type') or med.get('t'))} {clean(med.get('display_name') or med.get('n'))}".lower()
    if any(key in text for key in NO_ROUTINE_ANTIBIOTIC_KEYS) and "bacterial" not in text:
        return False
    return any(key in text for key in BACTERIAL_KEYS)


def readiness_for_med(med: dict[str, Any], product: dict[str, Any] | None, disease_id: str = "") -> dict[str, Any]:
    product = product or {}
    source_ids = list(product.get("source_ids") or [])
    verified_source_ids = [source_id for source_id in source_ids if source_id and source_id != "PRIMARY_WORKBOOK"]
    product_manual = bool(product.get("manual_review") or product.get("manual_review_required"))
    line_type = clean(med.get("line_type") or med.get("t")).upper()
    missing: list[str] = []
    source_status = "source_verified" if verified_source_ids and not product_manual else "local_rule_only"
    clinical_readiness = "usable_with_warning"
    fast_mode_allowed = True

    if not verified_source_ids:
        missing.append("verified guideline source")
        source_status = "source_gap"

    if product_manual:
        missing.append("product manual review")

    if is_pediatric_calculated(med):
        for requirement in ["pediatric source", "explicit age/body-weight rule", "parseable concentration", "route/form match"]:
            if requirement not in missing:
                missing.append(requirement)
        source_status = "pending_manual_review"
        clinical_readiness = "manual_review_required"
        fast_mode_allowed = False

    if is_antibiotic(product, med):
        if not disease_allows_antibiotic(disease_id, med):
            missing.append("bacterial indication criteria")
            clinical_readiness = "blocked" if line_type == "RX NOW" else "manual_review_required"
            fast_mode_allowed = False
        elif not verified_source_ids:
            missing.append("antibiotic source-linked rule")
            clinical_readiness = "manual_review_required"
            fast_mode_allowed = False
        source_status = "pending_manual_review" if clinical_readiness != "ready" else source_status

    if product_manual and clinical_readiness == "usable_with_warning":
        clinical_readiness = "manual_review_required"
        fast_mode_allowed = False
        source_status = "pending_manual_review"

    if source_status == "source_verified" and not missing:
        clinical_readiness = "ready"
        fast_mode_allowed = True

    return {
        "source_status": source_status,
        "clinical_readiness": clinical_readiness,
        "missing_requirements": sorted(set(missing)),
        "fast_mode_allowed": bool(fast_mode_allowed),
        "evidence_status": product.get("evidence_status", "pending_source_collection"),
        "evidence_score": float(product.get("evidence_score") or 0),
        "evidence_confidence": product.get("evidence_confidence", "none"),
        "evidence_source_ids": list(product.get("evidence_source_ids") or []),
        "evidence_required_fields_missing": list(
            product.get("evidence_required_fields_missing")
            or ["source collection", "source extraction"]
        ),
        "auto_resolution_status": product.get("auto_resolution_status", "pending_source_collection"),
    }
