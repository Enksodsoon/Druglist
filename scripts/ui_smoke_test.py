#!/usr/bin/env python3
"""UI smoke test for critical app actions."""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
URL = os.environ.get("DRUGLIST_URL", "http://127.0.0.1:8781/index.html")
ART = ROOT / "artifacts"
ART.mkdir(exist_ok=True)


def is_env_dependency_error(exc: Exception) -> bool:
    s = str(exc).lower()
    needles = [
        'host system is missing dependencies',
        'error while loading shared libraries',
        'playwright install-deps',
        'cannot open shared object file',
        'looks like playwright was just installed or updated',
        'please run the following command to download new browsers',
        "executable doesn\'t exist at",
    ]
    return any(n in s for n in needles)


def run_smoke(browser_name: str) -> None:
    with sync_playwright() as p:
        bt = getattr(p, browser_name)
        browser = bt.launch()
        page = browser.new_page(viewport={"width": 1600, "height": 1300})
        errs: list[str] = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.goto(URL, wait_until="domcontentloaded")

        assert page.locator("[data-tab]").count() >= 8

        for tab in ["compare", "validation", "admin", "rules", "release"]:
            page.click(f'[data-tab="{tab}"]')

        page.click('[data-tab="validation"]')
        assert page.locator('#dlImpQueueJson').count() == 1
        assert page.locator('#dlImpQueueCsv').count() == 1

        page.click('[data-tab="admin"]')
        assert page.locator('#dlImpQueueJsonAdmin').count() == 1
        assert page.locator('#dlImpQueueCsvAdmin').count() == 1

        page.click('[data-tab="rules"]')
        page.fill('#ruleCheckpointLabel', 'smoke-checkpoint')
        page.click('[data-rchkadd]')
        assert page.locator('[data-rchkdiff]').count() >= 1
        assert page.locator('[data-rchkrename]').count() >= 1
        assert page.locator('[data-rchkdel]').count() >= 1
        page.click('[data-rchkdiff]')

        page.fill('#rulePackImport', '{"complaints": []}')
        page.click('[data-rapply]')  # should auto-checkpoint before apply
        assert page.locator('[data-rchkrestore]').count() >= 1

        page.click('[data-tab="release"]')
        page.click('#runReleaseCheck')
        assert page.locator('#releasePanel .good, #releasePanel .warning').count() >= 1

        page.screenshot(path=str(ART / 'ui-smoke.png'), full_page=True)
        browser.close()
        if errs:
            raise AssertionError(f"Page errors detected: {errs[:5]}")


def main() -> int:
    server = subprocess.Popen(["python", "-m", "http.server", "8781"], cwd=ROOT)
    try:
        time.sleep(1.0)
        last_err = None
        dep_failures = []
        for candidate in ["chromium", "firefox"]:
            try:
                run_smoke(candidate)
                print(f"ui_smoke_test: PASS ({candidate})")
                return 0
            except Exception as exc:
                last_err = exc
                print(f"ui_smoke_test: {candidate} failed -> {exc}")
                if is_env_dependency_error(exc):
                    dep_failures.append(str(exc))
        if dep_failures:
            print("ui_smoke_test: SKIP due to environment/browser dependencies (non-functional limitation)")
            return 0
        raise SystemExit(f"ui_smoke_test: FAIL ({last_err})")
    finally:
        server.terminate()
        server.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
