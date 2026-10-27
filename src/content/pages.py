"""Спеки внутренних страниц сайта для стратегии site_page."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

from .store import DATA_DIR, read_json, write_json, slugify, fix_mojibake_deep

PAGES_DIR = DATA_DIR / "pages"

PAGE_VAR_KEYS = (
    "page_id",
    "url",
    "locale",
    "page_type",
    "action",
    "parent_url",
    "primary_job",
    "primary_keyword",
    "secondary_keywords",
    "audience",
    "funnel_stage",
    "must_include",
    "must_exclude",
    "sibling_urls",
    "objections_to_handle",
    "verified_facts",
    "package_excerpts",
    "existing_copy",
    "source_url",
    "length",
    "cta_primary",
    "cta_secondary",
    "tone_shift",
    "output_extra",
)


def pages_dir() -> Path:
    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    return PAGES_DIR


def list_pages() -> list[str]:
    return sorted(p.stem for p in pages_dir().glob("*.json"))


def page_path(page_id: str) -> Path:
    return pages_dir() / f"{slugify(page_id)}.json"


def load_page(page_id: str) -> dict[str, Any]:
    data = read_json(page_path(page_id), default={})
    if not isinstance(data, dict):
        return {}
    fixed, changed = fix_mojibake_deep(data)
    if changed:
        save_page(page_id, fixed)
    return fixed


def save_page(page_id: str, data: dict[str, Any]) -> None:
    data = {**data, "page_id": page_id}
    if not data.get("term"):
        data["term"] = page_id
    write_json(page_path(page_id), data)


def delete_page(page_id: str) -> None:
    path = page_path(page_id)
    if path.exists():
        path.unlink()


_LIST_HEADER_RE = None


def _list_header_re():
    import re

    global _LIST_HEADER_RE
    if _LIST_HEADER_RE is None:
        _LIST_HEADER_RE = re.compile(
            r"(?i)^(pros|cons|advantages|disadvantages|pluses|minuses|"
            r"plus(?:es)?|minus(?:es)?|additional\s*info|key\s*(?:facts|details|info)|"
            r"casino\s*details|details|плюс[ыа]?|минус[ыа]?|"
            r"преимущества|недостатки|дополнительн\w*)\s*:?\s*$"
        )
    return _LIST_HEADER_RE


def normalize_section_list_markup(text: str) -> str:
    """Индентные пункты Pros/Cons → markdown `- `; заголовки списков сохранить."""
    import re

    raw = text or ""
    if not raw.strip():
        return raw
    hdr = _list_header_re()
    out: list[str] = []
    in_list = False
    for ln in raw.splitlines():
        if not ln.strip():
            out.append("")
            continue
        stripped = ln.strip()
        if hdr.match(stripped):
            out.append(stripped.rstrip(":").strip())
            in_list = True
            continue
        if stripped.startswith("#"):
            out.append(stripped)
            in_list = False
            continue
        is_bullet = bool(re.match(r"^([-*•]|\d+[.)])\s+\S", stripped))
        is_indented_item = bool(
            ln.startswith(("    ", "\t")) and 3 <= len(stripped) <= 160
        )
        if in_list or is_bullet or is_indented_item:
            if is_bullet:
                body = re.sub(r"^([-*•]|\d+[.)])\s+", "", stripped)
                out.append(f"- {body}")
            else:
                out.append(f"- {stripped}")
            in_list = True
            continue
        out.append(stripped)
        in_list = False
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()
    return cleaned + ("\n" if raw.endswith("\n") else "")


def set_existing_copy(
    page_id: str,
    text: str,
    *,
    source_url: str = "",
    action: str = "rewrite",
) -> dict[str, Any]:
    """Сохранить существующий текст страницы и пометить action=rewrite."""
    page = load_page(page_id) or empty_page(page_id)
    cleaned = (text or "").strip()
    page["existing_copy"] = cleaned if cleaned else "none"
    if source_url.strip():
        page["source_url"] = source_url.strip()
    elif action == "write" and not cleaned:
        page["source_url"] = ""
    page["action"] = action
    # сбросить устаревший seed — пересоберём из нового текста
    page.pop("structure_seed", None)
    save_page(page_id, page)
    # повторно читаем и сверяем — ловим сбои записи / mojibake-rewrite
    saved = load_page(page_id) or page
    got = str(saved.get("existing_copy") or "")
    expect = cleaned if cleaned else "none"
    if got != expect:
        # принудительно ещё раз без промежуточных мутаций
        saved["existing_copy"] = expect
        save_page(page_id, saved)
        saved = load_page(page_id) or saved
    refresh_structure_seed(page_id)
    return load_page(page_id) or saved


def _norm_heading_key(heading: str) -> str:
    h = re.sub(r"^#+\s*", "", (heading or "").strip())
    h = re.sub(r"[*_`]", "", h)
    h = re.sub(r"\s+", " ", h).strip().lower()
    return h


def _compact_heading_key(heading: str) -> str:
    """Ключ без пробелов/пунктуации — ловит «Brand Name» ↔ «BrandName»."""
    return re.sub(r"[^a-zа-я0-9]+", "", _norm_heading_key(heading), flags=re.I)


_HEADING_STOP = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "your",
        "our",
        "from",
        "into",
        "that",
        "this",
        "how",
        "what",
        "when",
        "which",
        "а",
        "и",
        "на",
        "для",
        "как",
        "что",
        "это",
    }
)


def _heading_tokens(heading: str) -> set[str]:
    key = _norm_heading_key(heading)
    return {
        t
        for t in re.findall(r"[a-zа-я0-9]{3,}", key, flags=re.I)
        if t.lower() not in _HEADING_STOP
    }


def heading_similarity(a: str, b: str) -> float:
    """0..1 сходство заголовков (compact ratio + Jaccard токенов)."""
    from difflib import SequenceMatcher

    ca, cb = _compact_heading_key(a), _compact_heading_key(b)
    if not ca or not cb:
        return 0.0
    if ca == cb:
        return 1.0
    compact = SequenceMatcher(None, ca, cb).ratio()
    ta, tb = _heading_tokens(a), _heading_tokens(b)
    jacc = (len(ta & tb) / len(ta | tb)) if ta and tb else 0.0
    # containment бонус: короче целиком внутри длиннее
    contain = 0.0
    if ca in cb or cb in ca:
        shorter, longer = (ca, cb) if len(ca) <= len(cb) else (cb, ca)
        contain = len(shorter) / max(1, len(longer))
    return max(compact, jacc, contain)


def _extract_copy_headings(text: str) -> list[tuple[int, str]]:
    """Кандидаты заголовков в existing_copy: ## / ### и короткие title-строки."""
    raw = text or ""
    out: list[tuple[int, str]] = []
    pos = 0
    for line in raw.splitlines(keepends=True):
        start = pos
        pos += len(line)
        stripped = line.strip()
        if not stripped or len(stripped) > 120:
            continue
        if stripped.endswith((".", "…", ";", ",")):
            continue
        if stripped.startswith("#"):
            h = re.sub(r"^#+\s*", "", stripped).strip()
            if h and not re.match(r"(?i)^(meta|page job|outline|full draft)\b", h):
                out.append((start, h))
            continue
        # title-like: короткий, без markdown-ссылок-скобок в избытке
        key = _norm_heading_key(stripped)
        if 8 <= len(key) <= 90 and stripped.count("[") < 2:
            # не брать строки из середины абзаца (много слов + lowercase start ok)
            out.append((start, stripped))
    # дедуп по compact-ключу, первая позиция
    seen: set[str] = set()
    uniq: list[tuple[int, str]] = []
    for start, h in out:
        ck = _compact_heading_key(h)
        if not ck or ck in seen:
            continue
        seen.add(ck)
        uniq.append((start, h))
    return uniq


