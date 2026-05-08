#!/usr/bin/env python3
"""Validate whole-regimen safety patterns and duplicate ingredient risks."""
from __future__ import annotations

from collections import Counter

from engine_common import now_iso, write_json
from clinical_audit_common import NO_ABX_DISEASE_TERMS, contains_any, is_antibiotic, product_map, regimens, text_for


ROLE_TERMS = {
    "paracetamol": ["paracetamol", "acetaminophen"],
    "nsaid": ["ibuprofen", "diclofenac", "naproxen", "mefenamic"],
    "antihistamine": ["cetirizine", "loratadine", "chlorpheniramine", "brompheniramine", "desloratadine"],
    "decongestant": ["pseudoephedrine", "phenylephrine", "xylometazoline"],
    "antibiotic": ["amoxicillin", "azithromycin", "cephalexin", "ofloxacin", "chloramphenicol", "clavulan"],
}


def roles_for(text: str) -> list[str]:
    return [role for role, terms in ROLE_TERMS.items() if contains_any(text, terms)]


def validate() -> list[dict[str, object]]:
    products = product_map()
    rows: list[dict[str, object]] = []
    for regimen in regimens():
        disease_id = str(regimen.get("disease_id") or "")
        disease_text = text_for(disease_id, regimen.get("display_name"), regimen.get("workflow_label"))
        role_counts: Counter[str] = Counter()
        blocked: list[str] = []
        warnings: list[str] = []
        duplicate_roles: list[str] = []
        for line in regimen.get("lines") or []:
            product = products.get(str(line.get("product_id") or "")) or {}
            line_text = text_for(line.get("display_name"), line.get("order_text"), product.get("generic"), product.get("composition"))
            for role in roles_for(line_text):
                role_counts[role] += 1
            if is_antibiotic(product, line, disease_id) and contains_any(disease_text, NO_ABX_DISEASE_TERMS):
                blocked.append("antibiotic in viral/simple/allergic/dry-eye condition")
            if line.get("clinical_readiness") == "ready" and line.get("source_status") != "source_verified":
                blocked.append("ready without verified source")
        duplicate_roles = sorted(role for role, count in role_counts.items() if count > 1)
        if duplicate_roles:
            warnings.append("duplicate therapeutic roles: " + ", ".join(duplicate_roles))
        rows.append(
            {
                "regimen_id": regimen.get("regimen_id"),
                "disease_key": disease_id,
                "regimen_safety_status": "blocked" if blocked else "warning" if warnings else "manual_review_required",
                "duplicate_roles": duplicate_roles,
                "blocked_reasons": sorted(set(blocked)),
                "warnings": sorted(set(warnings)),
                "suggested_removal": [],
            }
        )
    return rows


def main() -> int:
    rows = validate()
    write_json("data/safety/regimen_safety_rules.json", {"meta": {"generated_at": now_iso(), "regimen_count": len(rows)}, "items": rows})
    lines = [
        "# Regimen Safety Report",
        "",
        f"Generated: {now_iso()}",
        "",
        f"- Regimens checked: {len(rows)}",
        f"- Blocked: {sum(1 for r in rows if r['regimen_safety_status'] == 'blocked')}",
        f"- Warnings: {sum(1 for r in rows if r['regimen_safety_status'] == 'warning')}",
    ]
    for row in rows:
        if row["blocked_reasons"] or row["warnings"]:
            lines.append(f"- `{row['regimen_id']}` {row['regimen_safety_status']}: {', '.join(row['blocked_reasons'] or row['warnings'])}")
    open("reports/regimen_safety_report.md", "w", encoding="utf-8").write("\n".join(lines).rstrip() + "\n")
    print(f"regimen_safety_validate: regimens={len(rows)} blocked={sum(1 for r in rows if r['regimen_safety_status']=='blocked')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
