#!/usr/bin/env python3
"""Apply conservative correction overlays to generated runtime regimens."""
from __future__ import annotations

from engine_common import clean, now_iso, read_json, write_json


BLOCKING_ACTIONS = {"block_regimen", "remove_from_rx_now", "catalog_only"}
DOWNGRADE_ACTIONS = {"downgrade_readiness", "move_to_swap_criteria_dependent", "add_source_gap", "require_peds_source", "require_antibiotic_criteria", "require_red_flag_override"}


def apply() -> dict[str, int]:
    payload = read_json("data/core/fast_regimen_master.json", {"regimens": [], "meta": {}})
    corrections = [
        correction
        for correction in read_json("data/overrides/regimen_corrections.json", {"corrections": []}).get("corrections", [])
        if correction.get("validation_status") == "active"
    ]
    by_target: dict[str, list[dict[str, object]]] = {}
    for correction in corrections:
        by_target.setdefault(clean(correction.get("target_id")), []).append(correction)
    applied: list[dict[str, object]] = []
    for regimen in payload.get("regimens", []):
        reg_corrections = by_target.get(clean(regimen.get("regimen_id")), [])
        if not reg_corrections:
            continue
        blocked_reasons = list(regimen.get("blocked_reasons") or [])
        warnings = list(regimen.get("warnings") or [])
        for correction in reg_corrections:
            action = clean(correction.get("action"))
            reason = clean(correction.get("reason"))
            if action in BLOCKING_ACTIONS:
                regimen["clinical_readiness"] = "blocked"
                regimen["correction_status"] = "blocked_by_overlay"
                blocked_reasons.append(reason)
            elif action in DOWNGRADE_ACTIONS:
                regimen["clinical_readiness"] = "manual_review_required"
                regimen["correction_status"] = "downgraded_by_overlay"
                warnings.append(reason)
            regimen["manual_review"] = True
            regimen["source_gap_needed"] = bool(correction.get("source_required", True))
            regimen["next_action"] = "attach accepted source evidence and rerun clinical verification"
            for line in regimen.get("lines") or []:
                if action in BLOCKING_ACTIONS:
                    line["clinical_readiness"] = "blocked"
                    line["fast_mode_allowed"] = False
                    line["source_status"] = "pending_manual_review"
                    line["blocked_reason"] = reason
                else:
                    line["clinical_readiness"] = "manual_review_required"
                    line["fast_mode_allowed"] = False
                    line["source_status"] = "pending_manual_review"
                    line["blocked_reason"] = reason
                missing = list(line.get("missing_requirements") or [])
                missing.extend(["accepted source evidence", "traceable regimen dose/frequency/duration"])
                line["missing_requirements"] = sorted(set(missing))
                line["evidence_status"] = "blocked_missing_required_safety_field"
                line["auto_resolution_status"] = "blocked_missing_required_safety_field"
                line["clinical_audit_status"] = regimen.get("correction_status")
                line["correction_status"] = regimen.get("correction_status")
            applied.append({"correction_id": correction.get("correction_id"), "target_id": correction.get("target_id"), "action": action})
        regimen["blocked_reasons"] = sorted(set(blocked_reasons))
        regimen["warnings"] = sorted(set(warnings))
    payload["meta"] = {**payload.get("meta", {}), "correction_overlay_applied_count": len(applied), "generated_at": payload.get("meta", {}).get("generated_at") or now_iso()}
    write_json("data/core/fast_regimen_master.json", payload)
    write_json("data/meta/correction_overlay_applied.json", {"meta": {"generated_at": now_iso(), "applied_count": len(applied)}, "items": applied})
    lines = ["# Correction Overlay Report", "", f"Generated: {now_iso()}", "", f"- Corrections applied: {len(applied)}"]
    for item in applied:
        lines.append(f"- `{item['correction_id']}` {item['action']} target `{item['target_id']}`")
    open("reports/correction_overlay_report.md", "w", encoding="utf-8").write("\n".join(lines).rstrip() + "\n")
    return {"applied_count": len(applied)}


def main() -> int:
    summary = apply()
    print(f"apply_corrections: applied={summary['applied_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