def _find_heading_offset(text: str, heading: str, *, start: int = 0) -> int:
    """Найти позицию заголовка в existing_copy (точный / fuzzy / similarity)."""
    raw = text or ""
    if not raw or not heading.strip():
        return -1
    lower = raw.lower()
    variants = [
        heading.strip(),
        re.sub(r"^#+\s*", "", heading.strip()),
        f"## {heading.strip()}",
        f"### {heading.strip()}",
        f"# {heading.strip()}",
    ]
    best = -1
    for v in variants:
        if not v:
            continue
        idx = lower.find(v.lower(), start)
        if idx >= 0 and (best < 0 or idx < best):
            best = idx
    if best >= 0:
        return best

    target = _norm_heading_key(heading)
    if len(target) < 3:
        return -1
    # построчный fuzzy: строка содержит заголовок или наоборот
    pos = 0
    for line in raw.splitlines(keepends=True):
        line_start = pos
        pos += len(line)
        if line_start < start:
            continue
        key = _norm_heading_key(line)
        if not key or len(key) > 120:
            continue
        if key == target or target in key or key in target:
            if line.strip().endswith((".", "…", ";", ",")):
                continue
            return line_start

    # similarity к известным заголовкам страницы (BrandName ↔ Brand Name и т.п.)
    best_idx = -1
    best_score = 0.0
    for idx, cand in _extract_copy_headings(raw):
        if idx < start:
            continue
        score = heading_similarity(heading, cand)
        if score > best_score:
            best_score = score
            best_idx = idx
    if best_score >= 0.55:
        return best_idx
    return -1


def split_existing_copy_by_sections(
    existing_copy: str, sections: list[dict[str, Any]]
) -> dict[str, str]:
    """Разрезать existing_copy на куски по заголовкам outline-секций.

    Сначала exact/fuzzy offset; если часть секций без матча — жадный
    similarity-матч к заголовкам existing (чтобы переименованный outline
    всё равно подтягивал старый текст).
    """
    raw = (existing_copy or "").strip()
    if not raw or raw.lower() == "none":
        return {}
    active = [s for s in sections if isinstance(s, dict) and not is_section_removed(s)]
    if not active:
        return {}

    by_sid: dict[str, tuple[int, str]] = {}
    used_offsets: set[int] = set()

    # 1) точный / fuzzy поиск
    for sec in active:
        sid = str(sec.get("id") or "")
        heading = str(sec.get("heading") or "").strip()
        if not sid or not heading:
            continue
        idx = _find_heading_offset(raw, heading, start=0)
        if idx < 0:
            continue
        # не делить один offset на две секции
        if idx in used_offsets:
            continue
        by_sid[sid] = (idx, heading)
        used_offsets.add(idx)

    # 2) добить unmatched через bipartite-ish greedy similarity
    copy_heads = _extract_copy_headings(raw)
    unmatched = [
        s
        for s in active
        if str(s.get("id") or "") not in by_sid and str(s.get("heading") or "").strip()
    ]
    if unmatched and copy_heads:
        candidates: list[tuple[float, str, int, str, str]] = []
        for sec in unmatched:
            sid = str(sec.get("id") or "")
            heading = str(sec.get("heading") or "").strip()
            for idx, cand in copy_heads:
                if idx in used_offsets:
                    continue
                score = heading_similarity(heading, cand)
                if score >= 0.55:
                    candidates.append((score, sid, idx, heading, cand))
        candidates.sort(key=lambda x: -x[0])
        taken_sids: set[str] = set(by_sid.keys())
        for score, sid, idx, heading, _cand in candidates:
            if sid in taken_sids or idx in used_offsets:
                continue
            by_sid[sid] = (idx, heading)
            used_offsets.add(idx)
            taken_sids.add(sid)

    if not by_sid:
        return {}

    ordered = sorted(
        ((sid, pos, h) for sid, (pos, h) in by_sid.items()),
        key=lambda x: x[1],
    )

    out: dict[str, str] = {}
    for i, (sid, start, heading) in enumerate(ordered):
        end = ordered[i + 1][1] if i + 1 < len(ordered) else len(raw)
        chunk = raw[start:end].strip()
        if not chunk:
            continue
        lines = chunk.splitlines()
        first = lines[0].strip() if lines else ""
        if first.startswith("#"):
            body = "\n".join(lines[1:]).strip()
            chunk = f"## {heading}\n\n{body}" if body else f"## {heading}\n"
        elif heading_similarity(first, heading) >= 0.55:
            body = "\n".join(lines[1:]).strip()
            chunk = f"## {heading}\n\n{body}" if body else f"## {heading}\n"
        else:
            chunk = f"## {heading}\n\n{chunk}"
        if len(chunk.strip()) >= 20:
            out[sid] = chunk.strip()
    return out


