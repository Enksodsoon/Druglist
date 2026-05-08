#!/usr/bin/env python3
"""Generate prioritized source-manifest TODO rows without accepting sources."""
from __future__ import annotations

from engine_common import clean, now_iso, read_json, stable_id, write_json


def add_task(tasks: list[dict[str, object]], *, title_query: str, organization: str, clinical_domain: str, related_drugs: list[str], related_complaints: list[str], evidence_needed: list[str], source_type: str, priority: int) -> None:
    tasks.append(
        {
            "todo_id": stable_id("SRC_TODO", title_query + clinical_domain),
            "source_id_suggestion": stable_id("SRC", title_query)[:18].lower(),
            "title_query": title_query,
            "organization_target": organization,
            "clinical_domain": clinical_domain,
            "related_drugs": related_drugs,
            "related_complaints": related_complaints,
            "evidence_needed": evidence_needed,
            "preferred_source_type": source_type,
            "search_query": f"{organization} {title_query} guideline dose duration",
            "priority": priority,
            "review_status": "pending",
            "source_url_candidates": [],
            "notes": "Human review required before adding to source_manifest.json as accepted.",
        }
    )


def build() -> list[dict[str, object]]:
    tasks: list[dict[str, object]] = []
    add_task(tasks, title_query="acyclovir herpes zoster shingles adult treatment", organization="Thai MOPH or Thai specialty society", clinical_domain="antiviral", related_drugs=["acyclovir"], related_complaints=["herpes_zoster_adult", "shingles"], evidence_needed=["indication", "adult dose", "frequency", "duration", "timing window", "red flags"], source_type="guideline", priority=1)
    add_task(tasks, title_query="acyclovir herpes labialis adult treatment", organization="Thai MOPH or dermatology society", clinical_domain="antiviral", related_drugs=["acyclovir"], related_complaints=["herpes_labialis_adult"], evidence_needed=["indication", "adult dose", "frequency", "duration"], source_type="guideline", priority=1)
    for name in ["paracetamol pediatric fever pain", "ibuprofen pediatric fever pain", "ORS pediatric diarrhea", "cetirizine pediatric allergic rhinitis"]:
        add_task(tasks, title_query=name, organization="Thai Pediatric Society or MOPH", clinical_domain="pediatric", related_drugs=name.split()[:1], related_complaints=["pediatric common OPD"], evidence_needed=["age/BW rule", "dose basis", "frequency", "max dose", "duration"], source_type="guideline", priority=1)
    for name in ["viral URI no antibiotic", "simple diarrhea no routine antibiotic", "bacterial conjunctivitis topical antibiotic", "UTI antibiotic outpatient criteria"]:
        add_task(tasks, title_query=name, organization="Thai RDU/MOPH or IDSA/WHO", clinical_domain="antibiotic_rdu", related_drugs=["antibiotics"], related_complaints=[name], evidence_needed=["bacterial criteria", "no-antibiotic criteria", "dose", "duration"], source_type="guideline", priority=2)
    for name in ["red eye pain photophobia vision loss red flags", "pediatric severe dehydration red flags"]:
        add_task(tasks, title_query=name, organization="Thai MOPH or WHO", clinical_domain="red_flags", related_drugs=[], related_complaints=[name], evidence_needed=["red flags", "referral criteria"], source_type="guideline", priority=2)
    # Include audit-derived placeholders without duplicating huge source-gap data.
    for path, domain in [
        ("data/guidelines/antiviral_source_gaps.json", "antiviral"),
        ("data/pediatric/pediatric_source_gap_priority.json", "pediatric"),
        ("data/guidelines/antibiotic_source_gap_priority.json", "antibiotic_rdu"),
    ]:
        items = read_json(path, {"items": []}).get("items", [])[:10]
        for item in items:
            title = clean(item.get("display_name") or item.get("generic_name") or item.get("disease_key") or item.get("product_id") or item.get("gap_id"))
            if title:
                add_task(tasks, title_query=f"{title} source review", organization="official guideline or product label authority", clinical_domain=domain, related_drugs=[clean(item.get("generic_name") or item.get("product_id"))], related_complaints=[clean(item.get("disease_key"))], evidence_needed=list(item.get("evidence_needed") or ["source evidence"]), source_type="guideline", priority=int(item.get("tier") or item.get("priority") or 3))
    dedup = {task["todo_id"]: task for task in tasks}
    return sorted(dedup.values(), key=lambda task: (int(task["priority"]), str(task["title_query"])))


def main() -> int:
    tasks = build()
    write_json("data/evidence/source_manifest.todo.json", {"meta": {"generated_at": now_iso(), "todo_count": len(tasks)}, "items": tasks})
    lines = ["# Source Manifest Bootstrap Report", "", f"Generated: {now_iso()}", "", f"- TODO source rows: {len(tasks)}", "- Accepted sources created: 0"]
    for task in tasks[:20]:
        lines.append(f"- P{task['priority']} {task['clinical_domain']}: {task['title_query']}")
    open("reports/evidence/source_manifest_bootstrap_report.md", "w", encoding="utf-8").write("\n".join(lines).rstrip() + "\n")
    print(f"source_manifest_bootstrap: todo={len(tasks)} accepted=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
