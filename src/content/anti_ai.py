"""Общий анти-AI блок для system-промптов + эвристики паттернов.

Жёсткий pass подмешивает пакет iGamingTextLab AI-Humanizer
(CC BY 4.0 — см. data/prompts/igtl/ATTRIBUTION.md).
"""

from __future__ import annotations

import re
from pathlib import Path

from .store import PROMPTS_DIR

ANTI_AI_FILE = "anti_ai_style.md"
ANTI_AI_HARD_FILE = "anti_ai_style_hard.md"
IGTL_DIR = PROMPTS_DIR / "igtl"
IGTL_REF = IGTL_DIR / "references"

_PATTERN_RULES: list[tuple[str, re.Pattern[str]]] = [
    (
        "not X but Y / это не X а Y",
        re.compile(
            r"(?i)\b(?:this\s+is\s+)?not\s+[^,.;]{1,40},\s*but\b|"
            r"\bэто\s+не\s+[^,.;]{1,40},\s*а\b|"
            r"\bне\s+просто\s+[^,.;]{1,30},\s*а\b"
        ),
    ),
    ("Whether… or…", re.compile(r"(?i)\bwhether\s+you(?:'re| are)\b.{0,40}\bor\b")),
    ("From X to Y opener", re.compile(r"(?i)^from\s+.{0,40}\sto\s+", re.M)),
    (
        "When it comes to…",
        re.compile(r"(?i)\bwhen\s+it\s+comes\s+to\b|\bкогда\s+речь\s+ид[её]т\s+о\b"),
    ),
    (
        "Here's what / Let's break it down",
        re.compile(
            r"(?i)\bhere'?s\s+what\s+matters\b|\blet'?s\s+break\s+it\s+down\b|"
            r"\bat\s+the\s+end\s+of\s+the\s+day\b|\bдавайте\s+разбер"
        ),
    ),
    (
        "It offers / It provides",
        re.compile(
            r"(?i)\bit\s+(?:offers|provides)\b|"
            r"\bон[ао]?\s+(?:предлагает|обеспечивает)\b"
        ),
    ),
    ("By doing X, you…", re.compile(r"(?i)^by\s+\w+ing\b.{0,60}\byou\b", re.M)),
    (
        "In conclusion / В заключение",
        re.compile(r"(?i)\bin\s+conclusion\b|\bв\s+заключение\b|\bподводя\s+итог"),
    ),
    (
        "AI buzzwords",
        re.compile(
            r"(?i)\b(?:seamless|immersive|unforgettable|unparalleled|cutting-?edge|"
            r"unlock(?:s|ing)?|elevate|delve|journey|vibrant|empower|foster|harness|"
            r"tapestry|next-?level|streamline|pivotal|comprehensive|leverage)\b|"
            r"бесшовн|незабываем|погружени[ея]|уникальн(?:ый|ого)\s+опыт|"
            r"комплексн(?:ый|ого)\s+подход|инновационн"
        ),
    ),
    (
        "iGaming cliché",
        re.compile(
            r"(?i)\b(?:unbeatable\s+bonus|generous\s+promotions|lucrative\s+rewards|"
            r"maximize\s+your\s+winnings|boost\s+your\s+chances|"
            r"something\s+for\s+everyone|a\s+game\s+for\s+every\s+taste|"
            r"suits\s+novice\s+and\s+experienced|"
            r"seamless(?:ly)?\s+(?:gaming\s+)?experience|"
            r"immersive\s+gaming\s+experience|"
            r"user-?friendly\s+interface|"
            r"stands?\s+out\s+from\s+the\s+rest|"
            r"it'?s\s+worth\s+noting|"
            r"experience\s+the\s+thrill)\b|"
            r"бесшовн\w*\s+опыт|незабываем\w*\s+(?:бонус|опыт)|"
            r"есть\s+что[- ]то\s+для\s+каждого"
        ),
    ),
    ("Em-dash overuse", re.compile(r"—")),
    (
        "Rhetorical Q + soft CTA",
        re.compile(
            r"(?i)\?\s*(?:read\s+on|learn\s+more|find\s+out|узнай|читайте\s+дальше)"
        ),
    ),
    (
        "Great question / частый вопрос filler",
        re.compile(
            r"(?i)\bgreat\s+question\b|\bэто\s+частый\s+вопрос\b|"
            r"\bexcellent\s+question\b"
        ),
    ),
]


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _unwrap_fenced_block(text: str) -> str:
    """master-prompt.md обёрнут в ``` — достаём содержимое."""
    t = (text or "").strip()
    if "```" not in t:
        return t
    parts = t.split("```")
    # берём самый длинный кусок между fence
    chunks = [p.strip() for p in parts[1:] if p.strip() and not p.strip().startswith("md")]
    if not chunks:
        return t.replace("```", "").strip()
    return max(chunks, key=len)