def seed_section_drafts_from_existing(
    page_id: str, *, overwrite: bool = False
) -> dict[str, Any]:
    """Заполнить sections_draft из existing_copy по заголовкам outline.

    Returns: {ok, seeded, skipped, unmatched_sections, matched_ids}
    """
    page = load_page(page_id)
    if not page:
        return {
            "ok": False,
            "seeded": 0,
            "skipped": 0,
            "unmatched_sections": [],
            "matched_ids": [],
            "error": "page not found",
        }
    ec = str(page.get("existing_copy") or "").strip()
    if not ec or ec.lower() == "none":
        return {
            "ok": False,
            "seeded": 0,
            "skipped": 0,
            "unmatched_sections": [],
            "matched_ids": [],
            "error": "existing_copy пуст",
        }
    outline = page.get("outline") or {}
    sections = list(outline.get("sections") or [])
    active = active_sections(page)
    if not active:
        return {
            "ok": False,
            "seeded": 0,
            "skipped": 0,
            "unmatched_sections": [],
            "matched_ids": [],
            "error": "нет активных секций в outline",
        }

    chunks = split_existing_copy_by_sections(ec, sections)
    drafts = dict(page.get("sections_draft") or {})
    seeded = 0
    skipped = 0
    matched_ids: list[str] = []
    for sec in active:
        sid = str(sec.get("id") or "")
        chunk = chunks.get(sid)
        if not chunk:
            continue
        has = bool(str(drafts.get(sid) or "").strip())
        if has and not overwrite:
            skipped += 1
            matched_ids.append(sid)
            continue
        drafts[sid] = normalize_section_list_markup(chunk)
        seeded += 1
        matched_ids.append(sid)
        for s in sections:
            if isinstance(s, dict) and str(s.get("id") or "") == sid:
                if not is_section_removed(s):
                    s["status"] = "done"
                    s["seeded_from_existing"] = True
                break

    unmatched = [
        str(s.get("id"))
        for s in active
        if str(s.get("id") or "") not in matched_ids
    ]
    outline["sections"] = sections
    page["outline"] = outline
    page["sections_draft"] = drafts
    page["action"] = page.get("action") or "rewrite"
    save_page(page_id, page)
    return {
        "ok": True,
        "seeded": seeded,
        "skipped": skipped,
        "unmatched_sections": unmatched,
        "matched_ids": matched_ids,
        "error": "",
    }


def page_to_prompt_vars(page: dict[str, Any]) -> dict[str, str]:
    """Плоские строковые плейсхолдеры {Page_*} и совместимость с {Poker_Term}."""
    out: dict[str, str] = {}
    pid = str(page.get("page_id") or page.get("term") or "page")
    term = str(page.get("term") or pid)
    out["Poker_Term"] = term
    out["Page_Id"] = pid
    out["Page_Term"] = term

    def _as_text(val: Any) -> str:
        if val is None:
            return ""
        if isinstance(val, list):
            return "\n".join(f"- {x}" for x in val)
        return str(val)

    mapping = {
        "Page_Url": "url",
        "Page_Locale": "locale",
        "Page_Type": "page_type",
        "Page_Action": "action",
        "Page_Parent_Url": "parent_url",
        "Page_Primary_Job": "primary_job",
        "Page_Primary_Keyword": "primary_keyword",
        "Page_Secondary_Keywords": "secondary_keywords",
        "Page_Audience": "audience",
        "Page_Funnel_Stage": "funnel_stage",
        "Page_Must_Include": "must_include",
        "Page_Must_Exclude": "must_exclude",
        "Page_Sibling_Urls": "sibling_urls",
        "Page_Objections": "objections_to_handle",
        "Page_Verified_Facts": "verified_facts",
        "Page_Package_Excerpts": "package_excerpts",
        "Page_Existing_Copy": "existing_copy",
        "Page_Source_Url": "source_url",
        "Page_Length": "length",
        "Page_Cta_Primary": "cta_primary",
        "Page_Cta_Secondary": "cta_secondary",
        "Page_Tone_Shift": "tone_shift",
        "Page_Output_Extra": "output_extra",
    }
    for placeholder, key in mapping.items():
        out[placeholder] = _as_text(page.get(key, ""))

    out.setdefault("Page_Locale", "en")
    out.setdefault("Page_Length", "standard")
    out.setdefault("Page_Tone_Shift", "neutral")
    out.setdefault("Page_Action", "rewrite")
    out.setdefault("Page_Output_Extra", "none")
    out.setdefault("Page_Source_Url", "")
    if not out.get("Page_Verified_Facts"):
        out["Page_Verified_Facts"] = "none — use placeholders for numeric or license claims"
    if not out.get("Page_Existing_Copy"):
        out["Page_Existing_Copy"] = "none"

    out["Page_Notes"] = str(page.get("page_notes") or "").strip() or "(none)"
    editor = str(page.get("editor_inputs") or "").strip()
    seed = str(page.get("structure_seed") or "").strip()
    if seed and seed not in editor:
        editor_block = (editor + "\n\n" if editor else "") + "Structure seed:\n" + seed
    else:
        editor_block = editor
    out["Page_Editor_Inputs"] = editor_block or "(none)"
    out["Page_Structure_Seed"] = seed or "(none)"
    out["Page_Research_Brief"] = format_page_research_brief(page)
    outline = page.get("outline") or {}
    out["Page_Outline_Md"] = str(outline.get("raw_md") or "")
    out["Current_Outline_Md"] = current_outline_md_for_enrich(page)
    out["Page_Page_Job"] = str(outline.get("page_job") or page.get("primary_job") or "")
    sections = outline.get("sections") or []
    lines = []
    for i, sec in enumerate(sections, 1):
        if not isinstance(sec, dict):
            continue
        lines.append(
            f"{i}. [{sec.get('id', f's{i}')}] {sec.get('heading', '')} — "
            f"{sec.get('role', '')}"
        )
    out["Page_Outline_Sections"] = "\n".join(lines) if lines else "(no outline yet)"

    drafts = page.get("sections_draft") or {}
    if isinstance(drafts, dict) and drafts:
        parts = []
        for sec in sections:
            if not isinstance(sec, dict):
                continue
            sid = str(sec.get("id") or "")
            body = str(drafts.get(sid) or "").strip()
            if body:
                parts.append(body)
        out["Page_Sections_Assembled"] = "\n\n".join(parts) if parts else "(none yet)"
    else:
        out["Page_Sections_Assembled"] = "(none yet)"

    return out


