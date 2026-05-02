#!/usr/bin/env python3
"""Run deterministic OPD FAST MODE regression cases against the runtime seed."""
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Case:
    case_id: int
    text: str
    expected_hint: str = ""
    pediatric: bool = False
    red_flag: str = ""
    antibiotic_allowed: bool = False


CASES = [
    Case(1, "allergic rhinitis", "allergic_rhinitis"),
    Case(2, "uri with wet cough", "uri"),
    Case(3, "cough sore throat sputum nasal discharge", "uri"),
    Case(4, "sore throat no fever", "sore_throat"),
    Case(5, "fever myalgia", "fever"),
    Case(6, "diarrhea adult", "diarrhea"),
    Case(7, "diarrhea 5 yr BW 20 kg", "diarrhea", pediatric=True),
    Case(8, "dry eye", "dry_eye"),
    Case(9, "bacterial conjunctivitis", "bacterial_conjunctivitis", antibiotic_allowed=True),
    Case(10, "red eye pain no visual loss", red_flag="eye_red_flag"),
    Case(11, "red eye with vision loss", red_flag="eye_red_flag"),
    Case(12, "tinea cruris", "tinea"),
    Case(13, "aphthous ulcer", "aphthous"),
    Case(14, "herpes labialis", "herpes"),
    Case(15, "lip dermatitis", "dermatitis"),
    Case(16, "dyspepsia", "dyspepsia"),
    Case(17, "GERD", "gerd"),
    Case(18, "constipation with hemorrhoid", "constipation"),
    Case(19, "dysuria", "dysuria", antibiotic_allowed=True),
    Case(20, "urinary frequency pelvic pain", red_flag="urinary_red_flag"),
    Case(21, "dysmenorrhea", "dysmenorrhea"),
    Case(22, "one-sided headache no neurodef", "headache"),
    Case(23, "nausea dizzy", "nausea"),
    Case(24, "pterygium inflamed", "pterygium"),
    Case(25, "eyelid painful bump", "eyelid"),
    Case(26, "uri 10 yr BW 28 kg can take pill", "uri", pediatric=True),
    Case(27, "fever 1 yr BW 10 kg", "fever", pediatric=True),
    Case(28, "fever 5 yr BW 20 kg", "fever", pediatric=True),
    Case(29, "allergic rhinitis 6 yr BW 20 kg", "allergic_rhinitis", pediatric=True),
    Case(30, "cough cold 3 yr BW 14 kg", "cough", pediatric=True),
    Case(31, "suspected antibiotic allergy", red_flag="allergy_review"),
    Case(32, "penicillin allergy with bacterial disease", red_flag="allergy_review", antibiotic_allowed=True),
    Case(33, "NSAID allergy", red_flag="allergy_review"),
    Case(34, "pregnancy with pain", red_flag="pregnancy_review"),
    Case(35, "renal disease with NSAID request", red_flag="renal_review"),
    Case(36, "diarrhea with blood", red_flag="dehydration_or_invasive_diarrhea"),
    Case(37, "dyspnea with cough", red_flag="dyspnea_red_flag"),
    Case(38, "petechiae fever", red_flag="systemic_red_flag"),
    Case(39, "severe eye pain photophobia", red_flag="eye_red_flag"),
    Case(40, "vomiting severe dehydration", red_flag="dehydration_red_flag"),
]

FORBIDDEN_ANTIBIOTIC_HINTS = {"viral", "uri", "allergic_rhinitis", "dry_eye", "allergic_conjunctivitis", "diarrhea"}
ALLOWED_READINESS = {"ready", "usable_with_warning", "manual_review_required", "blocked"}


def load_json(path: str) -> Any:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def tokens(text: str) -> set[str]:
    return {token for token in norm(text).split() if len(token) > 1 and token not in {"with", "adult", "child", "year", "can", "take"}}


def product_is_antibiotic(product: dict[str, Any]) -> bool:
    text = " ".join(str(product.get(key, "")) for key in ["category", "generic", "composition", "display_name", "cc", "g", "c", "n"]).lower()
    return any(key in text for key in ["antibiotic", "amoxicillin", "azithromycin", "cephalexin", "clavulan", "chloramphenicol", "fusidic"])


