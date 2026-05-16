import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def git_files():
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.splitlines()


def test_raw_accepted_evidence_cache_is_not_tracked():
    tracked = git_files()
    leaked = [
        path for path in tracked
        if path.startswith("imports/accepted_evidence/")
        and not path.endswith((".gitignore", "README.md"))
    ]
    assert leaked == []


def test_large_duplicate_evidence_reports_are_not_tracked():
    tracked = set(git_files())
    blocked = {
        "reports/source_download_results.csv",
        "reports/source_download_queue.csv",
        "reports/evidence_manifest.jsonl",
        "reports/manual_download_todo.csv",
        "reports/dailymed_candidates.csv",
        "data/gold/long_accredited_source_acquisition_queue.json",
        "data/gold/accredited_source_sweep_evidence.json",
        "data/gold/all_drug_accredited_sweep.json",
    }
    assert tracked.isdisjoint(blocked)