def empty_page(page_id: str) -> dict[str, Any]:
    return {
        "page_id": page_id,
        "term": page_id,
        "url": "",
        "locale": "en",
        "page_type": "hub",
        "action": "write",
        "parent_url": "",
        "primary_job": "",
        "primary_keyword": "",
        "secondary_keywords": "",
        "audience": "",
        "funnel_stage": "consideration",
        "must_include": [],
        "must_exclude": [],
        "sibling_urls": [],
        "objections_to_handle": "",
        "verified_facts": "none — use placeholders for numeric or license claims",
        "package_excerpts": "",
        "existing_copy": "none",
        "source_url": "",
        "length": "standard",
        "cta_primary": "",
        "cta_secondary": "",
        "tone_shift": "neutral",
        "output_extra": "none",
        "editor_inputs": "",
        "page_notes": "",
        "section_notes": {},
        "section_edit_history": {},
        "structure_seed": "",
        "outline": {},
        "sections_draft": {},
    }


def parse_outline_markdown(raw: str) -> dict[str, Any]:
    """Разбор ответа outline-фазы в структуру outline + список секций."""
    text = (raw or "").strip()
    meta: dict[str, str] = {}
    page_job = ""
    sections: list[dict[str, str]] = []

    for label in ("Title", "Description", "URL", "H1"):
        m = re.search(rf"(?im)^(?:-\s*)?{label}\s*:\s*(.+)$", text)
        if m:
            meta[label.lower()] = m.group(1).strip()

    job_m = re.search(r"(?is)##\s*Page job.*?\n+(.+?)(?=\n##\s|\Z)", text)
    if job_m:
        page_job = job_m.group(1).strip()

    outline_block = text
    om = re.search(r"(?is)##\s*Outline\s*\n(.+?)(?=\n##\s|\Z)", text)
    if om:
        outline_block = om.group(1)

    patterns = [
        re.compile(
            r"(?m)^\s*(?:[-*]|\d+[.)])\s+\*\*(.+?)\*\*\s*[—\-–:]\s*(.+)$"
        ),
        re.compile(r"(?m)^\s*(?:[-*]|\d+[.)])\s+(.+?)\s+[—\-–]\s+(.+)$"),
        re.compile(r"(?m)^\s*(?:[-*]|\d+[.)])\s+(.+)$"),
    ]
    seen: set[str] = set()
    for line in outline_block.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        heading = ""
        role = ""
        for pat in patterns:
            m = pat.match(line)
            if not m:
                continue
            if m.lastindex and m.lastindex >= 2:
                heading, role = m.group(1).strip(), m.group(2).strip()
            else:
                heading = m.group(1).strip()
                role = ""
            break
        if not heading:
            continue
        if re.match(r"(?i)^(title|description|url|h1)\b", heading):
            continue
        key = heading.lower()
        if key in seen:
            continue
        seen.add(key)
        sid = f"s{len(sections) + 1}"
        sections.append(
            {"id": sid, "heading": heading, "role": role, "status": "pending"}
        )

    return {
        "meta": meta,
        "page_job": page_job,
        "sections": sections,
        "raw_md": text,
    }


def extract_headings_md_from_copy(text: str) -> str:
    """Вытащить черновик Outline из existing_copy.

    Приоритет: MD-заголовки; иначе короткие «титульные» строки,
    за которыми сразу идёт абзац (типичный паттерн лендинга).
    """
    raw = (text or "").strip()
    if not raw or raw.lower() == "none":
        return ""

    # Универсальный chrome: логин, юр.блоки, соцсети, типичные футер-якоря.
    # Доменные skip-фразы добавляйте в brief / editor_inputs при необходимости.
    skip_exact = {
        "войти",
        "log in",
        "login",
        "sign in",
        "sign up",
        "ru",
        "en",
        "создать аккаунт",
        "зарегистрироваться",
        "контакты",
        "contact",
        "contacts",
        "legal",
        "о нас",
        "about us",
        "связаться с нами",
        "mail",
        "home",
        "главная",
    }
    skip_re = re.compile(
        r"(?i)все права защищены|политика|cookie|privacy|партнер|"
        r"лицензи|email|whatsapp|telegram|instagram|facebook|"
        r"terms of (use|service)|all rights reserved|"
        r"^\[|^\]|http://|https://"
    )

    headings: list[str] = []
    seen: set[str] = set()

    def _add(h: str) -> bool:
        h = re.sub(r"\s+", " ", h).strip(" \t-–—*#")
        if len(h) < 3 or len(h) > 90:
            return False
        key = h.lower()
        if key in seen or key in skip_exact:
            return False
        if skip_re.search(h):
            return False
        if h.count(".") >= 2 or h.count(",") >= 3:
            return False
        if "/" in h and h.count("/") >= 2:
            return False
        if len(h.split()) > 12:
            return False
        seen.add(key)
        headings.append(h)
        return True

    # 1) явные MD-заголовки
    for line in raw.splitlines():
        m = re.match(r"^#{1,3}\s+(.+)$", line.strip())
        if m:
            _add(m.group(1))
        m = re.match(r"^[-*]\s+\*\*(.+?)\*\*", line.strip())
        if m:
            _add(m.group(1))

    # 2) short title + long paragraph
    if len(headings) < 2:
        lines = [ln.strip() for ln in raw.splitlines()]
        for i, line in enumerate(lines):
            if not line or line.startswith("[") or line.endswith("]"):
                continue
            if len(line) > 70 or line.endswith((".", "…", ";", ":")):
                continue
            letters = sum(ch.isalpha() for ch in line)
            if letters < 3:
                continue
            # следующий непустой — длинный абзац
            nxt = ""
            for j in range(i + 1, min(i + 4, len(lines))):
                if lines[j]:
                    nxt = lines[j]
                    break
            if len(nxt) < 80:
                continue
            _add(line)

    if not headings:
        return ""

    lines_out = ["## Outline (from existing page)"]
    for h in headings[:16]:
        lines_out.append(f"- **{h}** — (уточнить роль / обогатить)")
    return "\n".join(lines_out)


