"""Пути и JSON-хелперы для data/."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
PROMPTS_DIR = DATA_DIR / "prompts"
STRATEGIES_DIR = DATA_DIR / "strategies"
TERMS_PATH = DATA_DIR / "terms.json"
SETTINGS_PATH = DATA_DIR / "settings.json"
OUTPUT_DIR = PROJECT_ROOT / "output"
GUIDES_DIR = OUTPUT_DIR / "guides"
IMAGES_DIR = OUTPUT_DIR / "images"


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    raw = path.read_bytes()
    if not raw.strip():
        return default

    def _parse_text(text: str) -> Any:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            obj, _end = json.JSONDecoder().raw_decode(text.lstrip())
            return obj

    # JSON в проекте — только UTF-8; cp1251 НЕ используем как fallback:
    # один битый байт UTF-8 иначе превращает весь файл в «кракозябры».
    for enc in ("utf-8-sig", "utf-8"):
        try:
            return _parse_text(raw.decode(enc))
        except UnicodeDecodeError:
            continue
        except json.JSONDecodeError:
            continue

    # частично битый UTF-8 — вырезаем хвост через raw_decode
    try:
        text = raw.decode("utf-8", errors="replace")
        return _parse_text(text)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        pass

    # крайний случай: файл реально в Windows-1251 (legacy)
    try:
        return _parse_text(raw.decode("cp1251"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def fix_mojibake(text: str) -> str:
    """UTF-8, ошибочно прочитанный как Latin-1/CP1252 → нормальный Unicode."""
    if not text or not isinstance(text, str):
        return text
    # типичные следы double-encoding кириллицы / en-dash
    if not any(ch in text for ch in ("Ð", "Ã", "â", "Ñ", "Ò", "Ó", "Õ", "Ö", "×")):
        return text
    try:
        fixed = text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text
    # принять, если ушла «кракозябра» или появилась кириллица
    cyr_before = sum(1 for ch in text if "а" <= ch.lower() <= "я" or ch.lower() == "ё")
    cyr_after = sum(1 for ch in fixed if "а" <= ch.lower() <= "я" or ch.lower() == "ё")
    if cyr_after > cyr_before or ("Ð" in text and "Ð" not in fixed):
        return fixed
    return text


def fix_mojibake_deep(obj: Any) -> tuple[Any, bool]:
    """Рекурсивно починить строки в dict/list. Возвращает (obj, changed)."""
    if isinstance(obj, str):
        fixed = fix_mojibake(obj)
        return fixed, fixed != obj
    if isinstance(obj, list):
        changed = False
        out = []
        for item in obj:
            fixed_item, ch = fix_mojibake_deep(item)
            changed = changed or ch
            out.append(fixed_item)
        return out, changed
    if isinstance(obj, dict):
        changed = False
        out: dict[str, Any] = {}
        for k, v in obj.items():
            fixed_v, ch = fix_mojibake_deep(v)
            changed = changed or ch
            out[k] = fixed_v
        return out, changed
    return obj, False

def slugify(term: str) -> str:
    return (
        term.replace("/", "_")
        .replace("\\", "_")
        .replace(" ", "_")
        .replace("'", "")
        .replace('"', "")
    )


def content_stem(term: str, language: str = "ru") -> str:
    """Имя файла/папки без расширения: `{lang}_{slug}`."""
    lang = (language or "ru").strip().lower() or "ru"
    return f"{lang}_{slugify(term)}"


def parse_content_stem(stem: str) -> tuple[str, str]:
    """Из `en_How_to_use_...` → (`en`, `How_to_use_...`). Legacy без префикса → (`ru`, stem)."""
    from .languages import LANGUAGES, DEFAULT_LANGUAGE

    for code in LANGUAGES:
        prefix = f"{code}_"
        if stem.startswith(prefix) and len(stem) > len(prefix):
            return code, stem[len(prefix) :]
    return DEFAULT_LANGUAGE, stem

