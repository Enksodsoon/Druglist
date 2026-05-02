import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"


def test_dist_build_creates_frontend_artifact():
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_dist.py")], cwd=ROOT, check=True)
    assert (DIST / "index.html").exists()
    assert (DIST / "index.html").stat().st_size > 0
    assert (DIST / "data" / "core" / "app_seed_runtime.json").exists()
    assert (DIST / "build_info.json").exists()


def test_dist_excludes_private_and_review_files():
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_dist.py"), "--validate-only"], cwd=ROOT, check=True)
    forbidden_parts = {"source_workbooks", "source_guidelines", "reports", "scripts", "tests", ".venv"}
    forbidden_suffixes = {".xlsx", ".xls", ".sqlite", ".db", ".csv", ".py"}
    for path in DIST.rglob("*"):
        rel = path.relative_to(DIST)
        assert not (set(rel.parts) & forbidden_parts)
        if path.is_file():
            assert path.suffix.lower() not in forbidden_suffixes


def test_github_pages_workflow_exists():
    workflow = ROOT / ".github" / "workflows" / "deploy-pages.yml"
    assert workflow.exists()
    text = workflow.read_text(encoding="utf-8")
    assert "actions/deploy-pages" in text
    assert "scripts/build_dist.py" in text