def build_structure_seed(
    page: dict[str, Any], *, prefer_outline: bool = True
) -> str:
    """Черновик MD для шага 2: outline / seed / заголовки из existing_copy + вводные."""
    if prefer_outline:
        outline = page.get("outline") or {}
        if outline.get("raw_md") and outline.get("sections"):
            return str(outline["raw_md"])

    seed = str(page.get("structure_seed") or "").strip()
    if seed:
        return seed

    parts: list[str] = []
    inputs = str(page.get("editor_inputs") or "").strip()
    if inputs:
        parts.append("## Editor notes\n" + inputs)

    ec = str(page.get("existing_copy") or "").strip()
    if ec and ec.lower() != "none":
        extracted = extract_headings_md_from_copy(ec)
        if extracted:
            parts.append(extracted)
        else:
            parts.append(
                "## Outline\n"
                "- **(не удалось вытащить заголовки из existing_copy)** — "
                "вставьте MD вручную или сгенерируйте структуру LLM"
            )

    if parts:
        return "\n\n".join(parts)
    return ""


def refresh_structure_seed(page_id: str) -> str:
    """Пересобрать structure_seed из existing_copy + editor_inputs (игнорируя старый outline)."""
    page = load_page(page_id) or empty_page(page_id)
    page.pop("structure_seed", None)
    seed = build_structure_seed(page, prefer_outline=False)
    page["structure_seed"] = seed
    save_page(page_id, page)
    return seed


def format_page_research_brief(page: dict[str, Any]) -> str:
    """Сводка ресёрча/спеки страницы для enrich-outline и surgical improve."""

    def _as_text(val: Any) -> str:
        if val is None:
            return ""
        if isinstance(val, list):
            return "\n".join(f"- {x}" for x in val) if val else "(none)"
        s = str(val).strip()
        return s if s else "(none)"

    parts = [
        f"primary_job: {_as_text(page.get('primary_job'))}",
        f"audience: {_as_text(page.get('audience'))}",
        f"funnel_stage: {_as_text(page.get('funnel_stage'))}",
        f"primary_keyword: {_as_text(page.get('primary_keyword'))}",
        f"secondary_keywords: {_as_text(page.get('secondary_keywords'))}",
        "must_include:\n" + _as_text(page.get("must_include")),
        "must_exclude:\n" + _as_text(page.get("must_exclude")),
        f"objections: {_as_text(page.get('objections_to_handle'))}",
        f"verified_facts: {_as_text(page.get('verified_facts'))}",
        f"package_excerpts: {_as_text(page.get('package_excerpts'))}",
        f"cta_primary: {_as_text(page.get('cta_primary'))}",
        f"cta_secondary: {_as_text(page.get('cta_secondary'))}",
        f"editor_inputs: {_as_text(page.get('editor_inputs'))}",
        f"page_notes: {_as_text(page.get('page_notes'))}",
    ]
    return "\n\n".join(parts)


def current_outline_md_for_enrich(page: dict[str, Any]) -> str:
    """MD текущей структуры: locked outline → structure_seed → headings from copy."""
    outline = page.get("outline") or {}
    raw = str(outline.get("raw_md") or "").strip()
    if raw and outline.get("sections"):
        return raw
    sections = outline.get("sections") or []
    if sections:
        lines = ["## Outline"]
        for sec in sections:
            if not isinstance(sec, dict) or is_section_removed(sec):
                continue
            h = str(sec.get("heading") or "").strip()
            role = str(sec.get("role") or "").strip() or "(уточнить роль / обогатить)"
            if h:
                lines.append(f"- **{h}** — {role}")
        if len(lines) > 1:
            return "\n".join(lines)
    seed = str(page.get("structure_seed") or "").strip()
    if seed:
        return seed
    built = build_structure_seed(page, prefer_outline=False)
    return built or "(no current outline — build from research + existing_copy)"


def _next_section_id(used: set[str]) -> str:
    n = 1
    while f"s{n}" in used:
        n += 1
    return f"s{n}"


def _match_old_section(
    heading: str, old_sections: list[dict[str, Any]], used_ids: set[str]
) -> Optional[dict[str, Any]]:
    key = _norm_heading_key(heading)
    if not key:
        return None
    # exact
    for sec in old_sections:
        if not isinstance(sec, dict):
            continue
        sid = str(sec.get("id") or "")
        if not sid or sid in used_ids:
            continue
        if _norm_heading_key(str(sec.get("heading") or "")) == key:
            return sec
    # similarity (BrandName ↔ Brand Name, Features ↔ Opportunities…)
    best: Optional[dict[str, Any]] = None
    best_score = 0.0
    for sec in old_sections:
        if not isinstance(sec, dict):
            continue
        sid = str(sec.get("id") or "")
        if not sid or sid in used_ids:
            continue
        score = heading_similarity(heading, str(sec.get("heading") or ""))
        if score > best_score:
            best_score = score
            best = sec
    if best is not None and best_score >= 0.55:
        return best
    return None


