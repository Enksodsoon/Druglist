#!/usr/bin/env python3
"""Build guideline/source framework without fabricating clinical content."""
from __future__ import annotations

from collections import defaultdict

from engine_common import ensure_dirs, now_iso, read_json, stable_id, write_json, write_report

COMMON_OPD_PATTERNS = [
    "allergic_rhinitis",
    "uri_wet_cough",
    "uri_dry_cough",
    "sore_throat",
    "fever_myalgia",
    "diarrhea_adult",
    "diarrhea_child",
    "nausea_vomiting",
    "dyspepsia",
    "gerd",
    "constipation",
    "dry_eye",
    "red_eye",
    "bacterial_conjunctivitis",
    "allergic_conjunctivitis",
    "eyelid_bump",
    "pterygium",
    "tinea",
    "dermatitis",
    "herpes_labialis",
    "aphthous_ulcer",
    "urticaria",
    "dysuria",
    "urinary_frequency",
    "dysmenorrhea",
    "migraine_headache",
    "vertigo",
    "msk_pain",
    "minor_wound",
    "animal_bite",
]

SOURCE_PRIORITIES = [
    (1, "Thai FDA / NDP / NDI / NLEM / Thai RDU", "TH_PRIORITY_1"),
    (2, "Thai MOPH / Department of Medical Services", "TH_PRIORITY_2"),
    (3, "Thai specialty society guideline", "TH_PRIORITY_3"),
    (4, "Thai Pediatric Society / pediatric subspecialty CPG", "TH_PRIORITY_4"),
    (5, "WHO / CDC / NICE / IDSA / GINA / GOLD / ACG / AAP", "INTL_PRIORITY_5"),
    (6, "BNFC / Lexicomp Pediatric / Harriet Lane / Micromedex / drug monograph", "DRUG_REF_PRIORITY_6"),
    (7, "Product label / SmPC", "LABEL_PRIORITY_7"),
    (8, "Local clinic preference only", "LOCAL_PRIORITY_8"),
]


def registry() -> list[dict[str, object]]:
    return [
        {
            "source_id": source_id,
            "priority": priority,
            "name": name,
            "url": "",
            "local_path": "",
            "access_status": "pending_access",
            "extraction_status": "not_extracted",
            "manual_review": True,
            "notes": "Register exact document URL, version/date, and extracted page/section before using for clinical rules.",
        }
        for priority, name, source_id in SOURCE_PRIORITIES
    ]


