"""Загрузка существующей страницы по URL → текст для existing_copy."""

from __future__ import annotations

import re
import shutil
import subprocess
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import urlparse

import requests

MAX_CHARS = 80_000
USER_AGENT = (
    "Mozilla/5.0 (compatible; CardTableGen/1.0; +https://localhost; site-copy ingest)"
)


class _HTMLToText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip = 0
        self._in_heading = False

    def handle_starttag(self, tag: str, attrs) -> None:
        t = tag.lower()
        if t in ("script", "style", "noscript", "svg", "iframe"):
            self._skip += 1
            return
        if self._skip:
            return
        if t in ("br", "hr"):
            self._chunks.append("\n")
        elif t in ("p", "div", "section", "article", "li", "tr"):
            self._chunks.append("\n")
        elif t in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._chunks.append("\n\n")
            self._in_heading = True
        elif t == "a":
            href = dict(attrs).get("href")
            if href and not href.startswith("#"):
                self._chunks.append(f" [")

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in ("script", "style", "noscript", "svg", "iframe") and self._skip:
            self._skip -= 1
            return
        if self._skip:
            return
        if t in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._in_heading = False
            self._chunks.append("\n")
        elif t == "a":
            self._chunks.append("] ")
        elif t in ("p", "div", "li", "tr", "section", "article"):
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        text = data.strip() if not self._in_heading else data
        if text:
            self._chunks.append(text if self._in_heading else (" " + text + " "))

    def text(self) -> str:
        raw = "".join(self._chunks)
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def _html_to_text(html: str) -> str:
    parser = _HTMLToText()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # noqa: BLE001
        # fallback: грубая очистка тегов
        cleaned = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
        cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
        return re.sub(r"\s+", " ", cleaned).strip()
    return parser.text()


def _try_firecrawl(url: str) -> tuple[Optional[str], str]:
    """Firecrawl CLI → markdown. Returns (text|None, detail)."""
    bin_name = shutil.which("firecrawl") or shutil.which("npx")
    if not bin_name:
        return None, "firecrawl CLI не найден"
    try:
        if bin_name.endswith("npx") or bin_name.endswith("npx.cmd"):
            cmd = [
                bin_name,
                "--yes",
                "firecrawl",
                "scrape",
                url,
                "--only-main-content",
                "-f",
                "markdown",
            ]
        else:
            cmd = ["firecrawl", "scrape", url, "--only-main-content", "-f", "markdown"]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=90,
            encoding="utf-8",
            errors="replace",
        )
        err = ((proc.stderr or "") + "\n" + (proc.stdout or "")).strip()
        if proc.returncode != 0:
            low = err.lower()
            if "not authenticated" in low or "unauthorized" in low or "api key" in low:
                return None, "firecrawl не авторизован (firecrawl login --browser)"
            return None, f"firecrawl exit {proc.returncode}: {err[:200]}"
        out = (proc.stdout or "").strip()
        if not out:
            return None, "firecrawl вернул пусто"
        return out, "ok"
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"firecrawl error: {exc}"


def _try_playwright(url: str) -> tuple[Optional[str], str]:
    """Playwright chromium → текст body (для JS-сайтов)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None, "playwright не установлен"
    try:
        with sync_playwright() as p:
            browser = None
            for launcher in (
                lambda: p.chromium.launch(headless=True, channel="chrome"),
                lambda: p.chromium.launch(headless=True, channel="msedge"),
                lambda: p.chromium.launch(headless=True),
            ):
                try:
                    browser = launcher()
                    break
                except Exception:  # noqa: BLE001
                    continue
            if browser is None:
                return None, "не удалось запустить chromium"
            try:
                page = browser.new_page(user_agent=USER_AGENT)
                page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                try:
                    page.wait_for_load_state("networkidle", timeout=15_000)
                except Exception:  # noqa: BLE001
                    pass
                html = page.content()
            finally:
                browser.close()
        text = _html_to_text(html)
        if len(text.strip()) < 80:
            return None, "playwright: мало текста после очистки"
        return text, "ok"
    except Exception as exc:  # noqa: BLE001
        return None, f"playwright: {exc}"


def _fetch_http(url: str, *, timeout: int = 30) -> tuple[str, str]:
    """Возвращает (content_type, body_text_or_html)."""
    resp = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,*/*"},
        allow_redirects=True,
    )
    resp.raise_for_status()
    ctype = (resp.headers.get("Content-Type") or "").lower()
    # encoding из headers / apparent
    resp.encoding = resp.encoding or resp.apparent_encoding or "utf-8"
    return ctype, resp.text


def fetch_page_text(url: str, *, prefer_firecrawl: bool = True) -> dict:
    """
    Загружает страницу и возвращает dict:
      ok, text, source (firecrawl|http), url, error, chars
    """
    url = (url or "").strip()
    if not url:
        return {"ok": False, "error": "Пустой URL", "text": "", "source": "", "url": ""}
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return {
            "ok": False,
            "error": "Нужен абсолютный http(s) URL",
            "text": "",
            "source": "",
            "url": url,
        }

    notes: list[str] = []

    if prefer_firecrawl:
        md, detail = _try_firecrawl(url)
        if md:
            text = md[:MAX_CHARS]
            return {
                "ok": True,
                "text": text,
                "source": "firecrawl",
                "url": url,
                "error": "",
                "chars": len(text),
            }
        notes.append(detail)

    pw, pw_detail = _try_playwright(url)
    if pw:
        text = pw[:MAX_CHARS]
        return {
            "ok": True,
            "text": text,
            "source": "playwright",
            "url": url,
            "error": "",
            "chars": len(text),
            "notes": notes,
        }
    notes.append(pw_detail)

    try:
        ctype, body = _fetch_http(url)
    except requests.RequestException as exc:
        return {
            "ok": False,
            "error": f"HTTP: {exc}. " + "; ".join(notes),
            "text": "",
            "source": "http",
            "url": url,
            "chars": 0,
            "notes": notes,
        }

    if "html" in ctype or "<html" in body[:500].lower():
        text = _html_to_text(body)
    else:
        text = body.strip()

    text = text[:MAX_CHARS]
    if len(text.strip()) < 80:
        return {
            "ok": False,
            "error": (
                "Слишком мало текста после очистки (часто JS-сайт). "
                + "; ".join(notes)
                + ". Вставьте текст вручную или: firecrawl login --browser"
            ),
            "text": text,
            "source": "http",
            "url": url,
            "chars": len(text),
            "notes": notes,
        }
    return {
        "ok": True,
        "text": text,
        "source": "http",
        "url": url,
        "error": "",
        "chars": len(text),
        "notes": notes,
    }