def import_outline_md_preserving_drafts(page_id: str, md: str) -> dict[str, Any]:
    """Импорт outline с сохранением драфтов/notes/history по совпадению заголовков."""
    page = load_page(page_id) or empty_page(page_id)
    old_outline = page.get("outline") or {}
    old_sections = [
        s for s in (old_outline.get("sections") or []) if isinstance(s, dict)
    ]
    old_drafts = dict(page.get("sections_draft") or {})
    old_notes = dict(page.get("section_notes") or {})
    old_hist = dict(page.get("section_edit_history") or {})

    outline = parse_outline_markdown(md)
    if not outline.get("sections"):
        # делегируем fallback обычному импорту, затем rematch ниже не сработает
        # на пустом — пусть import_outline_md бросит
        return import_outline_md(page_id, md)

    used_ids: set[str] = set()
    new_sections: list[dict[str, Any]] = []
    new_drafts: dict[str, str] = {}
    new_notes: dict[str, str] = {}
    new_hist: dict[str, Any] = {}
    remapped = 0
    created = 0

    for sec in outline.get("sections") or []:
        if not isinstance(sec, dict):
            continue
        heading = str(sec.get("heading") or "").strip()
        role = str(sec.get("role") or "").strip()
        old = _match_old_section(heading, old_sections, used_ids)
        if old:
            sid = str(old.get("id") or "")
            used_ids.add(sid)
            remapped += 1
            status = "done" if str(old_drafts.get(sid) or "").strip() else "pending"
            entry = {
                "id": sid,
                "heading": heading or str(old.get("heading") or ""),
                "role": role or str(old.get("role") or ""),
                "status": status,
            }
            if old.get("seeded_from_existing"):
                entry["seeded_from_existing"] = True
            if is_section_removed(old):
                entry["status"] = "removed"
                entry["removed"] = True
            new_sections.append(entry)
            if sid in old_drafts:
                new_drafts[sid] = old_drafts[sid]
            if sid in old_notes:
                new_notes[sid] = old_notes[sid]
            if sid in old_hist:
                new_hist[sid] = old_hist[sid]
        else:
            sid = _next_section_id(used_ids)
            used_ids.add(sid)
            created += 1
            new_sections.append(
                {
                    "id": sid,
                    "heading": heading,
                    "role": role,
                    "status": "pending",
                }
            )

    outline["sections"] = new_sections
    page["outline"] = outline
    page["structure_seed"] = md.strip()
    page["sections_draft"] = new_drafts
    page["section_notes"] = new_notes
    page["section_edit_history"] = new_hist
    page["action"] = page.get("action") or "rewrite"
    save_page(page_id, page)

    ec = str(page.get("existing_copy") or "").strip()
    seed_info: dict[str, Any] = {}
    if ec and ec.lower() != "none":
        seed_info = seed_section_drafts_from_existing(page_id, overwrite=False)
        page = load_page(page_id) or page
        outline = page.get("outline") or outline

    outline["_enrich_meta"] = {
        "remapped": remapped,
        "created": created,
        "seeded": seed_info.get("seeded", 0) if seed_info else 0,
    }
    return outline


def preview_editorial_plan(page_id: str) -> dict[str, Any]:
    """Сухой план точечного прохода: что improve / seed / skip — без записи на диск.

    Returns:
      {
        ok, page_id, sections: [
          {id, heading, role, action, action_label, draft_chars, seed_chars,
           matched_existing_heading, will_touch, reason}
        ],
        counts: {improve, seed_then_improve, skip_new, skip_empty, total}
      }
    """
    page = load_page(page_id)
    if not page:
        return {
            "ok": False,
            "page_id": page_id,
            "sections": [],
            "counts": {},
            "error": "page not found",
        }
    ec = str(page.get("existing_copy") or "").strip()
    has_ec = bool(ec and ec.lower() != "none")
    active = active_sections(page)
    drafts = page.get("sections_draft") or {}
    chunks: dict[str, str] = {}
    if has_ec and active:
        chunks = split_existing_copy_by_sections(ec, active)

    # для подписи: какой заголовок existing сматчился
    copy_heads = _extract_copy_headings(ec) if has_ec else []

    rows: list[dict[str, Any]] = []
    counts = {
        "improve": 0,
        "seed_then_improve": 0,
        "skip_new": 0,
        "skip_empty": 0,
        "total": 0,
    }

    for sec in active:
        if not isinstance(sec, dict):
            continue
        sid = str(sec.get("id") or "")
        heading = str(sec.get("heading") or "").strip()
        role = str(sec.get("role") or "").strip()
        draft = str(drafts.get(sid) or "").strip()
        seed = str(chunks.get(sid) or "").strip()
        matched_h = ""
        if seed and copy_heads:
            # ближайший заголовок existing к этой секции
            best_s, best_h = 0.0, ""
            for _idx, cand in copy_heads:
                sc = heading_similarity(heading, cand)
                if sc > best_s:
                    best_s, best_h = sc, cand
            if best_s >= 0.55:
                matched_h = best_h

        if draft and len(draft) >= 40:
            action = "improve"
            label = "improve — правим текущий драфт"
            will_touch = True
            reason = f"есть драфт ({len(draft)} симв.)"
            counts["improve"] += 1
        elif seed and len(seed) >= 40:
            action = "seed_then_improve"
            label = "seed → improve — сначала подтянем existing, потом правка"
            will_touch = True
            reason = (
                f"драфт пуст, но в existing есть кусок ({len(seed)} симв.)"
                + (f" ≈ «{matched_h}»" if matched_h else "")
            )
            counts["seed_then_improve"] += 1
        elif has_ec:
            action = "skip_new"
            label = "пропуск — новая секция (нет в existing)"
            will_touch = False
            reason = "нет драфта и нет матча в existing_copy (NEW из ресёрча)"
            counts["skip_new"] += 1
        else:
            action = "skip_empty"
            label = "пропуск — пусто"
            will_touch = False
            reason = "нет драфта и нет existing_copy"
            counts["skip_empty"] += 1

        counts["total"] += 1
        rows.append(
            {
                "id": sid,
                "heading": heading,
                "role": role,
                "action": action,
                "action_label": label,
                "draft_chars": len(draft),
                "seed_chars": len(seed),
                "matched_existing_heading": matched_h,
                "will_touch": will_touch,
                "reason": reason,
                "default_include": will_touch,
            }
        )

    return {
        "ok": True,
        "page_id": page_id,
        "sections": rows,
        "counts": counts,
        "error": "",
    }


