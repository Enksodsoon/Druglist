#!/usr/bin/env python3
"""Shared helpers for conservative clinical audit scripts."""
from __future__ import annotations

from collections import Counter
from typing import Any

from engine_common import clean, now_iso, read_json, stable_id, write_json

ANTIBIOTIC_TERMS = [
    "amoxicillin",
    "clavulan",
    "azithromycin",
    "cephalexin",
    "ofloxacin",
    "ciprofloxacin",
    "chloramphenicol",
    "antibiotic",
]
ANTIVIRAL_TERMS = ["acyclovir", "acyvir", "clinovir", "vilerm", "valacyclovir", "zoster", "herpes", "varicella"]
NO_ABX_DISEASE_TERMS = ["viral", "uri", "allergic_rhinitis", "dry_eye", "allergic_conjunctivitis", "simple_diarrhea"]
RED_FLAG_TERMS = ["vision_loss", "photophobia", "dyspnea", "petechiae", "dehydration", "gi_bleed", "neuro"]


def products() -> list[dict[str, Any]]:
    return read_json("data/core/drug_master_rebuilt.json", {"products": []}).get("products", [])


def regimens() -> list[dict[str, Any]]:
    return read_json("data/core/fast_regimen_master.json", {"regimens": []}).get("regimens", [])


def peds_items() -> list[dict[str, Any]]:
    return read_json("data/pediatric/peds_product_dose_output.json", {"items": []}).get("items", [])


def product_map() -> dict[str, dict[str, Any]]:
    return {clean(product.get("id")): product for product in products()}


def text_for(*values: Any) -> str:
    return " ".join(clean(value) for value in values).lower()


def product_text(product: dict[str, Any]) -> str:
    return text_for(
        product.get("id"),
        product.get("display_name"),
        product.get("generic"),
        product.get("composition"),
        product.get("category"),
        product.get("form"),
        product.get("route"),
    )


def line_text(line: dict[str, Any], product: dict[str, Any] | None = None, disease_id: str = "") -> str:
    product = product or {}
    return text_for(
        disease_id,
        line.get("line_type"),
        line.get("display_name"),
        line.get("order_text"),
        line.get("duration_label"),
        product_text(product),
    )


def contains_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def is_antibiotic(product: dict[str, Any], line: dict[str, Any] | None = None, disease_id: str = "") -> bool:
    return contains_any(line_text(line or {}, product, disease_id), ANTIBIOTIC_TERMS)


def is_antiviral(product: dict[str, Any], line: dict[str, Any] | None = None, disease_id: str = "") -> bool:
    return contains_any(line_text(line or {}, product, disease_id), ANTIVIRAL_TERMS)


def is_topical(product: dict[str, Any]) -> bool:
    return contains_any(product_text(product), ["cream", "ointment", "topical", "gel"])


def is_oral(product: dict[str, Any]) -> bool:
    return contains_any(product_text(product), ["tablet", "capsule", "oral"])


def needs_concentration(product: dict[str, Any]) -> bool:
    return contains_any(product_text(product), ["syrup", "suspension", "drops", "solution"]) and not clean(product.get("concentration"))


def make_issue(
    *,
    issue_id: str,
    severity: str,
    disease_key: str = "",
    regimen_id: str = "",
    product_id: str = "",
    generic_name: str = "",
    current_sig: str = "",
    current_duration: str = "",
    issue_type: str,
    why_suspect: str,
    source_status: str = "",
    evidence_status: str = "",
    recommended_action: str,
    source_gap_needed: bool = True,
    test_case_needed: bool = True,
) -> dict[str, Any]:
    return {
        "issue_id": issue_id,
        "severity": severity,
        "disease_key": disease_key,
        "regimen_id": regimen_id,
        "product_id": product_id,
        "generic_name": generic_name,
        "current_sig": current_sig,
        "current_dose": current_sig,
        "current_duration": current_duration,
        "issue_type": issue_type,
        "why_suspect": why_suspect,
        "source_status": source_status,
        "evidence_status": evidence_status or "pending_source_collection",
        "recommended_action": recommended_action,
        "source_gap_needed": bool(source_gap_needed),
        "test_case_needed": bool(test_case_needed),
    }


def report_markdown(title: str, issues: list[dict[str, Any]], extra_lines: list[str] | None = None) -> str:
    counts = Counter(issue.get("severity") for issue in issues)
    lines = [
        f"# {title}",
        "",
        f"Generated: {now_iso()}",
        "",
        f"- Issues: {len(issues)}",
        f"- Blockers: {counts.get('blocker', 0)}",
        f"- High: {counts.get('high', 0)}",
        f"- Medium: {counts.get('medium', 0)}",
        f"- Low: {counts.get('low', 0)}",
        "",
        "No dose, duration, indication, or source was fabricated by this audit.",
    ]
    if extra_lines:
        lines.extend(["", *extra_lines])
    lines.extend(["", "## Top Issues"])
    for issue in issues[:20]:
        lines.append(
            f"- `{issue['issue_id']}` {issue['severity']} {issue['issue_type']} "
            f"{issue.get('disease_key','')} {issue.get('product_id','')}: {issue['recommended_action']}"
        )
    return "\n".join(lines).rstrip() + "\n"


def write_issue_artifacts(json_path: str, report_path: str, title: str, issues: list[dict[str, Any]], extra_lines: list[str] | None = None) -> None:
    write_json(json_path, {"meta": {"generated_at": now_iso(), "issue_count": len(issues)}, "issues": issues})
    from pathlib import Path

    Path(report_path).write_text(report_markdown(title, issues, extra_lines), encoding="utf-8")


def stable_issue(prefix: str, *parts: Any) -> str:
    return stable_id(prefix, "|".join(clean(part) for part in parts))
