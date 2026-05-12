#!/usr/bin/env python3
"""UI smoke test for critical app actions."""
from __future__ import annotations

import os
import json
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
URL = os.environ.get("DRUGLIST_URL", "http://127.0.0.1:8781/index.html")
ART = ROOT / "artifacts"
ART.mkdir(exist_ok=True)


def complaint_with_swap() -> str | None:
    data = json.loads((ROOT / "data/core/app_seed_runtime.json").read_text(encoding="utf-8"))
    for complaint in data.get("cp") or []:
        for regimen in complaint.get("r") or []:
            if any("SWAP" in str(row.get("t") or row.get("s") or "").upper() for row in regimen.get("m") or []):
                return complaint.get("i")
    return None


def require_selector(page, selector: str, label: str) -> None:
    count = page.locator(selector).count()
    if count < 1:
        raise AssertionError(f"Missing {label}: {selector}")


def smoke_main_builder(page) -> None:
    page.click('[data-tab="main"]')
    page.wait_for_selector("#mainComplaints [data-c]", timeout=10000)
    buttons = page.locator("#mainComplaints [data-c]")
    if buttons.count() < 1:
        raise AssertionError("Main Builder complaint list is empty")
    swap_complaint = complaint_with_swap()
    if swap_complaint and page.locator(f'#mainComplaints [data-c="{swap_complaint}"]').count():
        page.locator(f'#mainComplaints [data-c="{swap_complaint}"]').click()
    else:
        buttons.first.click()
    page.wait_for_timeout(250)
    text = page.locator("#mainBuilder").inner_text(timeout=5000).strip()
    if len(text) < 80:
        raise AssertionError("Main Builder stayed blank after complaint selection")
    require_selector(page, "#mainBuilder .main-med-card, #mainBuilder .main-empty", "main builder rendered content")
    if page.locator("#mainBuilder .main-med-card").count() and "Status:" not in text:
        raise AssertionError("Main Builder medication rows are missing readiness status")
    if swap_complaint:
        require_selector(page, '#mainBuilder [data-testid="main-swap-panel"]', "Drug SWAPS panel")
        require_selector(page, '#mainBuilder [data-mswap]', "Drug SWAPS action")
        before = page.locator("#mainBuilder .main-swap-card.active").count()
        page.locator("#mainBuilder [data-mswap]").first.click()
        page.wait_for_timeout(150)
        after = page.locator("#mainBuilder .main-swap-card.active").count()
        if after < 1 or after < before:
            raise AssertionError("Drug SWAPS action did not activate a swap option")


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
        try:
            page = browser.new_page(viewport={"width": 1600, "height": 1300})
            errs: list[str] = []
            page.on("pageerror", lambda e: errs.append(str(e)))
            page.goto(URL, wait_until="domcontentloaded")

            page.wait_for_function("document.querySelectorAll('[data-tab]').length >= 8", timeout=10000)
            if page.locator("[data-tab]").count() < 8:
                raise AssertionError("Expected at least 8 navigation tabs")

            smoke_main_builder(page)

            for tab in ["compare", "validation", "admin", "rules", "release"]:
                page.click(f'[data-tab="{tab}"]')

            page.click('[data-tab="validation"]')
            require_selector(page, '[data-hero-action="review:json"]', "validation review JSON export")
            require_selector(page, '[data-hero-action="review:csv"]', "validation review CSV export")

            page.click('[data-tab="admin"]')
            require_selector(page, '#adminSummary .review-kpi, #adminSummary .admin-metric', "admin summary metrics")
            require_selector(page, '[data-hero-action="review:csv"], #dlImpQueueCsvAdmin', "admin review CSV export")
            require_selector(page, '[data-hero-action="review:json"], #dlImpQueueJsonAdmin', "admin review JSON export")

            page.click('[data-tab="rules"]')
            page.fill('#ruleCheckpointLabel', 'smoke-checkpoint')
            page.click('[data-rchkadd]')
            page.wait_for_selector('[data-rchkdiff]', timeout=5000)
            require_selector(page, '[data-rchkdiff]', "rule checkpoint diff")
            require_selector(page, '[data-rchkrename]', "rule checkpoint rename")
            require_selector(page, '[data-rchkdel]', "rule checkpoint delete")
            page.click('[data-rchkdiff]')

            page.fill('#rulePackImport', '{"complaints": []}')
            page.click('[data-rapply]')  # should auto-checkpoint before apply
            page.wait_for_selector('[data-rchkrestore]', timeout=5000)
            require_selector(page, '[data-rchkrestore]', "rule checkpoint restore")

            page.click('[data-tab="release"]')
            require_selector(page, '#releasePanel', "release panel")
            require_selector(page, '#releaseManifest, #runReleaseCheck', "release check action")
            require_selector(
                page,
                '#releasePanel .release-health, #releasePanel .good, #releasePanel .warning',
                "release status summary",
            )

            page.screenshot(path=str(ART / 'ui-smoke.png'), full_page=True)
            if errs:
                raise AssertionError(f"Page errors detected: {errs[:5]}")
        finally:
            browser.close()


def main() -> int:
    server = subprocess.Popen([sys.executable, "-m", "http.server", "8781"], cwd=ROOT)
    try:
        time.sleep(1.0)
        last_err = None
        last_functional_err = None
        dep_failures = []
        functional_failures = []
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
                else:
                    last_functional_err = exc
                    functional_failures.append(str(exc))
        if functional_failures:
            raise SystemExit(f"ui_smoke_test: FAIL ({last_functional_err or functional_failures[-1]})")
        if dep_failures:
            print("ui_smoke_test: SKIP due to environment/browser dependencies (non-functional limitation)")
            return 0
        raise SystemExit(f"ui_smoke_test: FAIL ({last_err})")
    finally:
        server.terminate()
        server.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
