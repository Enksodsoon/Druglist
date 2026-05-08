#!/usr/bin/env python3
"""Smoke-test Main Builder complaint selection and blocked/manual row visibility."""

from __future__ import annotations

import http.server
import json
import socketserver
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "data/core/app_seed_runtime.json"
REPORT = ROOT / "reports/main_builder_smoke_report.md"


def choose_cases() -> tuple[str | None, str | None]:
    data = json.loads(RUNTIME.read_text(encoding="utf-8"))
    linked = None
    zoster = None
    herpes_fallback = None
    for complaint in data.get("cp") or []:
        has_lines = any(regimen.get("m") for regimen in (complaint.get("r") or []))
        if has_lines and not linked:
            linked = complaint.get("i")
        hay = " ".join(
            str(x)
            for x in [
                complaint.get("i"),
                complaint.get("c"),
                complaint.get("d"),
                complaint.get("g"),
                complaint.get("mt"),
            ]
        ).lower()
        if has_lines and any(token in hay for token in ("zoster", "shingles")):
            zoster = complaint.get("i")
        if has_lines and not herpes_fallback and "herpes" in hay:
            herpes_fallback = complaint.get("i")
        if linked and zoster:
            break
    return linked, zoster or herpes_fallback


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        return


def run_browser(linked_id: str, zoster_id: str | None) -> tuple[bool, list[str]]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - exercised only on missing local deps.
        return False, [f"Playwright unavailable: {exc}"]

    messages: list[str] = []
    with socketserver.TCPServer(("127.0.0.1", 0), QuietHandler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page(viewport={"width": 1280, "height": 900})
                errors: list[str] = []
                page.on("pageerror", lambda exc: errors.append(str(exc)))
                page.goto(f"http://127.0.0.1:{port}/index.html", wait_until="networkidle")
                page.click('[data-tab="main"]')
                page.wait_for_selector("#mainComplaints [data-c]", timeout=10000)
                page.locator(f'#mainComplaints [data-c="{linked_id}"]').click()
                page.wait_for_timeout(250)
                text = page.locator("#mainBuilder").inner_text(timeout=5000).strip()
                card_count = page.locator("#mainBuilder .main-med-card").count()
                if card_count < 1 or len(text) < 80:
                    messages.append("linked complaint rendered no useful Main Builder content")
                if "Status:" not in text or "Source:" not in text:
                    messages.append("Main Builder did not render readiness/source status")
                if zoster_id:
                    page.locator(f'#mainComplaints [data-c="{zoster_id}"]').click()
                    page.wait_for_timeout(250)
                    z_text = page.locator("#mainBuilder").inner_text(timeout=5000)
                    if not any(term in z_text.lower() for term in ("blocked", "manual review", "source")):
                        messages.append("zoster/herpes selection did not expose blocked/manual/source status")
                if errors:
                    messages.extend(f"page error: {err}" for err in errors)
                browser.close()
        finally:
            server.shutdown()
    return not messages, messages


def main() -> int:
    linked_id, zoster_id = choose_cases()
    messages: list[str] = []
    if not linked_id:
        messages.append("No complaint with linked regimen rows found in runtime seed.")
    passed = False
    if linked_id:
        passed, messages = run_browser(linked_id, zoster_id)

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(
        "\n".join(
            [
                "# Main Builder Smoke Report",
                "",
                f"- Linked complaint tested: {linked_id or 'none'}",
                f"- Zoster/herpes complaint tested: {zoster_id or 'none'}",
                f"- Pass: {passed}",
                "",
                "## Messages",
                "",
                *(f"- {message}" for message in (messages or ["Main Builder rendered linked rows with readiness/source status."])),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if passed:
        print("main_builder_smoke_test: PASS")
        return 0
    print("main_builder_smoke_test: FAIL")
    for message in messages:
        print(f"- {message}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
