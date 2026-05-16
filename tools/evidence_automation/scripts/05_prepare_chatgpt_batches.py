#!/usr/bin/env python3
import argparse
from pathlib import Path
import pandas as pd

COMMON_FIRST = [
    "uri", "cough", "sore", "rhinitis", "sinus", "diarr", "gastro", "uti", "cystitis",
    "conjunct", "dry eye", "tinea", "dermat", "eczema", "urticaria", "pain", "fever",
]
DOCTOR_PICK = ["doctor", "pick", "common", "frequent", "popular", "top"]
ANTIBIOTICS = ["antibiotic", "amoxic", "azith", "cephal", "cipro", "clinda", "doxy", "metronid"]
PEDIATRICS = ["pediatric", "child", "paed", "เด็ก", "syrup", "suspension"]


def score_task(text):
    t = text.lower()
    score = 100
    for i, k in enumerate(COMMON_FIRST):
        if k in t:
            score -= 50 - i
    for k in DOCTOR_PICK:
        if k in t:
            score -= 30
    for k in ANTIBIOTICS:
        if k in t:
            score -= 20
    for k in PEDIATRICS:
        if k in t:
            score -= 10
    return score


def read_tasks(xlsx):
    xls = pd.ExcelFile(xlsx)
    tasks = []
    for sheet, row_type in [("Disease_Download_Map", "disease"), ("Drug_Label_Links", "drug"), ("Product_Label_Links", "product")]:
        if sheet not in xls.sheet_names:
            continue
        df = pd.read_excel(xlsx, sheet_name=sheet, dtype=str).fillna("")
        for idx, row in df.iterrows():
            text = " | ".join(str(v) for v in row.to_dict().values())
            record = row.to_dict()
            tasks.append({
                "task_id": f"{row_type.upper()}_{idx+2:04d}",
                "row_type": row_type,
                "sheet": sheet,
                "row_number": idx + 2,
                "record_id": record.get("Disease_Key") or record.get("Drug") or record.get("Product_Code") or record.get("Product_Name") or "",
                "name": record.get("Disease") or record.get("Generic") or record.get("Drug") or record.get("Product_Name") or record.get("Product") or "",
                "priority_score": score_task(text),
                "source_hint": text[:1000]
            })
    return sorted(tasks, key=lambda r: (r["priority_score"], r["row_type"], r["task_id"]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--links-xlsx", required=True)
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--out-dir", default="batches/evidence_extraction")
    args = parser.parse_args()

    prompt_path = Path("tools/evidence_automation/prompts/evidence_extraction_prompt.md")
    prompt_template = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else "Extract evidence for task_list.csv."
    tasks = read_tasks(args.links_xlsx)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(exist_ok=True)

    for i in range(0, len(tasks), args.batch_size):
        batch_no = i // args.batch_size + 1
        bdir = out_dir / f"batch_{batch_no:03d}"
        bdir.mkdir(parents=True, exist_ok=True)
        chunk = tasks[i:i+args.batch_size]
        pd.DataFrame(chunk).to_csv(bdir / "task_list.csv", index=False)
        (bdir / "prompt.md").write_text(prompt_template + "\n\nUse `task_list.csv` for this batch.\n", encoding="utf-8")

    print(f"Tasks: {len(tasks)}")
    print(f"Batches: {(len(tasks) + args.batch_size - 1) // args.batch_size}")
    print(f"Wrote under: {out_dir}")

if __name__ == "__main__":
    main()
