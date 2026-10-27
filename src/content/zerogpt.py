"""ZeroGPT: браузерный check с извлечением подсвеченных AI-предложений.

Официальный score-only API не даёт highlights. Сайт www.zerogpt.com подсвечивает
жёлтым отдельные предложения — их забираем из DOM через Playwright.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from typing import Optional


ZEROGPT_URL = "https://www.zerogpt.com/"
# Лимит сайта ZeroGPT для вставки текста в браузере (~15k символов).
ZEROGPT_MAX_CHARS = 15_000

_chromium_ready: bool | None = None


def ensure_playwright_chromium(*, force: bool = False) -> tuple[bool, str]:
    """Поставить пакет playwright (если надо) и скачать chromium.

    На Streamlit Community Cloud браузер не ставится вместе с pip — качаем при первом check.
    """
    global _chromium_ready
    if _chromium_ready is True and not force:
        return True, "chromium already ready"

    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "playwright==1.49.0"],
                check=True,
                timeout=300,
                capture_output=True,
                text=True,
            )
        except Exception as exc:  # noqa: BLE001
            _chromium_ready = False
            return False, f"pip install playwright failed: {exc}"

    try:
        r = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=False,
            timeout=420,
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            err = (r.stderr or r.stdout or "").strip()[-500:]
            _chromium_ready = False
            return False, f"playwright install chromium failed: {err or r.returncode}"
    except Exception as exc:  # noqa: BLE001
        _chromium_ready = False
        return False, f"playwright install chromium error: {exc}"

    _chromium_ready = True
    return True, "chromium installed"


@dataclass
class ZeroGPTResult:
    ok: bool
    ai_percent: Optional[float] = None
    highlighted: list[str] = field(default_factory=list)
    error: str = ""
    raw_note: str = ""
    source: str = ""  # browser | manual | api


def _normalize_sentences(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for s in items:
        t = " ".join((s or "").split()).strip()
        if len(t) < 12:
            continue
        if "highlighted text is suspected" in t.lower():
            continue
        key = t.lower()
        if key in seen:
            continue
        # отбросить полный дамп всего текста (слишком длинный «highlight»)
        if len(t) > 600:
            continue
        seen.add(key)
        out.append(t)
    return out


def parse_manual_highlights(blob: str) -> list[str]:
    """Ручной ввод: по одному предложению на строку (или через ---)."""
    text = (blob or "").strip()
    if not text:
        return []
    if "\n---\n" in text:
        parts = text.split("\n---\n")
    else:
        parts = text.splitlines()
    return _normalize_sentences(parts)


def check_text_via_browser(
    text: str,
    *,
    headless: bool = True,
    timeout_ms: int = 90_000,
) -> ZeroGPTResult:
    """Открыть ZeroGPT в Chromium, Detect Text, снять жёлтые spans."""
    body = (text or "").strip()
    if len(body) < 80:
        return ZeroGPTResult(
            ok=False, error="Слишком короткий текст для ZeroGPT (нужно ~150+ слов)"
        )
    if len(body) > ZEROGPT_MAX_CHARS:
        return ZeroGPTResult(
            ok=False,
            error=(
                f"Текст слишком длинный для ZeroGPT: {len(body)} симв. "
                f"(лимит {ZEROGPT_MAX_CHARS}). Разбейте на секции или сократите."
            ),
            source="browser",
        )
    ok_pw, pw_msg = ensure_playwright_chromium()
    if not ok_pw:
        return ZeroGPTResult(
            ok=False,
            error=(
                f"Playwright/Chromium недоступен: {pw_msg}. "
                "Пока можно вставить подсвеченные предложения вручную."
            ),
            source="browser",
        )

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return ZeroGPTResult(
            ok=False,
            error=(
                "Нужен Playwright: pip install playwright && playwright install chromium. "
                "Пока можно вставить подсвеченные предложения вручную."
            ),
            source="browser",
        )

    try:
        with sync_playwright() as p:
            browser = None
            last_err: Exception | None = None
            # Сначала bundled chromium (Cloud), потом системные Chrome/Edge
            for launcher in (
                lambda: p.chromium.launch(headless=headless),
                lambda: p.chromium.launch(headless=headless, channel="chrome"),
                lambda: p.chromium.launch(headless=headless, channel="msedge"),
            ):
                try:
                    browser = launcher()
                    break
                except Exception as exc:  # noqa: BLE001
                    last_err = exc
                    browser = None
            if browser is None:
                # ещё одна попытка доустановить chromium
                ensure_playwright_chromium(force=True)
                try:
                    browser = p.chromium.launch(headless=headless)
                except Exception as exc:  # noqa: BLE001
                    last_err = exc
                    browser = None
            if browser is None:
                return ZeroGPTResult(
                    ok=False,
                    error=(
                        f"Не удалось запустить браузер ({last_err}). "
                        "Установите Chrome/Edge или: playwright install chromium. "
                        "Пока вставьте жёлтые предложения вручную."
                    ),
                    source="browser",
                )
            context = browser.new_context(viewport={"width": 1280, "height": 900})
            page = context.new_page()
            page.goto(ZEROGPT_URL, wait_until="domcontentloaded", timeout=timeout_ms)
            # cookie / consent overlays
            page.evaluate(
                """() => {
                  document.querySelectorAll('iframe,[id^="sp_message"],[class*="sp_veil"]')
                    .forEach(e => e.remove());
                }"""
            )
            ta = page.locator("textarea").first
            ta.wait_for(state="visible", timeout=timeout_ms)
            ta.fill(body)
            page.evaluate(
                """() => {
                  document.querySelectorAll('iframe,[id^="sp_message"],[class*="sp_veil"]')
                    .forEach(e => e.remove());
                  const btn = [...document.querySelectorAll('button')]
                    .find(b => /detect text/i.test(b.textContent || ''));
                  if (btn) btn.click();
                }"""
            )
            # ждём результат (gauge / AI GPT)
            page.wait_for_function(
                """() => /AI GPT\\*?/i.test(document.body.innerText)
                    && /\\d{1,3}(?:\\.\\d+)?%/.test(document.body.innerText)""",
                timeout=timeout_ms,
            )
            # дать DOM дорисовать подсветку
            page.wait_for_timeout(1500)
            data = page.evaluate(
                """() => {
                  function isYellow(el) {
                    const s = getComputedStyle(el);
                    const bg = s.backgroundColor || '';
                    const m = bg.match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)/);
                    if (!m) return false;
                    const r = +m[1], g = +m[2], b = +m[3];
                    return r > 200 && g > 180 && b < 120;
                  }
                  const sentences = [];
                  for (const el of document.querySelectorAll('span, mark')) {
                    if (!isYellow(el)) continue;
                    const t = (el.innerText || '').trim();
                    if (t.length >= 12) sentences.push(t);
                  }
                  const scoreM = document.body.innerText.match(
                    /(\\d{1,3}(?:\\.\\d+)?)%\\s*\\n?AI GPT/i
                  );
                  return {
                    score: scoreM ? parseFloat(scoreM[1]) : null,
                    sentences
                  };
                }"""
            )
            browser.close()
    except Exception as exc:  # noqa: BLE001
        return ZeroGPTResult(
            ok=False,
            error=f"ZeroGPT browser: {exc}",
            source="browser",
        )

    highlighted = _normalize_sentences(list(data.get("sentences") or []))
    score = data.get("score")
    return ZeroGPTResult(
        ok=True,
        ai_percent=float(score) if score is not None else None,
        highlighted=highlighted,
        source="browser",
        raw_note=f"highlights={len(highlighted)}",
    )


def apply_sentence_replacements(text: str, mapping: dict[str, str]) -> str:
    """Заменить указанные фрагменты. Пустой new = удалить фрагмент."""
    import re

    out = text
    for old, new in mapping.items():
        if not old:
            continue
        replacement = (new or "").strip()
        if old == replacement:
            continue
        if old in out:
            out = out.replace(old, replacement, 1)
        else:
            pat = re.compile(re.escape(old), re.IGNORECASE)
            out, n = pat.subn(replacement, out, count=1)
            if not n:
                loose = re.sub(r"\s+", r"\\s+", re.escape(old.strip()))
                out = re.sub(loose, replacement, out, count=1)
    # подчистить дыры после delete
    out = re.sub(r"[ \t]+\n", "\n", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    out = re.sub(r"  +", " ", out)
    out = re.sub(r" +([,.;:!?])", r"\1", out)
    return out.strip() + ("\n" if text.endswith("\n") else "")