def build() -> dict[str, object]:
    ensure_dirs("data/guidelines", "reports")
    products = read_json("data/core/drug_master_rebuilt.json", {"products": []}).get("products", [])
    generated_at = now_iso()
    source_registry = {"meta": {"generated_at": generated_at, "status": "framework_pending_source_access"}, "sources": registry()}

    disease_map = {
        "meta": {"generated_at": generated_at, "status": "unlinked_pending_source_extraction"},
        "diseases": [
            {
                "disease_id": pattern,
                "display_name": pattern.replace("_", " ").title(),
                "source_ids": [],
                "source_status": "missing_verified_source",
                "manual_review": True,
                "notes": "No guideline facts populated until a prioritized source is attached and reviewed.",
            }
            for pattern in COMMON_OPD_PATTERNS
        ],
    }

    indication_items = []
    for product in products:
        tags = set(product.get("role_tags") or [])
        if not tags:
            continue
        indication_items.append(
            {
                "product_id": product["id"],
                "display_name": product["display_name"],
                "role_tags": sorted(tags),
                "indications": [],
                "source_ids": [],
                "source_status": "missing_verified_source",
                "manual_review": True,
            }
        )

    empty_rule_meta = {"generated_at": generated_at, "status": "no_verified_rules_without_sources", "manual_review": True}
    rdu_rules = {
        "meta": empty_rule_meta,
        "rules": [
            {
                "rule_id": "RDU_FRAMEWORK_PENDING",
                "title": "RDU rule framework pending source extraction",
                "source_ids": [],
                "active": False,
                "manual_review": True,
                "notes": "Do not activate until Thai RDU/NLEM/NDP or equivalent source text is attached.",
            }
        ],
    }
    antibiotic_rules = {
        "meta": empty_rule_meta,
        "rules": [
            {
                "rule_id": "ABX_STEWARDSHIP_FRAMEWORK_PENDING",
                "title": "Antibiotic stewardship framework pending source extraction",
                "source_ids": [],
                "active": False,
                "manual_review": True,
                "notes": "No disease-specific antibiotic indication, dose, or duration is asserted here.",
            }
        ],
    }
    safety_rules = {
        "meta": empty_rule_meta,
        "rules": [
            {
                "rule_id": "SAFETY_FRAMEWORK_PENDING",
                "title": "Safety guideline framework pending source extraction",
                "source_ids": [],
                "active": False,
                "manual_review": True,
                "notes": "Safety validations may exist as non-dose guardrails, but source-linked clinical assertions remain pending.",
            }
        ],
    }

    source_gap_items = []
    for pattern in COMMON_OPD_PATTERNS:
        source_gap_items.append(
            {
                "gap_id": stable_id("GAP_DISEASE", pattern),
                "entity_type": "disease",
                "entity_id": pattern,
                "required_source_priority": [p for p, _, _ in SOURCE_PRIORITIES[:6]],
                "status": "pending_access",
                "manual_review": True,
            }
        )
    tagged_counts: dict[str, int] = defaultdict(int)
    for product in products:
        for tag in product.get("role_tags") or []:
            tagged_counts[tag] += 1
    for tag, count in sorted(tagged_counts.items()):
        source_gap_items.append(
            {
                "gap_id": stable_id("GAP_TAG", tag),
                "entity_type": "drug_role_tag",
                "entity_id": tag,
                "affected_products": count,
                "required_source_priority": [p for p, _, _ in SOURCE_PRIORITIES[:7]],
                "status": "pending_access",
                "manual_review": True,
            }
        )

    outputs = {
        "data/guidelines/source_registry.json": source_registry,
        "data/guidelines/disease_guideline_map.json": disease_map,
        "data/guidelines/drug_indication_guideline_map.json": {
            "meta": {"generated_at": generated_at, "status": "unlinked_pending_source_extraction"},
            "items": indication_items,
        },
        "data/guidelines/dose_rules_adult_source_linked.json": {"meta": empty_rule_meta, "rules": []},
        "data/guidelines/dose_rules_peds_source_linked.json": {"meta": empty_rule_meta, "rules": []},
        "data/guidelines/rdu_source_linked_rules.json": rdu_rules,
        "data/guidelines/antibiotic_guideline_rules.json": antibiotic_rules,
        "data/guidelines/safety_guideline_rules.json": safety_rules,
        "data/guidelines/evidence_conflict_log.json": {"meta": {"generated_at": generated_at}, "conflicts": []},
        "data/guidelines/source_gap_list.json": {
            "meta": {"generated_at": generated_at, "gap_count": len(source_gap_items)},
            "items": source_gap_items,
        },
    }
    for path, payload in outputs.items():
        write_json(path, payload)

    write_report(
        "reports/guideline_integration_report.md",
        "Guideline Source Layer Report",
        [
            ("Status", "Framework generated. No local guideline source documents were found in `source_guidelines/`, so clinical rules remain inactive and manual-review gated."),
            ("Source Priority Registry", "\n".join(f"- P{p}: {name}" for p, name, _ in SOURCE_PRIORITIES)),
            ("Generated Maps", f"Disease maps: {len(COMMON_OPD_PATTERNS)}\n\nDrug role mappings requiring sources: {len(indication_items)}"),
            ("Clinical Data Policy", "No guideline dose, pediatric dose, duration, indication, contraindication, or safety assertion was fabricated."),
        ],
    )
    write_report(
        "reports/source_gap_report.md",
        "Source Gap Report",
        [
            ("Summary", f"Pending source gaps: {len(source_gap_items)}"),
            ("Required Action", "Attach exact source documents or URLs, extract page/section evidence, then promote rules from inactive/manual-review to active."),
        ],
    )
    return {"source_count": len(source_registry["sources"]), "gap_count": len(source_gap_items)}


def main() -> int:
    meta = build()
    print(f"built guideline framework: sources={meta['source_count']} gaps={meta['gap_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
