#!/usr/bin/env python3
import argparse
import subprocess
import sys
from pathlib import Path

STEPS = [
    ["tools/evidence_automation/scripts/00_setup_folders.py"],
    ["tools/evidence_automation/scripts/01_build_source_queue.py", "--links-xlsx"],
    ["tools/evidence_automation/scripts/02_download_http_sources.py", "--queue", "reports/evidence_acquisition/source_download_queue.csv"],
    ["tools/evidence_automation/scripts/03_dailymed_resolver.py", "--links-xlsx"],
    ["tools/evidence_automation/scripts/04_build_manifest.py", "--root", "imports/accepted_evidence"],
    ["tools/evidence_automation/scripts/05_prepare_chatgpt_batches.py", "--links-xlsx"],
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--links-xlsx", default="druglist_all_download_links_2026-05-13.xlsx")
    parser.add_argument("--skip-download", action="store_true")
    args = parser.parse_args()

    for step in STEPS:
        if args.skip_download and "02_download_http_sources.py" in step[0]:
            print("Skipping HTTP download step")
            continue
        cmd = [sys.executable]
        for part in step:
            if part == "--links-xlsx":
                cmd += [part, args.links_xlsx]
            else:
                cmd.append(part)
        print("\n$ " + " ".join(cmd))
        subprocess.run(cmd, check=True)

if __name__ == "__main__":
    main()