def build_surgical_improve_notes(
    page: dict[str, Any], section: dict[str, Any], draft: str
) -> str:
    """Авто-замечания для точечного improve: роль + пробелы ресёрча + page_notes."""
    sid = str(section.get("id") or "")
    heading = str(section.get("heading") or "").strip()
    role = str(section.get("role") or "").strip()
    draft_l = (draft or "").lower()
    lines = [
        "SURGICAL EDIT — keep existing prose that still fits the role.",
        "Do NOT rewrite the whole section from scratch.",
        "Only: tighten weak sentences, weave in missing research that belongs HERE, cut filler/overlap.",
        f"Section: {sid} · {heading}",
    ]
    if role and "уточнить" not in role.lower():
        lines.append(f"Role to satisfy: {role}")
    else:
        lines.append(
            "Role is weak/placeholder — infer a concrete job from page research "
            "and advance only that job."
        )

    must = page.get("must_include") or []
    if isinstance(must, list) and must:
        missing: list[str] = []
        for item in must:
            text = str(item).strip()
            if not text:
                continue
            tokens = [
                t
                for t in re.findall(r"[A-Za-zА-Яа-я0-9/+-]{4,}", text.lower())
                if t
                not in {
                    "with",
                    "from",
                    "that",
                    "this",
                    "when",
                    "than",
                    "have",
                    "link",
                    "page",
                    "poker",
                }
            ]
            if not tokens:
                continue
            hits = sum(1 for t in tokens if t in draft_l)
            if hits < max(1, len(tokens) // 2):
                missing.append(text)
        if missing:
            lines.append(
                "Page research points possibly missing from THIS draft "
                "(add only if they belong to this role; otherwise skip):"
            )
            for m in missing[:8]:
                lines.append(f"- {m}")

    objections = str(page.get("objections_to_handle") or "").strip()
    if objections and objections.lower() not in ("none", "(none)"):
        # если в драфте почти нет следов возражений — напомнить
        obj_tokens = re.findall(r"[A-Za-zА-Яа-я]{4,}", objections.lower())
        if obj_tokens and sum(1 for t in obj_tokens[:6] if t in draft_l) < 2:
            lines.append(
                f"Objections to handle if this section owns them: {objections}"
            )

    siblings = page.get("sibling_urls") or []
    if isinstance(siblings, list) and siblings:
        sib_txt = ", ".join(str(x) for x in siblings if str(x).strip())
        if sib_txt:
            lines.append(
                f"Keep sibling links where relevant (do not steal their jobs): {sib_txt}"
            )

    existing_notes = get_section_notes(page, sid)
    if existing_notes:
        lines.append("Editor section notes (mandatory):")
        lines.append(existing_notes)

    page_notes = str(page.get("page_notes") or "").strip()
    if page_notes:
        lines.append(f"Page notes (apply if relevant): {page_notes}")

    editor = str(page.get("editor_inputs") or "").strip()
    if editor:
        lines.append(f"Editor inputs (global): {_clip_history_text(editor, 400)}")

    return "\n".join(lines)


def import_outline_md(page_id: str, md: str) -> dict[str, Any]:
    """Принять готовый MD (Meta/Outline или список заголовков) → сохранить outline."""
    page = load_page(page_id) or empty_page(page_id)
    outline = parse_outline_markdown(md)
    if not outline.get("sections"):
        # fallback: строки ## Heading или - Heading без role
        sections: list[dict[str, str]] = []
        for line in (md or "").splitlines():
            line = line.strip()
            m = re.match(r"^#{1,3}\s+(.+)$", line)
            if m:
                h = m.group(1).strip()
                if re.match(r"(?i)^(meta|page job|outline|full draft)\b", h):
                    continue
                sections.append(
                    {
                        "id": f"s{len(sections) + 1}",
                        "heading": h,
                        "role": "",
                        "status": "pending",
                    }
                )
                continue
            m2 = re.match(r"^[-*]\s+\*\*(.+?)\*\*", line) or re.match(
                r"^[-*]\s+(.+)$", line
            )
            if m2:
                h = m2.group(1).strip()
                if "—" in h or " - " in h:
                    parts = re.split(r"\s+[—\-]\s+", h, maxsplit=1)
                    h, role = parts[0], (parts[1] if len(parts) > 1 else "")
                else:
                    role = ""
                sections.append(
                    {
                        "id": f"s{len(sections) + 1}",
                        "heading": h.strip("* "),
                        "role": role,
                        "status": "pending",
                    }
                )
        if sections:
            outline = {
                "meta": outline.get("meta") or {},
                "page_job": outline.get("page_job") or page.get("primary_job") or "",
                "sections": sections,
                "raw_md": md.strip(),
            }
    if not outline.get("sections"):
        raise ValueError(
            "Не нашёл секции. Нужен блок ## Outline с `- **Heading** — role` "
            "или список `## Heading` / `- Heading`."
        )
    page["outline"] = outline
    save_page(page_id, page)
    # если есть existing_copy — сразу разложить по секциям для точечного improve
    ec = str(page.get("existing_copy") or "").strip()
    if ec and ec.lower() != "none":
        seed_section_drafts_from_existing(page_id, overwrite=False)
        page = load_page(page_id) or page
        outline = page.get("outline") or outline
    return outline


def get_section_notes(page: dict[str, Any], section_id: str) -> str:
    notes = page.get("section_notes") or {}
    if isinstance(notes, dict):
        return str(notes.get(section_id) or "").strip()
    return ""


def set_section_notes(page_id: str, section_id: str, text: str) -> None:
    page = load_page(page_id) or empty_page(page_id)
    notes = dict(page.get("section_notes") or {})
    cleaned = (text or "").strip()
    if cleaned:
        notes[section_id] = cleaned
    elif section_id in notes:
        del notes[section_id]
    page["section_notes"] = notes
    save_page(page_id, page)


def _clip_history_text(text: str, max_chars: int = 500) -> str:
    t = (text or "").strip()
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 20].rstrip() + "\n…[truncated]…"


