"""Smoke: ZeroGPT helpers + char limit (без браузера)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.content.zerogpt import (  # noqa: E402
    ZEROGPT_MAX_CHARS,
    check_text_via_browser,
    parse_manual_highlights,
)


def test_parse_manual_highlights():
    blob = "First flagged sentence here.\nSecond flagged sentence here."
    items = parse_manual_highlights(blob)
    assert len(items) == 2
    assert "First flagged" in items[0]


def test_zerogpt_max_chars_constant():
    assert ZEROGPT_MAX_CHARS == 15_000


def test_zerogpt_rejects_overlong_without_browser():
    body = "x" * (ZEROGPT_MAX_CHARS + 50)
    res = check_text_via_browser(body, headless=True)
    assert res.ok is False
    assert "15" in res.error or str(ZEROGPT_MAX_CHARS) in res.error
