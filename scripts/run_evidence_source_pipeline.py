#!/usr/bin/env python3
import argparse
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL_RUNNER = REPO_ROOT / "tools" / "evidence_automation" / "scripts" / "run_pipeline.py"


def main():
    parser = argparse.ArgumentParser(description="Run Druglist evidence source acquisition from repo root.")
    parser.add_argument("--links-xlsx", default="druglist_all_download_links_2026-05-13.xlsx")
    parser.add_argument("--skip-download", action="store_true")
    args = parser.parse_args()

    cmd = [sys.executable, str(TOOL_RUNNER), "--links-xlsx", args.links_xlsx]
    if args.skip_download:
        cmd.append("--skip-download")
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)


if __name__ == "__main__":
    main()