def _adapt_igtl_for_pipeline(text: str) -> str:
    """В пайплайне нельзя «спросить пользователя» — только placeholder / вырезка."""
    t = text or ""
    replacements = [
        (
            "ask the user for one or drop the claim",
            "use `[PLACEHOLDER]` or drop the claim",
        ),
        (
            "ask the user for one",
            "use `[PLACEHOLDER]` if the brief lacks the fact",
        ),
        (
            "ask rather than guess",
            "use `[PLACEHOLDER]` or omit — never invent",
        ),
        (
            "ask for it, or drop the claim",
            "use `[PLACEHOLDER]`, or drop the claim",
        ),
        (
            "ask the user",
            "leave `[PLACEHOLDER]` / omit",
        ),
    ]
    low = t
    for old, new in replacements:
        low = re.sub(re.escape(old), new, low, flags=re.I)
    return low


def load_anti_ai_style() -> str:
    path = PROMPTS_DIR / ANTI_AI_FILE
    base = _read_text(path)
    addon = _read_text(IGTL_DIR / "soft_addon.md")
    if not base:
        return addon
    if not addon:
        return base
    return f"{base}\n\n---\n\n{addon}".strip()


def load_anti_ai_hard(*, language: str = "ru", max_chars: int = 18000) -> str:
    """Жёсткий pass: локальные правила + IGTL humanizer pack."""
    from .languages import is_cyrillic_language, normalize_language_code

    lang = normalize_language_code(language)
    local = _read_text(PROMPTS_DIR / ANTI_AI_HARD_FILE) or load_anti_ai_style()
    master_raw = _read_text(IGTL_REF / "master-prompt.md")
    master = _adapt_igtl_for_pipeline(_unwrap_fenced_block(master_raw))
    # master уже содержит много списков — ужимаем, чтобы влезли lexicon/markers/rhythm
    if len(master) > 5500:
        master = master[:5500].rstrip() + "\n…[truncated IGTL master]…"
    structure = _adapt_igtl_for_pipeline(
        _read_text(IGTL_REF / "structure-and-rhythm.md")
    )
    checklist = _adapt_igtl_for_pipeline(
        _read_text(IGTL_REF / "self-check-checklist.md")
    )
    lexicon = _adapt_igtl_for_pipeline(_read_text(IGTL_REF / "igaming-lexicon.md"))
    if is_cyrillic_language(lang):
        markers = _adapt_igtl_for_pipeline(_read_text(IGTL_REF / "ru-markers.md"))
        markers_label = "IGTL RU markers"
    else:
        markers = _adapt_igtl_for_pipeline(_read_text(IGTL_REF / "en-markers.md"))
        markers_label = "IGTL EN markers"

    attribution = (
        "IGTL AI-Humanizer pack (CC BY 4.0 © iGamingTextLab) — "
        "https://github.com/igamingtextlab/IGTL-SKILLS. "
        "Judge matches in context; never synonym-swap filler; "
        "replace with a real fact from the brief or delete / `[PLACEHOLDER]`."
    )

    # порядок: lexicon/markers важнее длинного checklist
    sections: list[tuple[str, str, bool]] = [
        ("Attribution", attribution, True),
        ("Local hard rules", local, True),
        ("IGTL master style guide", master, True),
        ("IGTL iGaming lexicon", lexicon, True),
        (markers_label, markers, True),
        ("IGTL structure & rhythm", structure, False),
        ("IGTL self-check", checklist, False),
    ]

    parts: list[str] = []
    used = 0
    for title, body, required in sections:
        body = (body or "").strip()
        if not body:
            continue
        block = f"## {title}\n\n{body}"
        if used + len(block) + 8 > max_chars:
            room = max_chars - used - len(title) - 24
            if room < (800 if required else 400):
                if required:
                    # всё равно втиснуть урезанный обязательный блок
                    room = max(room, 600)
                    if max_chars - used < 650:
                        break
                else:
                    break
            block = f"## {title}\n\n{body[:room].rstrip()}\n…[truncated]…"
        parts.append(block)
        used = sum(len(p) + 8 for p in parts)
        if used >= max_chars:
            break

    pack = "\n\n---\n\n".join(parts).strip()
    if len(pack) > max_chars:
        pack = pack[: max_chars - 20].rstrip() + "\n…[truncated]…"
    return pack


def scan_ai_patterns(text: str) -> list[str]:
    """Эвристики LLM-паттернов для второго прохода (список находок)."""
    raw = text or ""
    found: list[str] = []
    em_count = len(re.findall(r"—", raw))
    for label, pat in _PATTERN_RULES:
        if label == "Em-dash overuse":
            if em_count >= 3:
                found.append(f"{label} ({em_count}×)")
            continue
        hits = pat.findall(raw)
        if hits:
            n = len(hits) if isinstance(hits, list) else 1
            found.append(f"{label} ({n}×)")
    starts: list[str] = []
    for para in re.split(r"\n\s*\n", raw):
        line = next((ln.strip() for ln in para.splitlines() if ln.strip()), "")
        if line.startswith("#"):
            continue
        token = re.split(r"\s+", line, maxsplit=1)[0].lower() if line else ""
        if token:
            starts.append(token)
    for i in range(len(starts) - 2):
        if (
            starts[i] == starts[i + 1] == starts[i + 2]
            and starts[i] not in {"-", "*", "1.", "2."}
        ):
            found.append(f"mirrored paragraph openings («{starts[i]}…» ×3+)")
            break
    return found
