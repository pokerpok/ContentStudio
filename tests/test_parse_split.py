"""Smoke: parse outline + split existing copy by sections."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.content.pages import (  # noqa: E402
    parse_outline_markdown,
    split_existing_copy_by_sections,
)


SAMPLE_OUTLINE = """
Title: Demo Page
Description: A short demo
URL: /en/demo
H1: Demo Page

## Page job
Help the reader understand the demo.

## Outline
- **Getting started** — intro and setup
- **Features** — what you get
- **FAQ** — common questions
"""

SAMPLE_COPY = """
## Getting started

Welcome to the demo. Install and open the app.

## Features

Speed, clarity, and editorial control.

## FAQ

Q: Is this universal?
A: Yes.
"""


def test_parse_outline_markdown_sections():
    data = parse_outline_markdown(SAMPLE_OUTLINE)
    assert data.get("meta", {}).get("title") or "Demo" in str(data)
    sections = data.get("sections") or []
    assert len(sections) >= 3
    headings = [str(s.get("heading") or "") for s in sections]
    assert any("Getting started" in h for h in headings)
    assert any("Features" in h for h in headings)


def test_split_existing_copy_by_sections():
    outline = parse_outline_markdown(SAMPLE_OUTLINE)
    sections = outline["sections"]
    chunks = split_existing_copy_by_sections(SAMPLE_COPY, sections)
    assert isinstance(chunks, dict)
    assert len(chunks) >= 2
    joined = "\n".join(chunks.values()).lower()
    assert "welcome" in joined or "demo" in joined
    assert "speed" in joined or "features" in joined
