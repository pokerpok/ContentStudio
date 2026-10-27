"""Smoke: strategy + brief + message build без вызова LLM."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.content import briefs as briefs_mod  # noqa: E402
from src.content import pages as pages_mod  # noqa: E402
from src.content import strategies as strategies_mod  # noqa: E402
from src.content.site_page_pipeline import build_site_page_messages  # noqa: E402


def test_default_brief_and_strategy():
    assert "default" in briefs_mod.list_briefs()
    brief = briefs_mod.load_brief("default")
    assert brief.get("id") == "default"
    strat = strategies_mod.get_strategy("site_page")
    assert strat.get("mode") == "site_page"
    assert strat.get("project_brief") == "default"


def test_build_outline_messages(tmp_path, monkeypatch):
    # изолируем pages dir? pages пишут в data/pages — создаём тестовую страницу
    pid = "_SMOKE_TEST"
    page = pages_mod.empty_page(pid)
    page["term"] = "Smoke"
    page["editor_inputs"] = "Keep it short."
    page["primary_job"] = "Explain smoke test"
    pages_mod.save_page(pid, page)
    try:
        msgs = build_site_page_messages(pid, phase="outline", language="en")
        assert msgs.get("system")
        assert msgs.get("user")
        assert "Your Brand" in msgs["system"] or "Project brief" in msgs["system"]
    finally:
        path = pages_mod.page_path(pid)
        if path.exists():
            path.unlink()
