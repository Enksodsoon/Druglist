#!/usr/bin/env python3
"""Common helpers for Gold source adapters."""

from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AdapterOutput:
    accepted_sources: list[dict[str, Any]] = field(default_factory=list)
    evidence_claims: list[dict[str, Any]] = field(default_factory=list)
    rejected_sources: list[dict[str, Any]] = field(default_factory=list)
    search_tasks: list[dict[str, Any]] = field(default_factory=list)


def fetch_json(url: str, timeout: int = 20) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "DruglistGold/2.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_text(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "DruglistGold/2.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read(4_000_000).decode("utf-8", errors="ignore")
    text = re.sub(r"<[^>]+>", " ", raw)
    return html.unescape(re.sub(r"\s+", " ", text)).strip()


def text_window(text: str, phrase: str, width: int = 520) -> str:
    idx = text.lower().find(phrase.lower())
    if idx < 0:
        return ""
    start = max(0, idx - width // 2)
    end = min(len(text), idx + width // 2)
    return re.sub(r"\s+", " ", text[start:end]).strip()


def quote(value: str) -> str:
    return urllib.parse.quote(value)