def get_section_edit_history(
    page: dict[str, Any], section_id: str
) -> list[dict[str, Any]]:
    hist = page.get("section_edit_history") or {}
    if not isinstance(hist, dict):
        return []
    items = hist.get(section_id) or []
    return [x for x in items if isinstance(x, dict)]


def clear_section_edit_history(
    page_id: str, section_id: Optional[str] = None
) -> None:
    """Сбросить историю одной секции или всей страницы."""
    page = load_page(page_id) or empty_page(page_id)
    if section_id is None:
        page["section_edit_history"] = {}
    else:
        hist = dict(page.get("section_edit_history") or {})
        if section_id in hist:
            del hist[section_id]
        page["section_edit_history"] = hist
    save_page(page_id, page)


def append_section_revision(
    page_id: str,
    section_id: str,
    *,
    action: str,
    before: str,
    after: str,
    model: str = "",
    notes: str = "",
    patterns: Optional[list[str]] = None,
    max_keep: int = 5,
) -> None:
    """Записать один проход правки (before→after) в историю секции."""
    from datetime import datetime, timezone

    page = load_page(page_id) or empty_page(page_id)
    hist = dict(page.get("section_edit_history") or {})
    items = list(hist.get(section_id) or [])
    before_s = (before or "").strip()
    after_s = (after or "").strip()
    if not before_s and not after_s:
        return
    if before_s == after_s:
        return
    entry = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "action": (action or "rewrite").strip()[:40],
        "model": (model or "").strip()[:80],
        "before": _clip_history_text(before_s, 520),
        "after": _clip_history_text(after_s, 520),
        "notes": _clip_history_text((notes or "").strip(), 240),
        "patterns": [str(p)[:120] for p in (patterns or [])[:8]],
    }
    items.append(entry)
    if len(items) > max_keep:
        items = items[-max_keep:]
    hist[section_id] = items
    page["section_edit_history"] = hist
    save_page(page_id, page)


def format_section_edit_history(
    page: dict[str, Any],
    section_id: str,
    *,
    max_passes: int = 5,
    max_total_chars: int = 2800,
) -> str:
    """Текст истории для промпта: не ходить по кругу."""
    items = get_section_edit_history(page, section_id)
    if not items:
        return "(none — first edit pass for this section)"
    recent = items[-max_passes:]
    blocks: list[str] = [
        "Recent edit passes on THIS section. Do NOT undo them or restore "
        "rejected openings/transitions from Before excerpts. Prefer a new "
        "direction; if stuck, cut filler rather than synonym-cycling."
    ]
    for i, e in enumerate(recent, start=1):
        n = len(items) - len(recent) + i
        pats = e.get("patterns") or []
        pats_txt = ", ".join(str(p) for p in pats) if pats else "(none recorded)"
        notes = str(e.get("notes") or "").strip() or "(none)"
        blocks.append(
            f"### Pass {n} · {e.get('action') or 'rewrite'}"
            f" · {e.get('model') or '?'} · {e.get('ts') or ''}\n"
            f"Patterns before: {pats_txt}\n"
            f"Notes used: {notes}\n"
            f"Before (excerpt):\n{e.get('before') or '(empty)'}\n\n"
            f"After (excerpt):\n{e.get('after') or '(empty)'}"
        )
    out = "\n\n".join(blocks)
    if len(out) > max_total_chars:
        out = out[: max_total_chars - 20].rstrip() + "\n…[truncated]…"
    return out


def is_section_removed(sec: dict[str, Any]) -> bool:
    if not isinstance(sec, dict):
        return False
    if bool(sec.get("removed")):
        return True
    return str(sec.get("status") or "").strip().lower() in {
        "removed",
        "deleted",
        "dropped",
    }


def active_sections(page: dict[str, Any]) -> list[dict[str, Any]]:
    """Секции outline без удалённых (для генерации / сборки / coverage)."""
    outline = page.get("outline") or {}
    return [
        s
        for s in (outline.get("sections") or [])
        if isinstance(s, dict) and not is_section_removed(s)
    ]


def section_status(page: dict[str, Any], section_id: str) -> str:
    outline = page.get("outline") or {}
    for sec in outline.get("sections") or []:
        if isinstance(sec, dict) and sec.get("id") == section_id:
            if is_section_removed(sec):
                return "removed"
            break
    drafts = page.get("sections_draft") or {}
    body = str(drafts.get(section_id) or "").strip()
    if len(body) >= 80:
        return "done"
    for sec in outline.get("sections") or []:
        if isinstance(sec, dict) and sec.get("id") == section_id:
            return str(sec.get("status") or "pending")
    return "pending"


def remove_section(
    page_id: str, section_id: str, *, drop_draft: bool = False
) -> bool:
    """Пометить секцию удалённой (не попадает в assemble / generate_all)."""
    page = load_page(page_id)
    if not page:
        return False
    outline = dict(page.get("outline") or {})
    sections = list(outline.get("sections") or [])
    found = False
    for sec in sections:
        if not isinstance(sec, dict):
            continue
        if str(sec.get("id") or "") != section_id:
            continue
        sec["removed"] = True
        sec["status"] = "removed"
        found = True
        break
    if not found:
        return False
    outline["sections"] = sections
    page["outline"] = outline
    if drop_draft:
        drafts = dict(page.get("sections_draft") or {})
        drafts.pop(section_id, None)
        page["sections_draft"] = drafts
    save_page(page_id, page)
    return True


def restore_section(page_id: str, section_id: str) -> bool:
    """Вернуть удалённую секцию в активный outline."""
    page = load_page(page_id)
    if not page:
        return False
    outline = dict(page.get("outline") or {})
    sections = list(outline.get("sections") or [])
    found = False
    for sec in sections:
        if not isinstance(sec, dict):
            continue
        if str(sec.get("id") or "") != section_id:
            continue
        sec.pop("removed", None)
        drafts = page.get("sections_draft") or {}
        body = str(drafts.get(section_id) or "").strip()
        sec["status"] = "done" if len(body) >= 80 else "pending"
        found = True
        break
    if not found:
        return False
    outline["sections"] = sections
    page["outline"] = outline
    save_page(page_id, page)
    return True
