"""Pros/Cons list formatting must survive normalize / collapse guards."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.content.pages import normalize_section_list_markup  # noqa: E402
from src.content.site_page_pipeline import (  # noqa: E402
    _is_structured_block,
    _preserve_structured_format,
)


SAMPLE = """## LuckyWave Casino Review

Intro paragraph stays prose.

Pros

    Mixed fiat and crypto deposit routes in one account
    Supports BTC, ETH, LTC, DOGE, BCH and USDT wallets
    Crypto withdrawals stated at around one hour

Cons

    No licensing authority confirmed in reliable public sources
    Not covered by UK Gambling Commission or GAMSTOP
"""


def test_normalize_indented_pros_cons_to_bullets():
    out = normalize_section_list_markup(SAMPLE)
    assert "- Mixed fiat" in out
    assert "- Supports BTC" in out
    assert "- No licensing" in out
    assert "Pros\n\n- " in out or "Pros\n- " in out


def test_structured_block_detected():
    assert _is_structured_block(
        "Pros\n\n    Item one here is long enough\n    Item two here is long enough"
    )


def test_preserve_rejects_collapsed_list():
    original = normalize_section_list_markup(SAMPLE)
    collapsed = (
        "Pros Mixed fiat and crypto deposit routes in one account "
        "Supports BTC, ETH, LTC and Cons No licensing authority confirmed"
    )
    kept = _preserve_structured_format(original, collapsed)
    assert "- Mixed fiat" in kept
    assert "\n" in kept