def fallback_disease(case: Case, diseases: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if case.red_flag:
        return None
    case_tokens = tokens(case.expected_hint or case.text)
    best: tuple[int, Optional[dict[str, Any]]] = (0, None)
    for disease in diseases:
        text = " ".join(str(disease.get(key, "")) for key in ["disease_id", "display_name", "category"])
        score = len(case_tokens & tokens(text))
        if case.expected_hint and case.expected_hint.lower() in str(disease.get("disease_id", "")).lower():
            score += 5
        if score > best[0]:
            best = (score, disease)
    if not best[1]:
        return None
    return {"c": case.text, "d": best[1].get("disease_id", ""), "r": []}


def select_complaint(case: Case, complaints: list[dict[str, Any]], diseases: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if case.red_flag:
        return None
    case_tokens = tokens(case.text)
    best: tuple[int, Optional[dict[str, Any]]] = (0, None)
    for complaint in complaints:
        text = " ".join(str(complaint.get(key, "")) for key in ["c", "d", "g"])
        score = len(case_tokens & tokens(text))
        disease = str(complaint.get("d", "")).lower()
        if case.expected_hint and case.expected_hint.lower() in disease:
            score += 5
        if case.pediatric and ("peds" in disease or "child" in text.lower()):
            score += 3
        if score > best[0]:
            best = (score, complaint)
    return best[1] or fallback_disease(case, diseases)


def regimen_lines(complaint: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
    if not complaint:
        return []
    regimens = complaint.get("r") or []
    selected = next((regimen for regimen in regimens if regimen.get("y")), regimens[0] if regimens else {})
    return list(selected.get("m") or [])


def run_cases() -> tuple[list[dict[str, Any]], list[str]]:
    seed = load_json("data/core/app_seed_runtime.json")
    disease_master = load_json("data/core/disease_master.json")
    products = {product["i"]: product for product in seed.get("dr", [])}
    complaints = seed.get("cp", [])
    diseases = disease_master.get("diseases", [])
    results: list[dict[str, Any]] = []
    failures: list[str] = []
    for case in CASES:
        complaint = select_complaint(case, complaints, diseases)
        lines = regimen_lines(complaint)
        disease_key = str((complaint or {}).get("d", ""))
        status_values = [line.get("clinical_readiness") for line in lines]
        antibiotics = [
            line
            for line in lines
            if product_is_antibiotic(products.get(line.get("i"), {})) or "antibiotic" in str(line.get("n", "")).lower()
        ]
        rx_now_antibiotics = [line for line in antibiotics if line.get("t") == "RX NOW"]

        if not disease_key and not case.red_flag:
            failures.append(f"case {case.case_id}: no disease key or red flag category")
        if lines and not all(status in ALLOWED_READINESS for status in status_values):
            failures.append(f"case {case.case_id}: missing readiness status")
        if case.red_flag and lines:
            failures.append(f"case {case.case_id}: red-flag case should not routine-prescribe")
        if not case.antibiotic_allowed and any(key in disease_key for key in FORBIDDEN_ANTIBIOTIC_HINTS) and rx_now_antibiotics:
            failures.append(f"case {case.case_id}: forbidden RX NOW antibiotic behavior")
        if case.pediatric and lines and any(line.get("fast_mode_allowed") for line in lines):
            failures.append(f"case {case.case_id}: pediatric case bypassed review gate")
        if antibiotics and any(line.get("fast_mode_allowed") for line in antibiotics):
            failures.append(f"case {case.case_id}: antibiotic bypassed FAST MODE source gate")

        results.append(
            {
                "case_id": case.case_id,
                "input": case.text,
                "disease_key": disease_key,
                "red_flag_category": case.red_flag,
                "med_count": len(lines),
                "antibiotic_count": len(antibiotics),
                "readiness": sorted({str(value) for value in status_values if value}),
                "pass": not any(f"case {case.case_id}:" in failure for failure in failures),
            }
        )
    return results, failures


def write_report(results: list[dict[str, Any]], failures: list[str]) -> None:
    lines = [
        "# OPD FAST MODE Case Report",
        "",
        "This harness checks deterministic runtime behavior and safety gates. It does not prove complete clinical correctness.",
        "",
        f"Cases: {len(results)}",
        f"Pass: {not failures}",
        "",
        "| # | Input | Disease / red flag | Meds | Antibiotics | Readiness | Pass |",
        "|---|---|---|---:|---:|---|---|",
    ]
    for row in results:
        target = row["red_flag_category"] or row["disease_key"] or "unmatched"
        readiness = ", ".join(row["readiness"]) or "n/a"
        lines.append(
            f"| {row['case_id']} | {row['input']} | {target} | {row['med_count']} | {row['antibiotic_count']} | {readiness} | {row['pass']} |"
        )
    if failures:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- {failure}" for failure in failures)
    target = ROOT / "reports" / "opd_fast_mode_case_report.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    try:
        results, failures = run_cases()
    except Exception as exc:
        print(f"OPD harness crashed: {exc}", file=sys.stderr)
        return 1
    write_report(results, failures)
    print(f"wrote OPD FAST MODE case report: reports/opd_fast_mode_case_report.md ({len(results)} cases)")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
