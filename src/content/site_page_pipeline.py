"""Посекционный пайплайн для стратегии site_page: outline → section → assemble."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from ..llm import (
    LLMClient,
    LLMConfig,
    ensemble_partner_config,
    load_settings,
)
from . import pages as pages_mod
from . import strategies as strategies_mod
from .languages import DEFAULT_LANGUAGE
from .prompt_store import build_messages_for_term, load_prompt, render_prompt
from .store import GUIDES_DIR, content_stem

ProgressCb = Callable[[str], None]


@dataclass
class SitePageResult:
    ok: bool
    page_id: str
    phase: str = ""
    text: str = ""
    path: Optional[Path] = None
    error: str = ""
    sections: list[dict] = field(default_factory=list)


def _strategy() -> dict:
    st = strategies_mod.get_strategy("site_page")
    if not st:
        raise RuntimeError("Стратегия site_page не найдена")
    return st


def _phase_prompt_files(strategy: dict, phase: str) -> tuple[str, str]:
    phases = strategy.get("phase_prompts") or {}
    spec = phases.get(phase) or {}
    if phase == "full" or not spec:
        return (
            str(strategy.get("system_prompt") or "site_page_system.md"),
            str(strategy.get("user_prompt") or "site_page_user.md"),
        )
    return (
        str(spec.get("system") or strategy.get("system_prompt")),
        str(spec.get("user") or strategy.get("user_prompt")),
    )


def build_site_page_messages(
    page_id: str,
    *,
    phase: str = "full",
    language: str = DEFAULT_LANGUAGE,
    section: Optional[dict[str, Any]] = None,
    section_mode: str = "write",
    extra_vars: Optional[dict[str, str]] = None,
) -> dict[str, str]:
    """Собрать system/user для фазы full | outline | section."""
    strategy = _strategy()
    page = pages_mod.load_page(page_id)
    if not page:
        raise RuntimeError(f"Page not found: {page_id}")

    # Рабочая копия: для section/antia_pass не тащим весь сырой скрейп
    page_ctx = dict(page)
    if phase in (
        "section",
        "antia_pass",
        "zerogpt_fix",
        "sentence_step",
        "paragraph_step",
    ):
        page_ctx["existing_copy"] = _section_existing_excerpt(page, section)
        page_ctx["structure_seed"] = ""
        outline = dict(page_ctx.get("outline") or {})
        if outline.get("raw_md") and len(str(outline["raw_md"])) > 2500:
            outline["raw_md"] = _clip(str(outline["raw_md"]), 2500)
        page_ctx["outline"] = outline
        page_ctx["editor_inputs"] = _clip(str(page.get("editor_inputs") or ""), 1200)
    elif phase == "enrich_outline":
        # для обогащения структуры — усечённый existing + явный current outline
        page_ctx["existing_copy"] = _clip(str(page.get("existing_copy") or ""), 6000)
        page_ctx["structure_seed"] = _clip(str(page.get("structure_seed") or ""), 2500)

    sys_file, user_file = _phase_prompt_files(strategy, phase)
    phased = {**strategy, "system_prompt": sys_file, "user_prompt": user_file}

    vars_extra: dict[str, str] = dict(extra_vars or {})
    if phase == "enrich_outline":
        vars_extra.setdefault(
            "Current_Outline_Md",
            pages_mod.current_outline_md_for_enrich(page),
        )
        vars_extra.setdefault(
            "Page_Research_Brief",
            pages_mod.format_page_research_brief(page),
        )
    if phase in (
        "section",
        "antia_pass",
        "zerogpt_fix",
        "sentence_step",
        "paragraph_step",
    ) and section:
        from .anti_ai import load_anti_ai_hard, scan_ai_patterns

        sid = str(section.get("id") or "")
        drafts = page.get("sections_draft") or {}
        prev_full = str(drafts.get(sid) or "").strip()
        prev = _clip(
            prev_full,
            4500 if phase == "zerogpt_fix" else (3500 if phase == "antia_pass" else 2500),
        )
        if phase in ("sentence_step", "paragraph_step"):
            # для next-sentence / next-paragraph используем Written_So_Far из extra_vars
            prev = vars_extra.get("Written_So_Far") or prev
        sec_list = pages_mod.active_sections(page)
        idx = next(
            (i for i, s in enumerate(sec_list) if s.get("id") == sid),
            -1,
        )
        # ближайший предыдущий блок — чуть полнее для стыка
        immediate_prev = ""
        if idx > 0:
            prev_sid = str(sec_list[idx - 1].get("id") or "")
            prev_body = str(drafts.get(prev_sid) or "").strip()
            if prev_body:
                immediate_prev = (
                    f"[{prev_sid}] {sec_list[idx - 1].get('heading', '')}\n"
                    + _clip(prev_body, 900)
                )
        prior_coverage = build_prior_sections_coverage(page, sid)
        later_jobs = build_later_section_jobs(page, sid)
        outline_lines = []
        for s in sec_list:
            mark = "→" if s.get("id") == sid else " "
            outline_lines.append(
                f"{mark} [{s.get('id')}] {s.get('heading', '')}"
                + (f" — {s.get('role')}" if s.get("role") else "")
            )
        detected = scan_ai_patterns(prev_full) if phase == "antia_pass" else []
        detected_txt = (
            "\n".join(f"- {x}" for x in detected)
            if detected
            else "- (эвристики ничего явного не нашли — всё равно ужесточи ритм и убери пену)"
        )
        zg_highlights = vars_extra.get("ZeroGPT_Highlights") or "(none)"
        sec_notes = pages_mod.get_section_notes(page, sid).strip()
        vars_extra.update(
            {
                "Section_Id": sid,
                "Section_Heading": str(section.get("heading") or ""),
                "Section_Role": str(section.get("role") or ""),
                "Section_Mode": section_mode,
                "Section_Previous_Draft": prev if prev else "(none)",
                "Section_Notes": sec_notes or "(none)",
                # legacy key = полная карта prior (не только ±1 сосед)
                "Page_Neighbor_Sections": prior_coverage,
                "Prior_Sections_Coverage": prior_coverage,
                "Immediate_Previous_Section": immediate_prev or "(none)",
                "Later_Section_Jobs": later_jobs,
                "Page_Outline_Md": "\n".join(outline_lines) or "(none)",
                "Detected_AI_Patterns": detected_txt,
                "Anti_AI_Hard": load_anti_ai_hard(language=language),
                "ZeroGPT_Highlights": zg_highlights,
                "Written_So_Far": vars_extra.get("Written_So_Far")
                or "(empty — write the opening)",
                "Sentence_Index": vars_extra.get("Sentence_Index") or "0",
                "Temp_Hint": vars_extra.get("Temp_Hint") or "medium",
                "Paragraph_Index": vars_extra.get("Paragraph_Index") or "0",
                "Ensemble_Model": vars_extra.get("Ensemble_Model") or "(primary)",
                "Ensemble_Hint": vars_extra.get("Ensemble_Hint")
                or "alternate voice vs previous paragraph",
                "Target_Paragraph": vars_extra.get("Target_Paragraph") or "(none)",
                "Edit_History": pages_mod.format_section_edit_history(
                    page, sid
                ),
            }
        )
        # если в extra_vars уже передали свежие notes (из UI) — они побеждают
        if (extra_vars or {}).get("Section_Notes"):
            vars_extra["Section_Notes"] = str(extra_vars["Section_Notes"]).strip() or "(none)"
    page_notes_val = str(page.get("page_notes") or "").strip() or "(none)"
    if (extra_vars or {}).get("Page_Notes"):
        page_notes_val = str(extra_vars["Page_Notes"]).strip() or "(none)"
    vars_extra["Page_Notes"] = page_notes_val
    editor = str(page.get("editor_inputs") or "").strip()
    seed = str(page.get("structure_seed") or "").strip()
    if phase in (
        "section",
        "antia_pass",
        "zerogpt_fix",
        "sentence_step",
        "paragraph_step",
    ):
        editor = _clip(editor, 1200)
        seed = ""
    if seed and seed not in editor:
        editor_block = (editor + "\n\n" if editor else "") + "Structure seed:\n" + _clip(
            seed, 2000
        )
    else:
        editor_block = editor
    vars_extra.setdefault("Page_Editor_Inputs", editor_block or "(none)")

    msgs = build_messages_for_term(
        phased,
        page_id,
        language=language,
        page=page_ctx,
        extra_vars=vars_extra,
    )
    # хвост-якорь: селектор языка побеждает existing_copy / русский outline
    from .languages import get_language, is_latin_script_language

    opt = get_language(language)
    lang_tail = (
        f"\n\n## FINAL LANGUAGE CHECK\n"
        f"Selector language = **{opt['name_en']}** (`{opt['code']}` / {opt['label']}).\n"
        f"Write the entire answer in {opt['name_en']}. "
        f"Russian/Cyrillic source material is reference only — translate, do not mirror.\n"
    )
    if is_latin_script_language(opt["code"]):
        lang_tail += (
            f"If your draft contains Cyrillic paragraphs, rewrite them into "
            f"{opt['name_en']} before returning.\n"
        )
    msgs["user"] = (msgs.get("user") or "") + lang_tail

    # anti-overlap якорь в конце (recency) для посекционной генерации
    if phase in ("section", "paragraph_step", "antia_pass", "sentence_step"):
        prior = str(vars_extra.get("Prior_Sections_Coverage") or "").strip()
        later = str(vars_extra.get("Later_Section_Jobs") or "").strip()
        if prior and not prior.startswith("(none"):
            msgs["user"] = (
                (msgs.get("user") or "")
                + "\n\n## HARD ANTI-OVERLAP\n"
                "Do not restate claims already covered in Prior_Sections_Coverage. "
                "Advance only this section's role. "
                "If you were about to redefine / re-pitch / re-list the same benefits — delete that.\n"
            )
            if later and not later.startswith("(none"):
                msgs["user"] += (
                    "Do not cover Later_Section_Jobs here either.\n"
                )

    # замечания редактора — в самом конце (recency), иначе их топят anti-AI / existing_copy
    sn = str(vars_extra.get("Section_Notes") or "").strip()
    pn = str(vars_extra.get("Page_Notes") or "").strip()
    notes_bits: list[str] = []
    if sn and sn != "(none)":
        notes_bits.append(f"SECTION NOTES (mandatory for this section):\n{sn}")
    if pn and pn != "(none)":
        notes_bits.append(f"PAGE NOTES (apply if relevant to this section):\n{pn}")
    if notes_bits and phase in (
        "section",
        "antia_pass",
        "zerogpt_fix",
        "sentence_step",
        "paragraph_step",
        "outline",
        "enrich_outline",
        "full",
    ):
        msgs["user"] = (
            (msgs.get("user") or "")
            + "\n\n## HARD EDITOR NOTES — obey these over generic style rules\n"
            + "\n\n".join(notes_bits)
            + "\n\nDo not ignore the notes above. If a note conflicts with filler style, "
            "follow the note. Keep facts accurate; do not invent numbers.\n"
        )
        msgs["system"] = (
            (msgs.get("system") or "")
            + "\n\nEDITOR NOTES OVERRIDE: if the user message includes HARD EDITOR NOTES, "
            "those instructions outrank generic anti-AI / style guidance for this call.\n"
        )
    return msgs


def _clip(text: str, max_chars: int) -> str:
    t = (text or "").strip()
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 20].rstrip() + "\n…[truncated]…"


def _compress_section_for_coverage(text: str, *, max_chars: int = 420) -> str:
    """Сжатая выжимка секции: заголовок + первые фразы абзацев / пункты списков."""
    import re

    raw = (text or "").strip()
    if not raw:
        return ""
    lines = raw.splitlines()
    bits: list[str] = []
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        if s.startswith("#"):
            bits.append(s)
            continue
        if s.startswith(("-", "*", "•")) or re.match(r"^\d+[.)]\s+", s):
            bits.append(s[:160])
            continue
        # первая фраза абзаца
        m = re.match(r"^(.+?[.!?])(?:\s|$)", s)
        bits.append((m.group(1) if m else s)[:180])
    out = " | ".join(bits)
    return _clip(out, max_chars)


def build_prior_sections_coverage(
    page: dict[str, Any],
    section_id: str,
    *,
    max_total_chars: int = 3200,
    per_section_chars: int = 420,
) -> str:
    """Все УЖЕ написанные (активные) секции до текущей — для anti-overlap."""
    sec_list = pages_mod.active_sections(page)
    drafts = page.get("sections_draft") or {}
    idx = next(
        (i for i, s in enumerate(sec_list) if str(s.get("id") or "") == section_id),
        -1,
    )
    if idx <= 0:
        return "(none yet — this is the first section; still stay inside your role)"

    blocks: list[str] = [
        "ALREADY WRITTEN earlier on this page. Treat as covered ground: "
        "do NOT restate the same claims, definitions, benefits, or CTA pitch. "
        "One short bridge back-reference is OK; a second explanation is not."
    ]
    total = 0
    for s in sec_list[:idx]:
        sid = str(s.get("id") or "")
        body = str(drafts.get(sid) or "").strip()
        if not body:
            continue
        heading = str(s.get("heading") or sid)
        role = str(s.get("role") or "").strip()
        compressed = _compress_section_for_coverage(
            body, max_chars=per_section_chars
        )
        block = (
            f"### [{sid}] {heading}\n"
            f"role: {role or '—'}\n"
            f"covered: {compressed}"
        )
        if total + len(block) > max_total_chars:
            blocks.append("…[earlier sections truncated]…")
            break
        blocks.append(block)
        total += len(block)
    if len(blocks) == 1:
        return "(none yet — prior outline slots have no drafts)"
    return "\n\n".join(blocks)


def build_later_section_jobs(
    page: dict[str, Any], section_id: str
) -> str:
    """Роли следующих активных секций — чтобы текущая не воровала их смысл."""
    sec_list = pages_mod.active_sections(page)
    idx = next(
        (i for i, s in enumerate(sec_list) if str(s.get("id") or "") == section_id),
        -1,
    )
    if idx < 0 or idx >= len(sec_list) - 1:
        return "(none — last section; still avoid rehashing prior coverage)"
    lines: list[str] = [
        "LATER sections own these jobs — do NOT cover them here "
        "(leave hooks at most, no full explanation):"
    ]
    for s in sec_list[idx + 1 :]:
        sid = str(s.get("id") or "")
        heading = str(s.get("heading") or sid)
        role = str(s.get("role") or "").strip() or "—"
        lines.append(f"- [{sid}] {heading} — {role}")
    return "\n".join(lines)


def scan_cross_section_overlap(
    draft: str,
    page: dict[str, Any],
    section_id: str,
    *,
    min_shingle: int = 6,
) -> list[str]:
    """Грубые пересечения текущей секции с уже написанными (для UI)."""
    import re

    def norm_words(text: str) -> list[str]:
        t = (text or "").lower()
        t = re.sub(r"[#*`\[\]()\"']", " ", t)
        return [w for w in re.split(r"[^\wа-яё]+", t, flags=re.I) if len(w) > 2]

    def shingles(words: list[str], n: int) -> set[str]:
        if len(words) < n:
            return set()
        return {" ".join(words[i : i + n]) for i in range(len(words) - n + 1)}

    cur = norm_words(draft)
    if len(cur) < min_shingle:
        return []
    cur_set = shingles(cur, min_shingle)
    sec_list = pages_mod.active_sections(page)
    drafts = page.get("sections_draft") or {}
    idx = next(
        (i for i, s in enumerate(sec_list) if str(s.get("id") or "") == section_id),
        -1,
    )
    hits: list[str] = []
    for s in sec_list[: max(idx, 0)]:
        sid = str(s.get("id") or "")
        if sid == section_id:
            continue
        body = str(drafts.get(sid) or "").strip()
        if not body:
            continue
        overlap = cur_set & shingles(norm_words(body), min_shingle)
        if len(overlap) >= 2:
            sample = next(iter(overlap))
            hits.append(
                f"перекрытие с [{sid}] {s.get('heading')}: «{sample}…» "
                f"(×{len(overlap)} совп.)"
            )
        elif len(overlap) == 1:
            sample = next(iter(overlap))
            hits.append(
                f"возможный повтор с [{sid}] {s.get('heading')}: «{sample}…»"
            )
    return hits[:6]


def _section_existing_excerpt(
    page: dict[str, Any], section: Optional[dict[str, Any]], *, max_chars: int = 2800
) -> str:
    """Кусок existing_copy для секции: предпочтительно точный слайс по заголовку."""
    raw = str(page.get("existing_copy") or "").strip()
    if not raw or raw.lower() == "none":
        return "none"
    sid = str((section or {}).get("id") or "")
    # 1) уже посеянный драфт этой секции (лучший источник для improve)
    drafts = page.get("sections_draft") or {}
    seeded = str(drafts.get(sid) or "").strip()
    if seeded and len(seeded) >= 40:
        return _clip(seeded, max_chars)
    # 2) разрез existing_copy по outline
    if section:
        chunks = pages_mod.split_existing_copy_by_sections(
            raw, (page.get("outline") or {}).get("sections") or []
        )
        if sid and chunks.get(sid):
            return _clip(chunks[sid], max_chars)
        heading = str(section.get("heading") or "").strip()
        if heading:
            idx = pages_mod._find_heading_offset(raw, heading, start=0)
            if idx >= 0:
                # до следующего вероятного H2/короткого заголовка или max_chars
                chunk = raw[idx : idx + max_chars]
                return chunk if idx == 0 else "…\n" + chunk
    # 3) fallback: начало основного текста
    lines = raw.splitlines()
    body_start = 0
    for i, ln in enumerate(lines):
        if len(ln.strip()) > 100:
            body_start = i
            break
    joined = "\n".join(lines[body_start:])
    return _clip(joined, max_chars) or "none"


def _chunk_text_for_clean(text: str, *, max_chars: int = 12000) -> list[str]:
    """Режем длинный скрейп на куски по абзацам/заголовкам."""
    raw = (text or "").strip()
    if not raw:
        return []
    if len(raw) <= max_chars:
        return [raw]
    parts = raw.split("\n\n")
    chunks: list[str] = []
    buf = ""
    for part in parts:
        candidate = (buf + "\n\n" + part).strip() if buf else part
        if len(candidate) <= max_chars:
            buf = candidate
            continue
        if buf:
            chunks.append(buf)
        if len(part) <= max_chars:
            buf = part
        else:
            # жёсткий разрез сверхдлинного куска
            for i in range(0, len(part), max_chars):
                chunks.append(part[i : i + max_chars])
            buf = ""
    if buf:
        chunks.append(buf)
    return chunks


def clean_existing_copy(
    page_id: str,
    *,
    client: Optional[LLMClient] = None,
    config: Optional[LLMConfig] = None,
    progress: Optional[ProgressCb] = None,
    chunk_chars: int = 12000,
) -> SitePageResult:
    """LLM: убрать меню/футер/chrome, сохранить весь основной текст."""

    def log(msg: str) -> None:
        if progress:
            progress(msg)

    try:
        page = pages_mod.load_page(page_id)
        if not page:
            return SitePageResult(
                ok=False, page_id=page_id, phase="clean_copy", error="page not found"
            )
        raw = str(page.get("existing_copy") or "").strip()
        if not raw or raw.lower() == "none":
            return SitePageResult(
                ok=False,
                page_id=page_id,
                phase="clean_copy",
                error="existing_copy пуст",
            )

        cfg = config or load_settings()
        llm = client or LLMClient(cfg)
        strategy = _strategy()
        sys_file, user_file = _phase_prompt_files(strategy, "clean_copy")
        system = load_prompt(sys_file) or (
            "Remove nav/footer chrome. Keep full main content. Output cleaned text only."
        )
        user_tmpl = load_prompt(user_file) or (
            "Source: {Source_Url}\n\n{Raw_Copy}\n"
        )
        source_url = str(page.get("source_url") or page.get("url") or "")

        # sidecar до очистки
        pre_path = guide_path_for_page(
            page_id, language=DEFAULT_LANGUAGE, suffix=".existing_pre_clean"
        )
        pre_path.parent.mkdir(parents=True, exist_ok=True)
        pre_path.write_text(raw, encoding="utf-8")

        chunks = _chunk_text_for_clean(raw, max_chars=chunk_chars)
        cleaned_parts: list[str] = []
        log(f"{page_id}: clean existing_copy ({len(raw)}c → {len(chunks)} chunk(s))…")
        for i, chunk in enumerate(chunks):
            log(f"clean chunk {i + 1}/{len(chunks)} ({len(chunk)}c)")
            user = render_prompt(
                user_tmpl,
                poker_term=str(page.get("term") or page_id),
                Source_Url=source_url or "(none)",
                Raw_Copy=chunk,
            )
            part = _chat(
                llm,
                {"system": system, "user": user},
                temperature=0.2,
                max_tokens=min(8192, int(getattr(cfg, "max_tokens", 4096) or 4096)),
                thinking_enabled=False,
            ).strip()
            if part:
                cleaned_parts.append(part)

        cleaned = "\n\n".join(cleaned_parts).strip()
        if len(cleaned) < 80:
            return SitePageResult(
                ok=False,
                page_id=page_id,
                phase="clean_copy",
                error="LLM вернул слишком короткий текст после очистки",
                text=cleaned,
            )

        pages_mod.set_existing_copy(
            page_id,
            cleaned,
            source_url=source_url,
            action=str(page.get("action") or "rewrite"),
        )
        log(
            f"{page_id}: existing_copy cleaned "
            f"{len(raw)} → {len(cleaned)} chars (pre=`{pre_path.name}`)"
        )
        return SitePageResult(
            ok=True,
            page_id=page_id,
            phase="clean_copy",
            text=cleaned,
            path=pre_path,
        )
    except Exception as exc:  # noqa: BLE001
        return SitePageResult(
            ok=False, page_id=page_id, phase="clean_copy", error=str(exc)
        )


def guide_path_for_page(
    page_id: str, *, language: str = DEFAULT_LANGUAGE, suffix: str = ""
) -> Path:
    strategy = _strategy()
    page = pages_mod.load_page(page_id) or {}
    term = str(page.get("term") or page_id)
    sub = strategy.get("output_subdir") or "site_page"
    stem = content_stem(term, language)
    if suffix:
        stem = f"{stem}{suffix}"
    return GUIDES_DIR / sub / f"{stem}.md"


def generate_outline(
    page_id: str,
    *,
    client: Optional[LLMClient] = None,
    config: Optional[LLMConfig] = None,
    language: str = DEFAULT_LANGUAGE,
    progress: Optional[ProgressCb] = None,
) -> SitePageResult:
    def log(msg: str) -> None:
        if progress:
            progress(msg)

    try:
        cfg = config or load_settings()
        llm = client or LLMClient(cfg)
        log(f"{page_id}: outline [{language}]…")
        msgs = build_site_page_messages(page_id, phase="outline", language=language)
        text = _chat_with_language_guard(llm, msgs, language=language, log=log)
        outline = pages_mod.parse_outline_markdown(text)
        if not outline.get("sections"):
            return SitePageResult(
                ok=False,
                page_id=page_id,
                phase="outline",
                text=text,
                error="Не удалось разобрать секции из Outline (нужен формат `- **Heading** — role`)",
            )
        page = pages_mod.load_page(page_id) or pages_mod.empty_page(page_id)
        page["outline"] = outline
        # сброс драфтов если структура сильно новая — оставляем drafts с тем же id
        pages_mod.save_page(page_id, page)
        seed_info = ""
        ec = str(page.get("existing_copy") or "").strip()
        if ec and ec.lower() != "none":
            seeded = pages_mod.seed_section_drafts_from_existing(
                page_id, overwrite=False
            )
            if seeded.get("ok"):
                seed_info = (
                    f", seeded {seeded.get('seeded', 0)} from existing_copy"
                )
                page = pages_mod.load_page(page_id) or page
                outline = page.get("outline") or outline
        path = guide_path_for_page(page_id, language=language, suffix=".outline")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        log(
            f"{page_id}: outline → {len(outline['sections'])} секций"
            f"{seed_info}, `{path.name}`"
        )
        return SitePageResult(
            ok=True,
            page_id=page_id,
            phase="outline",
            text=text,
            path=path,
            sections=list(outline["sections"]),
        )
    except Exception as exc:  # noqa: BLE001
        return SitePageResult(
            ok=False, page_id=page_id, phase="outline", error=str(exc)
        )


def enrich_outline_from_research(
    page_id: str,
    *,
    client: Optional[LLMClient] = None,
    config: Optional[LLMConfig] = None,
    language: str = DEFAULT_LANGUAGE,
    progress: Optional[ProgressCb] = None,
    draft_md: str = "",
) -> SitePageResult:
    """Обогатить структуру: текущий outline/existing + ресёрч спеки страницы.

    Сохраняет драфты по совпадению заголовков; новые секции — pending + seed из existing.
    """

    def log(msg: str) -> None:
        if progress:
            progress(msg)

    try:
        cfg = config or load_settings()
        llm = client or LLMClient(cfg)
        page = pages_mod.load_page(page_id)
        if not page:
            return SitePageResult(
                ok=False,
                page_id=page_id,
                phase="enrich_outline",
                error="page not found",
            )
        # если редактор правил MD в UI — зафиксируем как seed до LLM
        if draft_md.strip():
            page["structure_seed"] = draft_md.strip()
            pages_mod.save_page(page_id, page)

        log(f"{page_id}: enrich outline from research [{language}]…")
        msgs = build_site_page_messages(
            page_id, phase="enrich_outline", language=language
        )
        text = _chat_with_language_guard(llm, msgs, language=language, log=log)
        parsed = pages_mod.parse_outline_markdown(text)
        if not parsed.get("sections"):
            return SitePageResult(
                ok=False,
                page_id=page_id,
                phase="enrich_outline",
                text=text,
                error="Не удалось разобрать секции (нужен `- **Heading** — role`)",
            )

        outline = pages_mod.import_outline_md_preserving_drafts(page_id, text)
        meta = outline.pop("_enrich_meta", {}) if isinstance(outline, dict) else {}
        # _enrich_meta не должен жить в сохранённом outline — убрать с диска
        page = pages_mod.load_page(page_id) or page
        ol = dict(page.get("outline") or {})
        ol.pop("_enrich_meta", None)
        page["outline"] = ol
        pages_mod.save_page(page_id, page)
        outline = ol

        path = guide_path_for_page(
            page_id, language=language, suffix=".outline_enriched"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        n = len(outline.get("sections") or [])
        log(
            f"{page_id}: enrich → {n} секций "
            f"(remap={meta.get('remapped', 0)}, new={meta.get('created', 0)}, "
            f"seed={meta.get('seeded', 0)}) · `{path.name}`"
        )
        return SitePageResult(
            ok=True,
            page_id=page_id,
            phase="enrich_outline",
            text=text,
            path=path,
            sections=list(outline.get("sections") or []),
        )
    except Exception as exc:  # noqa: BLE001
        return SitePageResult(
            ok=False, page_id=page_id, phase="enrich_outline", error=str(exc)
        )


def editorial_improve_pass(
    page_id: str,
    *,
    client: Optional[LLMClient] = None,
    config: Optional[LLMConfig] = None,
    language: str = DEFAULT_LANGUAGE,
    progress: Optional[ProgressCb] = None,
    ensemble: Optional[bool] = None,
    seed_from_existing: bool = True,
    only_with_draft: bool = True,
    auto_gap_notes: bool = True,
    section_ids: Optional[list[str]] = None,
) -> list[SitePageResult]:
    """Точечный проход по всем секциям: preserve + дописать пробелы ресёрча.

    1) при необходимости засеять драфты из existing_copy
    2) для каждой активной секции с драфтом — improve с surgical notes
    3) секции без драфта: write (если only_with_draft=False) или пропуск
    4) section_ids — если задан, правим только эти id (остальные пропускаем)
    """

    def log(msg: str) -> None:
        if progress:
            progress(msg)

    page = pages_mod.load_page(page_id) or {}
    results: list[SitePageResult] = []
    allow = {str(x) for x in (section_ids or []) if str(x).strip()} or None

    if seed_from_existing:
        ec = str(page.get("existing_copy") or "").strip()
        if ec and ec.lower() != "none":
            seeded = pages_mod.seed_section_drafts_from_existing(
                page_id, overwrite=False
            )
            if seeded.get("ok"):
                log(
                    f"{page_id}: seed existing → +{seeded.get('seeded', 0)}, "
                    f"skip {seeded.get('skipped', 0)}, "
                    f"unmatched {len(seeded.get('unmatched_sections') or [])}"
                )
            page = pages_mod.load_page(page_id) or page

    active = pages_mod.active_sections(page)
    if not active:
        return [
            SitePageResult(
                ok=False,
                page_id=page_id,
                phase="editorial_pass",
                error="нет активных секций в outline",
            )
        ]

    for sec in active:
        sid = str(sec.get("id") or "")
        if not sid:
            continue
        if allow is not None and sid not in allow:
            log(f"{page_id}: skip {sid} (снято в плане прохода)")
            continue
        page = pages_mod.load_page(page_id) or page
        drafts = page.get("sections_draft") or {}
        draft = str(drafts.get(sid) or "").strip()
        # ещё раз подтянуть кусок existing, если после enrich заголовок слегка уехал
        if not draft and seed_from_existing:
            excerpt = _section_existing_excerpt(page, sec, max_chars=4500)
            if excerpt and excerpt.strip().lower() != "none" and len(excerpt) >= 80:
                drafts = dict(drafts)
                drafts[sid] = excerpt if excerpt.lstrip().startswith("#") else (
                    f"## {sec.get('heading') or sid}\n\n{excerpt}"
                )
                page["sections_draft"] = drafts
                for s in (page.get("outline") or {}).get("sections") or []:
                    if isinstance(s, dict) and s.get("id") == sid:
                        s["status"] = "done"
                        s["seeded_from_existing"] = True
                        break
                pages_mod.save_page(page_id, page)
                draft = drafts[sid]
                log(f"{page_id}: soft-seed {sid} from existing ({len(draft)}c)")

        if not draft and only_with_draft:
            log(
                f"{page_id}: skip {sid} (нет драфта и нет матча в existing — "
                f"новая секция из ресёрча; сгенерируйте отдельно)"
            )
            continue

        mode = "improve" if draft else "write"
        existing_notes = pages_mod.get_section_notes(page, sid)
        notes = None
        if auto_gap_notes and mode == "improve":
            notes = pages_mod.build_surgical_improve_notes(page, sec, draft)
            # generate_section пишет section_notes на диск — после вызова вернём ручные

        log(f"{page_id}: editorial {sid} ({mode})…")
        res = generate_section(
            page_id,
            sid,
            mode=mode,
            client=client,
            config=config,
            language=language,
            progress=progress,
            section_notes=notes,
            ensemble=ensemble,
        )
        if auto_gap_notes and mode == "improve":
            # восстановить только ручные замечания редактора
            pages_mod.set_section_notes(page_id, sid, existing_notes)
        results.append(res)
        if not res.ok:
            break
    return results


def _chat(client: LLMClient, messages: dict[str, str], **gen_kw: Any) -> str:
    return client.generate(
        prompt=messages.get("user") or "",
        system_prompt=messages.get("system") or "",
        **gen_kw,
    )


def _parse_llm_json_object(raw: str) -> dict[str, Any]:
    """Достать первый JSON-объект из ответа LLM (fence / хвост / Extra data)."""
    import json
    import re

    text = (raw or "").strip()
    if not text:
        raise ValueError("пустой ответ LLM")

    # ```json ... ``` или ``` ... ```
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.I)
    if fence:
        text = fence.group(1).strip()

    # срез от первой { — raw_decode игнорирует хвост после объекта
    start = text.find("{")
    if start < 0:
        raise ValueError(f"нет JSON-объекта: {text[:200]}")
    payload, _end = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(payload, dict):
        raise ValueError(f"ожидался object, got {type(payload).__name__}")
    return payload


def sentence_temperature(index: int) -> tuple[float, str]:
    """Динамическая температура: чередование факта / пояснения / рубца."""
    # 0: якорь-факт, 1: пояснение, 2: короткий рубец, 3: переход
    bucket = index % 4
    table = {
        0: (0.28, "low — concrete fact / constraint"),
        1: (0.72, "high — explanation with uneven rhythm"),
        2: (0.45, "mid — short blunt beat"),
        3: (0.88, "very high — punchy transition / human quirk"),
    }
    return table[bucket]


def _cyrillic_ratio(text: str) -> float:
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    cyr = sum(1 for ch in letters if "а" <= ch.lower() <= "я" or ch.lower() == "ё")
    return cyr / len(letters)


def sentence_matches_language(text: str, language: str) -> bool:
    """Грубая проверка: en/es не должны быть по-кириллице; ru/uk — наоборот."""
    return text_matches_language(text, language, min_letters=8)


def text_matches_language(
    text: str, language: str, *, min_letters: int = 40
) -> bool:
    """Проверка языка целого драфта (секция / outline)."""
    from .languages import is_cyrillic_language, is_latin_script_language

    t = (text or "").strip()
    if not t or t.upper() == "DONE":
        return True
    letters = [ch for ch in t if ch.isalpha()]
    if len(letters) < min_letters:
        return True
    ratio = _cyrillic_ratio(t)
    lang = (language or "").strip()
    if is_latin_script_language(lang):
        # допускаем чуть кириллицы в цитатах, но не тело на русском
        return ratio < 0.18
    if is_cyrillic_language(lang):
        return ratio > 0.30
    return True


def _language_retry_messages(
    msgs: dict[str, str], *, language: str, bad_draft: str
) -> dict[str, str]:
    """Жёсткий хвост: переписать весь драфт на целевой язык."""
    from .languages import get_language

    opt = get_language(language)
    stamp = (
        f"\n\n=== LANGUAGE FIX (mandatory) ===\n"
        f"Your previous draft was NOT in {opt['name_en']} (`{opt['code']}`).\n"
        f"Rewrite the FULL answer in {opt['name_en']} only. "
        f"No Cyrillic body if the target language uses Latin script. "
        f"Keep the same structure/facts; translate headings and prose.\n"
        f"Rejected draft (wrong language) starts below — do not copy its language:\n"
        f"----\n{(bad_draft or '')[:3500]}\n----\n"
    )
    out = dict(msgs)
    out["user"] = (msgs.get("user") or "") + stamp
    out["system"] = (
        (msgs.get("system") or "")
        + f"\n\nLANGUAGE FIX MODE: output must be 100% {opt['name_en']} (`{opt['code']}`)."
    )
    return out


def _chat_with_language_guard(
    client: LLMClient,
    msgs: dict[str, str],
    *,
    language: str,
    log: Optional[ProgressCb] = None,
    **gen_kw: Any,
) -> str:
    """Один вызов + ретрай, если язык драфта не совпал с селектором."""
    text = _chat(client, msgs, **gen_kw).strip()
    lang = (language or DEFAULT_LANGUAGE).strip().lower() or DEFAULT_LANGUAGE
    if text_matches_language(text, lang):
        return text
    if log:
        log(
            f"language guard: draft not in `{lang}` "
            f"(cyrillic_ratio={_cyrillic_ratio(text):.2f}) — retry"
        )
    retry = _language_retry_messages(msgs, language=lang, bad_draft=text)
    text2 = _chat(
        client,
        retry,
        temperature=min(float(gen_kw.get("temperature", 0.5) or 0.5), 0.4),
        **{k: v for k, v in gen_kw.items() if k != "temperature"},
    ).strip()
    if text_matches_language(text2, lang):
        return text2
    if log:
        log(
            f"language guard: retry still mismatched for `{lang}` "
            f"(ratio={_cyrillic_ratio(text2):.2f}) — keeping retry draft"
        )
    return text2 or text


def _clean_one_sentence(raw: str) -> str:
    t = (raw or "").strip().strip('"').strip("'")
    # убрать markdown fences / нумерацию
    if t.startswith("```"):
        t = t.strip("`").strip()
    t = t.lstrip("0123456789.-) ").strip()
    # только первая «предложенческая» единица, если модель разгулялась
    for sep in (". ", "? ", "! "):
        if sep in t and not t.endswith(sep.strip()):
            # сохранить конец предложения
            parts = []
            buf = t
            # take until first .?! that ends a sentence
            import re

            m = re.match(r"^(.+?[.!?])(?:\s+|$)", t, re.S)
            if m and len(m.group(1)) >= 12:
                t = m.group(1).strip()
            break
    return t


def generate_section_heavy_flow(
    page_id: str,
    section_id: str,
    *,
    client: Optional[LLMClient] = None,
    config: Optional[LLMConfig] = None,
    language: str = DEFAULT_LANGUAGE,
    progress: Optional[ProgressCb] = None,
    max_sentences: int = 14,
) -> SitePageResult:
    """Тяжёлый флоу: секция по одному предложению с динамической temperature."""
    import time

    def log(msg: str) -> None:
        if progress:
            progress(msg)

    try:
        page = pages_mod.load_page(page_id)
        if not page:
            return SitePageResult(
                ok=False, page_id=page_id, phase="heavy_flow", error="page not found"
            )
        outline = page.get("outline") or {}
        section = next(
            (
                s
                for s in (outline.get("sections") or [])
                if isinstance(s, dict) and s.get("id") == section_id
            ),
            None,
        )
        if not section:
            return SitePageResult(
                ok=False,
                page_id=page_id,
                phase="heavy_flow",
                error=f"Секция {section_id} не найдена",
            )

        cfg = config or load_settings()
        llm = client or LLMClient(cfg)
        heading = str(section.get("heading") or section_id)
        sentences: list[str] = []
        temps_used: list[float] = []
        lang = (language or DEFAULT_LANGUAGE).strip().lower() or DEFAULT_LANGUAGE
        log(
            f"{page_id}: heavy flow {section_id} "
            f"(lang={lang}, max {max_sentences} sentences)…"
        )

        for i in range(max_sentences):
            temp, hint = sentence_temperature(i)
            written = "\n\n".join(
                [f"## {heading}", ""] + _group_sentences_to_paras(sentences)
            ).strip()
            msgs = build_site_page_messages(
                page_id,
                phase="sentence_step",
                language=lang,
                section=section,
                section_mode="sentence_step",
                extra_vars={
                    "Written_So_Far": written
                    if sentences
                    else f"## {heading}\n\n(empty — write the opening sentence)",
                    "Sentence_Index": str(i),
                    "Temp_Hint": f"{temp:.2f} · {hint}",
                },
            )
            log(
                f"{section_id}: sentence {i + 1}/{max_sentences} "
                f"@ temp={temp:.2f} · lang={lang}"
            )
            raw = _chat(
                llm,
                msgs,
                temperature=temp,
                max_tokens=min(180, int(getattr(cfg, "max_tokens", 2048) or 2048)),
            ).strip()
            if raw.upper().startswith("DONE") or raw.strip() == "DONE":
                log(f"{section_id}: model signaled DONE at {i}")
                break
            sent = _clean_one_sentence(raw)
            if not sent or len(sent) < 8:
                log(f"{section_id}: empty sentence — stop")
                break
            # язык: если уехали в кириллицу при en (или наоборот) — один ретрай
            if not sentence_matches_language(sent, lang):
                log(
                    f"{section_id}: wrong language (got Cyrillic/Latin mismatch "
                    f"for `{lang}`) — retry"
                )
                retry_msgs = build_site_page_messages(
                    page_id,
                    phase="sentence_step",
                    language=lang,
                    section=section,
                    section_mode="sentence_step",
                    extra_vars={
                        "Written_So_Far": written
                        if sentences
                        else f"## {heading}\n\n(empty — write the opening sentence)",
                        "Sentence_Index": str(i),
                        "Temp_Hint": f"{temp:.2f} · {hint} · LANGUAGE FIX RETRY",
                        "Section_Notes": (
                            (pages_mod.get_section_notes(page, section_id) or "")
                            + f"\n\nLANGUAGE FIX: previous attempt was NOT in `{lang}`. "
                            f"Rewrite that idea as ONE sentence in the target language only."
                        ).strip(),
                    },
                )
                # жёсткий хвост в user — recency bias
                retry_msgs["user"] = (
                    (retry_msgs.get("user") or "")
                    + f"\n\nREJECTED DRAFT (wrong language):\n{sent}\n\n"
                    f"Rewrite ONLY that idea as one sentence in `{lang}`."
                )
                raw2 = _chat(
                    llm,
                    retry_msgs,
                    temperature=min(temp, 0.45),
                    max_tokens=min(180, int(getattr(cfg, "max_tokens", 2048) or 2048)),
                ).strip()
                if raw2.upper().startswith("DONE"):
                    log(f"{section_id}: DONE on language retry — stop")
                    break
                sent2 = _clean_one_sentence(raw2)
                if sent2 and sentence_matches_language(sent2, lang):
                    sent = sent2
                elif sent2:
                    log(f"{section_id}: retry still wrong language — skip sentence")
                    continue
                else:
                    log(f"{section_id}: empty on language retry — stop")
                    break
            # анти-повтор
            if sentences and sent.lower() == sentences[-1].lower():
                log(f"{section_id}: duplicate — stop")
                break
            sentences.append(sent)
            temps_used.append(temp)
            delay = float(getattr(cfg, "delay_seconds", 0) or 0)
            if delay > 0:
                time.sleep(min(delay, 2.0))

        if not sentences:
            return SitePageResult(
                ok=False,
                page_id=page_id,
                phase="heavy_flow",
                error="Тяжёлый флоу не дал ни одного предложения",
            )

        body_paras = _group_sentences_to_paras(sentences)
        text = f"## {heading}\n\n" + "\n\n".join(body_paras)
        drafts = dict(page.get("sections_draft") or {})
        drafts[section_id] = text
        page["sections_draft"] = drafts
        for sec in outline.get("sections") or []:
            if isinstance(sec, dict) and sec.get("id") == section_id:
                sec["status"] = "done"
        page["outline"] = outline
        page.setdefault("heavy_flow_meta", {})
        page["heavy_flow_meta"][section_id] = {
            "temps": temps_used,
            "sentence_count": len(sentences),
            "language": lang,
        }
        pages_mod.save_page(page_id, page)

        safe_h = "".join(
            c if c.isalnum() or c in "-_" else "_" for c in heading
        )[:40]
        path = guide_path_for_page(
            page_id, language=language, suffix=f".section_{section_id}_{safe_h}"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        log(
            f"{section_id}: heavy flow done — {len(sentences)} sentences, "
            f"temps={','.join(f'{t:.2f}' for t in temps_used)}"
        )
        return SitePageResult(
            ok=True,
            page_id=page_id,
            phase="heavy_flow",
            text=text,
            path=path,
            sections=[section],
        )
    except Exception as exc:  # noqa: BLE001
        return SitePageResult(
            ok=False, page_id=page_id, phase="heavy_flow", error=str(exc)
        )


def _group_sentences_to_paras(sentences: list[str], group: int = 2) -> list[str]:
    """Слепить по 2 предложения в абзац — рваный ритм между абзацами."""
    paras: list[str] = []
    buf: list[str] = []
    for i, s in enumerate(sentences):
        buf.append(s)
        # чередуем размер группы 2 / 3 для неровности
        limit = 2 if (i // 2) % 2 == 0 else 3
        if len(buf) >= limit:
            paras.append(" ".join(buf))
            buf = []
    if buf:
        paras.append(" ".join(buf))
    return paras


def _list_header_re():
    return pages_mod._list_header_re()


def _is_structured_block(text: str) -> bool:
    """Pros/Cons / маркированные / много коротких строк — нельзя схлопывать в абзац."""
    import re

    lines = [ln for ln in (text or "").splitlines() if ln.strip()]
    if len(lines) < 2:
        return False
    hdr = _list_header_re()
    if any(hdr.match(ln.strip()) for ln in lines):
        return True
    bulletish = 0
    for ln in lines:
        s = ln.strip()
        if re.match(r"^([-*•]|\d+[.)])\s+\S", s):
            bulletish += 1
        elif ln.startswith(("    ", "\t")) and 3 <= len(s) <= 140:
            bulletish += 1
    if bulletish >= 2:
        return True
    short = sum(1 for ln in lines if 3 <= len(ln.strip()) <= 90)
    return len(lines) >= 4 and short >= 3 and short / len(lines) >= 0.6


def normalize_section_list_markup(text: str) -> str:
    """Прокси к pages.normalize_section_list_markup."""
    return pages_mod.normalize_section_list_markup(text)


def _preserve_structured_format(original: str, rewritten: str) -> str:
    """Если модель склеила список в одну строку — не принимаем схлопывание."""
    import re

    orig = (original or "").strip()
    new = (rewritten or "").strip()
    if not orig or not new:
        return rewritten
    if not _is_structured_block(orig):
        return normalize_section_list_markup(new) if _is_structured_block(new) else new

    orig_n = len([ln for ln in orig.splitlines() if ln.strip()])
    new_n = len([ln for ln in new.splitlines() if ln.strip()])
    # явный коллапс: было ≥3 строк, стало 1–2 без нормальных буллетов
    bullets_new = len(re.findall(r"(?m)^\s*[-*•]\s+\S", new))
    if orig_n >= 3 and new_n <= 2 and bullets_new < 2:
        return normalize_section_list_markup(orig)
    return normalize_section_list_markup(new)


def _clean_one_paragraph(raw: str, *, allow_multiline: bool = False) -> str:
    """Один абзац из ответа модели (без преамбулы / fences)."""
    import re

    t = (raw or "").strip().strip('"').strip("'")
    if not t:
        return ""
    if t.upper().startswith("DONE"):
        return "DONE"
    if t.startswith("```"):
        t = re.sub(r"^```(?:\w+)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t).strip()
    # убрать случайные заголовки секции
    lines: list[str] = []
    for ln in t.splitlines():
        s = ln.strip()
        if s.startswith("#") and not s.startswith("###"):
            continue
        lines.append(ln)
    t = "\n".join(lines).strip()
    if allow_multiline or _is_structured_block(t):
        t = re.sub(r"^(?:Paragraph|Абзац)\s*\d+\s*[:.\-–—]\s*", "", t, flags=re.I)
        return t.strip()
    # только первый абзац
    chunks = re.split(r"\n\s*\n", t, maxsplit=1)
    para = (chunks[0] if chunks else t).strip()
    para = re.sub(r"^(?:Paragraph|Абзац)\s*\d+\s*[:.\-–—]\s*", "", para, flags=re.I)
    return para.strip()


def _split_md_paragraphs(text: str) -> tuple[str, list[str]]:
    """Заголовок секции + список абзацев тела."""
    import re

    raw = (text or "").strip()
    if not raw:
        return "", []
    lines = raw.splitlines()
    heading = ""
    body_start = 0
    if lines and lines[0].lstrip().startswith("#"):
        heading = lines[0].strip()
        body_start = 1
        while body_start < len(lines) and not lines[body_start].strip():
            body_start += 1
    body = "\n".join(lines[body_start:]).strip()
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    return heading, paras


def rewrite_section_paragraphs(
    page_id: str,
    section_id: str,
    *,
    purpose: str = "improve",
    client: Optional[LLMClient] = None,
    config: Optional[LLMConfig] = None,
    language: str = DEFAULT_LANGUAGE,
    progress: Optional[ProgressCb] = None,
    section_notes: Optional[str] = None,
    page_notes: Optional[str] = None,
    ensemble: bool = True,
) -> SitePageResult:
    """Переписать абзацы секции (improve / Anti-AI), опционально чередуя модели."""
    import time

    from .anti_ai import scan_ai_patterns

    def log(msg: str) -> None:
        if progress:
            progress(msg)

    purpose_l = (purpose or "improve").strip().lower()
    phase_name = "antia_pass" if purpose_l == "antia" else "section"

    try:
        if section_notes is not None:
            pages_mod.set_section_notes(page_id, section_id, section_notes)
        page = pages_mod.load_page(page_id)
        if not page:
            return SitePageResult(
                ok=False, page_id=page_id, phase=phase_name, error="page not found"
            )
        if page_notes is not None:
            page["page_notes"] = page_notes
            pages_mod.save_page(page_id, page)
            page = pages_mod.load_page(page_id) or page

        outline = page.get("outline") or {}
        section = next(
            (
                s
                for s in (outline.get("sections") or [])
                if isinstance(s, dict) and s.get("id") == section_id
            ),
            None,
        )
        if not section:
            return SitePageResult(
                ok=False,
                page_id=page_id,
                phase=phase_name,
                error=f"Секция {section_id} не найдена",
            )

        drafts = dict(page.get("sections_draft") or {})
        prev = str(drafts.get(section_id) or "").strip()
        if not prev:
            return SitePageResult(
                ok=False,
                page_id=page_id,
                phase=phase_name,
                error=f"Нет драфта секции {section_id}",
            )

        cfg = config or load_settings()
        primary = client or LLMClient(cfg)
        partner_cfg = ensemble_partner_config(cfg)
        partner: Optional[LLMClient] = None
        if ensemble:
            if not partner_cfg.resolved_api_key():
                return SitePageResult(
                    ok=False,
                    page_id=page_id,
                    phase=phase_name,
                    error=(
                        "Нет ключа партнёра ансамбля "
                        f"({partner_cfg.api_key_env}). Задайте HYDRA_API_KEY."
                    ),
                )
            partner = LLMClient(partner_cfg)

        heading, paras = _split_md_paragraphs(prev)
        if not heading:
            heading = f"## {section.get('heading') or section_id}"
        if not paras:
            return SitePageResult(
                ok=False,
                page_id=page_id,
                phase=phase_name,
                error="В драфте нет абзацев для переписи",
            )

        patterns = scan_ai_patterns(prev) if purpose_l == "antia" else []
        notes_now = pages_mod.get_section_notes(page, section_id)
        lang = (language or DEFAULT_LANGUAGE).strip().lower() or DEFAULT_LANGUAGE
        mode_tag = "antia_paragraph" if purpose_l == "antia" else "improve_paragraph"
        log(
            f"{page_id}: rewrite {section_id} ({purpose_l}"
            f"{'·ensemble' if ensemble else ''}) "
            f"{len(paras)} ¶ [{lang}]"
        )

        # sidecar до правки (для antia)
        safe_h = "".join(
            c if c.isalnum() or c in "-_" else "_"
            for c in str(section.get("heading") or section_id)
        )[:40]
        if purpose_l == "antia":
            pre_path = guide_path_for_page(
                page_id,
                language=language,
                suffix=f".section_{section_id}_{safe_h}.pre_antia",
            )
            pre_path.parent.mkdir(parents=True, exist_ok=True)
            pre_path.write_text(prev, encoding="utf-8")

        new_paras: list[str] = []
        models_used: list[str] = []
        for i, old_para in enumerate(paras):
            use_partner = bool(ensemble and partner is not None and i % 2 == 1)
            llm = partner if use_partner and partner is not None else primary
            model_label = f"{llm.config.provider}:{llm.config.model}"
            if purpose_l == "antia":
                hint = (
                    "Anti-AI rewrite of ONE paragraph — kill LLM cadence, "
                    "keep facts; prefer cut over synonym foam"
                )
            else:
                hint = (
                    "Improve rewrite of ONE paragraph — obey section notes; "
                    "keep facts; vary rhythm vs neighbors"
                )
            written = "\n\n".join([heading, ""] + new_paras).strip()
            extra: dict[str, str] = {
                "Written_So_Far": written,
                "Paragraph_Index": str(i),
                "Ensemble_Model": model_label,
                "Ensemble_Hint": hint,
                "Target_Paragraph": old_para,
                "Section_Previous_Draft": _clip(prev, 3500),
            }
            if notes_now:
                extra["Section_Notes"] = notes_now
            elif purpose_l == "antia" and patterns:
                extra["Section_Notes"] = (
                    "Anti-AI: neutralize patterns: " + "; ".join(patterns[:8])
                )
            pn = str(page.get("page_notes") or "").strip()
            if pn:
                extra["Page_Notes"] = pn
            msgs = build_site_page_messages(
                page_id,
                phase="paragraph_step",
                language=lang,
                section=section,
                section_mode=mode_tag,
                extra_vars=extra,
            )
            structured = _is_structured_block(old_para)
            # жёсткий хвост для antia / improve
            if purpose_l == "antia":
                msgs["user"] = (
                    (msgs.get("user") or "")
                    + "\n\n## ANTI-AI PARAGRAPH TASK\n"
                    "Rewrite ONLY the Target paragraph. Neutralize AI patterns. "
                    "Do not expand into a new section.\n"
                )
            else:
                msgs["user"] = (
                    (msgs.get("user") or "")
                    + "\n\n## IMPROVE PARAGRAPH TASK\n"
                    "Rewrite ONLY the Target paragraph using Section/Page notes. "
                    "Return the rewritten block (or DONE to keep original if already perfect).\n"
                )
            if structured:
                msgs["user"] += (
                    "\n## HARD FORMAT LOCK (Pros/Cons / lists)\n"
                    "This target is a STRUCTURED list block. You MUST:\n"
                    "- Keep headings like Pros / Cons / Additional info on their own lines\n"
                    "- Keep ONE bullet per line as markdown `- item`\n"
                    "- NEVER join list items into a single prose paragraph or one long line\n"
                    "- Preserve roughly the same number of lines/items\n"
                )
            temp = 0.48 if purpose_l == "antia" else 0.52
            if use_partner:
                temp += 0.08
            log(f"{section_id}: ¶{i + 1}/{len(paras)} · {model_label}")
            raw = _chat(
                llm,
                msgs,
                temperature=temp,
                max_tokens=min(900, int(getattr(cfg, "max_tokens", 2048) or 2048)),
                thinking_enabled=False,
            ).strip()
            if raw.upper().startswith("DONE") or raw.strip() == "DONE":
                new_paras.append(old_para)
                models_used.append(f"{model_label}:keep")
                continue
            para = _clean_one_paragraph(raw, allow_multiline=structured)
            if not para or len(para) < 12 or para.upper() == "DONE":
                new_paras.append(old_para)
                models_used.append(f"{model_label}:keep")
                continue
            if not text_matches_language(para, lang, min_letters=20):
                retry_msgs = _language_retry_messages(
                    msgs, language=lang, bad_draft=para
                )
                raw2 = _chat(
                    llm,
                    retry_msgs,
                    temperature=min(temp, 0.4),
                    max_tokens=min(900, int(getattr(cfg, "max_tokens", 2048) or 2048)),
                    thinking_enabled=False,
                ).strip()
                para2 = _clean_one_paragraph(raw2, allow_multiline=structured)
                if para2 and text_matches_language(para2, lang, min_letters=20):
                    para = para2
                else:
                    new_paras.append(old_para)
                    models_used.append(f"{model_label}:lang_keep")
                    continue
            para = _preserve_structured_format(old_para, para)
            new_paras.append(para)
            models_used.append(model_label)
            delay = float(getattr(cfg, "delay_seconds", 0) or 0)
            if delay > 0:
                time.sleep(min(delay, 2.0))

        text = normalize_section_list_markup(
            heading + "\n\n" + "\n\n".join(new_paras)
        )
        page = pages_mod.load_page(page_id) or page
        outline = page.get("outline") or {}
        drafts = dict(page.get("sections_draft") or {})
        drafts[section_id] = text
        page["sections_draft"] = drafts
        for sec in outline.get("sections") or []:
            if isinstance(sec, dict) and sec.get("id") == section_id:
                sec["status"] = "done"
        page["outline"] = outline
        meta_key = "ensemble_meta" if ensemble else "rewrite_meta"
        page.setdefault(meta_key, {})
        page[meta_key][section_id] = {
            "purpose": purpose_l,
            "models": models_used,
            "paragraph_count": len(new_paras),
            "language": lang,
            "ensemble": bool(ensemble),
        }
        pages_mod.save_page(page_id, page)
        pages_mod.append_section_revision(
            page_id,
            section_id,
            action=f"{purpose_l}{'_ensemble' if ensemble else ''}",
            before=prev,
            after=text,
            model=" → ".join(models_used[:6]) or (
                f"{primary.config.provider}:{primary.config.model}"
            ),
            notes=notes_now,
            patterns=patterns if purpose_l == "antia" else None,
        )

        path = guide_path_for_page(
            page_id, language=language, suffix=f".section_{section_id}_{safe_h}"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        if purpose_l == "antia":
            after = scan_ai_patterns(text)
            log(
                f"{section_id}: antia rewrite done "
                f"(before={len(patterns)}, after={len(after)}) · "
                + " → ".join(models_used)
            )
        else:
            log(f"{section_id}: improve rewrite done · " + " → ".join(models_used))
        return SitePageResult(
            ok=True,
            page_id=page_id,
            phase=phase_name,
            text=text,
            path=path,
            sections=[section],
        )
    except Exception as exc:  # noqa: BLE001
        return SitePageResult(
            ok=False, page_id=page_id, phase=phase_name, error=str(exc)
        )


def generate_section_ensemble(
    page_id: str,
    section_id: str,
    *,
    client: Optional[LLMClient] = None,
    config: Optional[LLMConfig] = None,
    language: str = DEFAULT_LANGUAGE,
    progress: Optional[ProgressCb] = None,
    section_notes: Optional[str] = None,
    page_notes: Optional[str] = None,
    max_paragraphs: Optional[int] = None,
) -> SitePageResult:
    """Секция по абзацам: чередование primary LLM ↔ Hydra gpt-6-luna."""
    import time

    def log(msg: str) -> None:
        if progress:
            progress(msg)

    try:
        if section_notes is not None:
            pages_mod.set_section_notes(page_id, section_id, section_notes)
        page = pages_mod.load_page(page_id)
        if not page:
            return SitePageResult(
                ok=False, page_id=page_id, phase="ensemble", error="page not found"
            )
        if page_notes is not None:
            page["page_notes"] = page_notes
            pages_mod.save_page(page_id, page)
            page = pages_mod.load_page(page_id) or page

        outline = page.get("outline") or {}
        section = next(
            (
                s
                for s in (outline.get("sections") or [])
                if isinstance(s, dict) and s.get("id") == section_id
            ),
            None,
        )
        if not section:
            return SitePageResult(
                ok=False,
                page_id=page_id,
                phase="ensemble",
                error=f"Секция {section_id} не найдена",
            )

        cfg = config or load_settings()
        primary = client or LLMClient(cfg)
        partner_cfg = ensemble_partner_config(cfg)
        if not partner_cfg.resolved_api_key():
            return SitePageResult(
                ok=False,
                page_id=page_id,
                phase="ensemble",
                error=(
                    "Нет ключа партнёра ансамбля "
                    f"({partner_cfg.api_key_env}). Задайте HYDRA_API_KEY в .env."
                ),
            )
        partner = LLMClient(partner_cfg)
        limit = int(
            max_paragraphs
            if max_paragraphs is not None
            else (getattr(cfg, "ensemble_max_paragraphs", 8) or 8)
        )
        limit = max(2, min(limit, 16))
        heading = str(section.get("heading") or section_id)
        lang = (language or DEFAULT_LANGUAGE).strip().lower() or DEFAULT_LANGUAGE
        paragraphs: list[str] = []
        models_used: list[str] = []
        notes_now = pages_mod.get_section_notes(page, section_id)
        log(
            f"{page_id}: ensemble {section_id} "
            f"[{primary.config.model} ↔ {partner_cfg.model}] "
            f"lang={lang} max={limit}"
            + (f" · notes={len(notes_now)}c" if notes_now else "")
        )

        for i in range(limit):
            # чётные — primary, нечётные — Hydra (голос чередуется)
            use_partner = i % 2 == 1
            llm = partner if use_partner else primary
            model_label = (
                f"{llm.config.provider}:{llm.config.model}"
            )
            hint = (
                "partner voice — concrete / slightly different cadence"
                if use_partner
                else "primary voice — anchor facts and section spine"
            )
            written = "\n\n".join(
                [f"## {heading}", ""] + paragraphs
            ).strip()
            extra: dict[str, str] = {
                "Written_So_Far": written
                if paragraphs
                else f"## {heading}\n\n(empty — write the opening paragraph)",
                "Paragraph_Index": str(i),
                "Ensemble_Model": model_label,
                "Ensemble_Hint": hint,
            }
            if notes_now:
                extra["Section_Notes"] = notes_now
            pn = str(page.get("page_notes") or "").strip()
            if pn:
                extra["Page_Notes"] = pn
            msgs = build_site_page_messages(
                page_id,
                phase="paragraph_step",
                language=lang,
                section=section,
                section_mode="paragraph_step",
                extra_vars=extra,
            )
            temp = 0.55 if use_partner else 0.42
            log(f"{section_id}: ¶{i + 1}/{limit} · {model_label} @ temp={temp:.2f}")
            raw = _chat(
                llm,
                msgs,
                temperature=temp,
                max_tokens=min(900, int(getattr(cfg, "max_tokens", 2048) or 2048)),
                thinking_enabled=False,
            ).strip()
            if raw.upper().startswith("DONE") or raw.strip() == "DONE":
                log(f"{section_id}: DONE at ¶{i} ({model_label})")
                break
            para = _clean_one_paragraph(raw)
            if para.upper() == "DONE":
                log(f"{section_id}: DONE at ¶{i} ({model_label})")
                break
            if not para or len(para) < 24:
                log(f"{section_id}: empty paragraph — stop")
                break
            if not text_matches_language(para, lang, min_letters=20):
                log(
                    f"{section_id}: wrong language from {model_label} — retry"
                )
                retry_msgs = _language_retry_messages(
                    msgs, language=lang, bad_draft=para
                )
                raw2 = _chat(
                    llm,
                    retry_msgs,
                    temperature=min(temp, 0.4),
                    max_tokens=min(900, int(getattr(cfg, "max_tokens", 2048) or 2048)),
                    thinking_enabled=False,
                ).strip()
                if raw2.upper().startswith("DONE"):
                    break
                para2 = _clean_one_paragraph(raw2)
                if para2 and text_matches_language(para2, lang, min_letters=20):
                    para = para2
                elif para2:
                    log(f"{section_id}: retry still wrong language — skip")
                    continue
                else:
                    break
            if paragraphs and para.lower() == paragraphs[-1].lower():
                log(f"{section_id}: duplicate paragraph — stop")
                break
            paragraphs.append(para)
            models_used.append(model_label)
            delay = float(getattr(cfg, "delay_seconds", 0) or 0)
            if delay > 0:
                time.sleep(min(delay, 2.0))

        if not paragraphs:
            return SitePageResult(
                ok=False,
                page_id=page_id,
                phase="ensemble",
                error="Ансамбль не дал ни одного абзаца",
            )

        text = normalize_section_list_markup(
            f"## {heading}\n\n" + "\n\n".join(paragraphs)
        )
        page = pages_mod.load_page(page_id) or page
        outline = page.get("outline") or {}
        drafts = dict(page.get("sections_draft") or {})
        drafts[section_id] = text
        page["sections_draft"] = drafts
        for sec in outline.get("sections") or []:
            if isinstance(sec, dict) and sec.get("id") == section_id:
                sec["status"] = "done"
        page["outline"] = outline
        page.setdefault("ensemble_meta", {})
        page["ensemble_meta"][section_id] = {
            "models": models_used,
            "paragraph_count": len(paragraphs),
            "language": lang,
            "primary": f"{primary.config.provider}:{primary.config.model}",
            "partner": f"{partner_cfg.provider}:{partner_cfg.model}",
        }
        pages_mod.save_page(page_id, page)
        # свежая генерация с нуля — история правок не нужна
        pages_mod.clear_section_edit_history(page_id, section_id)

        safe_h = "".join(
            c if c.isalnum() or c in "-_" else "_" for c in heading
        )[:40]
        path = guide_path_for_page(
            page_id, language=language, suffix=f".section_{section_id}_{safe_h}"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        log(
            f"{section_id}: ensemble done — {len(paragraphs)} ¶ · "
            + " → ".join(models_used)
        )
        return SitePageResult(
            ok=True,
            page_id=page_id,
            phase="ensemble",
            text=text,
            path=path,
            sections=[section],
        )
    except Exception as exc:  # noqa: BLE001
        return SitePageResult(
            ok=False, page_id=page_id, phase="ensemble", error=str(exc)
        )


def generate_section(
    page_id: str,
    section_id: str,
    *,
    mode: str = "write",
    client: Optional[LLMClient] = None,
    config: Optional[LLMConfig] = None,
    language: str = DEFAULT_LANGUAGE,
    progress: Optional[ProgressCb] = None,
    section_notes: Optional[str] = None,
    page_notes: Optional[str] = None,
    ensemble: Optional[bool] = None,
) -> SitePageResult:
    def log(msg: str) -> None:
        if progress:
            progress(msg)

    try:
        # свежие замечания из UI — сохранить до сборки промпта
        if section_notes is not None:
            pages_mod.set_section_notes(page_id, section_id, section_notes)
        page = pages_mod.load_page(page_id)
        if not page:
            return SitePageResult(
                ok=False, page_id=page_id, phase="section", error="page not found"
            )
        if page_notes is not None:
            page["page_notes"] = page_notes
            pages_mod.save_page(page_id, page)
            page = pages_mod.load_page(page_id) or page

        outline = page.get("outline") or {}
        section = next(
            (
                s
                for s in (outline.get("sections") or [])
                if isinstance(s, dict) and s.get("id") == section_id
            ),
            None,
        )
        if not section:
            return SitePageResult(
                ok=False,
                page_id=page_id,
                phase="section",
                error=f"Секция {section_id} не найдена в outline",
            )
        if pages_mod.is_section_removed(section):
            return SitePageResult(
                ok=False,
                page_id=page_id,
                phase="section",
                error=f"Секция {section_id} удалена — сначала верните её",
            )

        cfg = config or load_settings()
        use_ensemble = (
            bool(ensemble)
            if ensemble is not None
            else bool(getattr(cfg, "ensemble_enabled", False))
        )
        if use_ensemble and mode == "write":
            return generate_section_ensemble(
                page_id,
                section_id,
                client=client,
                config=cfg,
                language=language,
                progress=progress,
                section_notes=None,  # уже сохранены выше
                page_notes=None,
            )
        if use_ensemble and mode == "improve":
            return rewrite_section_paragraphs(
                page_id,
                section_id,
                purpose="improve",
                client=client,
                config=cfg,
                language=language,
                progress=progress,
                section_notes=None,
                page_notes=None,
                ensemble=True,
            )

        llm = client or LLMClient(cfg)
        notes_now = pages_mod.get_section_notes(page, section_id)
        log(
            f"{page_id}: section {section_id} ({mode}) [{language}]"
            + (f" · notes={len(notes_now)}c" if notes_now else " · notes=∅")
            + "…"
        )
        extra: dict[str, str] = {}
        if notes_now:
            extra["Section_Notes"] = notes_now
        pn = str(page.get("page_notes") or "").strip()
        if pn:
            extra["Page_Notes"] = pn
        msgs = build_site_page_messages(
            page_id,
            phase="section",
            language=language,
            section=section,
            section_mode=mode,
            extra_vars=extra or None,
        )
        prev_draft = str(
            (page.get("sections_draft") or {}).get(section_id) or ""
        ).strip()
        text = _chat_with_language_guard(
            llm, msgs, language=language, log=log
        ).strip()
        if prev_draft:
            text = _preserve_structured_format(prev_draft, text)
        text = normalize_section_list_markup(text)
        # перечитать page — notes не затереть
        page = pages_mod.load_page(page_id) or page
        outline = page.get("outline") or {}
        drafts = dict(page.get("sections_draft") or {})
        drafts[section_id] = text
        page["sections_draft"] = drafts
        for sec in outline.get("sections") or []:
            if isinstance(sec, dict) and sec.get("id") == section_id:
                sec["status"] = "done"
        page["outline"] = outline
        pages_mod.save_page(page_id, page)
        if mode == "write":
            pages_mod.clear_section_edit_history(page_id, section_id)
        elif mode == "improve" and prev_draft:
            pages_mod.append_section_revision(
                page_id,
                section_id,
                action="improve",
                before=prev_draft,
                after=text,
                model=f"{llm.config.provider}:{llm.config.model}",
                notes=notes_now,
            )

        safe_h = "".join(
            c if c.isalnum() or c in "-_" else "_"
            for c in str(section.get("heading") or section_id)
        )[:40]
        path = guide_path_for_page(
            page_id, language=language, suffix=f".section_{section_id}_{safe_h}"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        log(f"{page_id}: section {section_id} saved ({len(text)} chars)")
        return SitePageResult(
            ok=True,
            page_id=page_id,
            phase="section",
            text=text,
            path=path,
            sections=[section],
        )
    except Exception as exc:  # noqa: BLE001
        return SitePageResult(
            ok=False, page_id=page_id, phase="section", error=str(exc)
        )


def zerogpt_rewrite_section(
    page_id: str,
    section_id: str,
    *,
    highlighted: list[str],
    client: Optional[LLMClient] = None,
    config: Optional[LLMConfig] = None,
    language: str = DEFAULT_LANGUAGE,
    progress: Optional[ProgressCb] = None,
    headless_browser: bool = True,
    run_browser_check: bool = False,
    recheck_after: bool = True,
) -> SitePageResult:
    """Проверить (опц.) ZeroGPT → точечно переписать только подсвеченные предложения.

    Если recheck_after=True — после правок снова гоняет браузерный ZeroGPT
    и пишет ai_percent_after в zerogpt_reports.
    """
    import json
    import re

    from .zerogpt import (
        apply_sentence_replacements,
        check_text_via_browser,
    )

    def _recheck_and_store(
        page_obj: dict,
        sid: str,
        body: str,
        report: dict,
    ) -> tuple[dict, Optional[float], str]:
        """Повторный ZeroGPT → обновить report. Возвращает (report, %, note)."""
        if not recheck_after:
            return report, None, ""
        log(f"{page_id}: ZeroGPT re-check after edit {sid}…")
        zg2 = check_text_via_browser(body, headless=headless_browser)
        if not zg2.ok:
            report = {**report, "ai_percent_after": None, "recheck_error": zg2.error}
            note = f" · re-check fail: {zg2.error}"
            return report, None, note
        report = {
            **report,
            "ai_percent_after": zg2.ai_percent,
            "highlighted_after": list(zg2.highlighted or []),
            "recheck_error": "",
        }
        note = f" · now {zg2.ai_percent}% AI"
        log(
            f"{page_id}: after edit ZeroGPT {zg2.ai_percent}% AI, "
            f"{len(zg2.highlighted or [])} highlighted"
        )
        return report, zg2.ai_percent, note

    def log(msg: str) -> None:
        if progress:
            progress(msg)

    try:
        page = pages_mod.load_page(page_id)
        if not page:
            return SitePageResult(
                ok=False, page_id=page_id, phase="zerogpt_fix", error="page not found"
            )
        outline = page.get("outline") or {}
        section = next(
            (
                s
                for s in (outline.get("sections") or [])
                if isinstance(s, dict) and s.get("id") == section_id
            ),
            None,
        )
        if not section:
            return SitePageResult(
                ok=False,
                page_id=page_id,
                phase="zerogpt_fix",
                error=f"Секция {section_id} не найдена",
            )
        drafts = dict(page.get("sections_draft") or {})
        prev = str(drafts.get(section_id) or "").strip()
        if not prev:
            return SitePageResult(
                ok=False,
                page_id=page_id,
                phase="zerogpt_fix",
                error=f"Нет драфта {section_id}",
            )

        flags = list(highlighted or [])
        zg_score = None
        if run_browser_check or not flags:
            log(f"{page_id}: ZeroGPT browser check {section_id}…")
            zg = check_text_via_browser(prev, headless=headless_browser)
            if not zg.ok:
                return SitePageResult(
                    ok=False,
                    page_id=page_id,
                    phase="zerogpt_fix",
                    error=zg.error,
                    text=prev,
                )
            flags = zg.highlighted
            zg_score = zg.ai_percent
            log(
                f"{page_id}: ZeroGPT {zg_score}% AI, "
                f"{len(flags)} highlighted sentence(s)"
            )

        usable: list[str] = []
        for f in flags:
            if not f:
                continue
            if f in prev:
                usable.append(f)
                continue
            # нормализованный поиск
            collapsed = re.sub(r"\s+", " ", prev)
            f2 = re.sub(r"\s+", " ", f)
            if f2 in collapsed:
                usable.append(f)
        if not usable:
            return SitePageResult(
                ok=True,
                page_id=page_id,
                phase="zerogpt_fix",
                text=prev,
                error=(
                    f"Нет подсвеченных фрагментов для правки"
                    + (f" (score={zg_score}%)" if zg_score is not None else "")
                ),
            )

        cfg = config or load_settings()
        llm = client or LLMClient(cfg)
        lang = (language or DEFAULT_LANGUAGE).strip() or DEFAULT_LANGUAGE
        from .languages import get_language, normalize_language_code

        lang = normalize_language_code(lang)
        lang_opt = get_language(lang)
        highlights_block = "\n".join(f"- {s}" for s in usable)
        log(
            f"{page_id}: editorial ZeroGPT pass on {len(usable)} span(s) "
            f"[{lang_opt['name_en']}/{lang}]…"
        )
        msgs = build_site_page_messages(
            page_id,
            phase="zerogpt_fix",
            language=lang,
            section=section,
            section_mode="zerogpt_fix",
            extra_vars={"ZeroGPT_Highlights": highlights_block},
        )
        # якорь языка ещё раз у конца user (поверх anti-AI pack)
        msgs["user"] = (
            (msgs.get("user") or "")
            + f"\n\n## LANGUAGE FOR `new` FIELDS\n"
            f"Selector = **{lang_opt['name_en']}** (`{lang}`). "
            f"Every non-empty `new` must be in {lang_opt['name_en']}. "
            f"Translate if `old` is another language.\n"
        )
        raw = _chat(
            llm,
            msgs,
            max_tokens=min(3500, int(getattr(cfg, "max_tokens", 4096) or 4096)),
        ).strip()
        try:
            payload = _parse_llm_json_object(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            return SitePageResult(
                ok=False,
                page_id=page_id,
                phase="zerogpt_fix",
                error=f"JSON parse: {exc}",
                text=raw,
            )
        if not isinstance(payload, dict):
            return SitePageResult(
                ok=False,
                page_id=page_id,
                phase="zerogpt_fix",
                error=f"LLM JSON не объект: {type(payload).__name__}",
                text=raw,
            )

        def _coerce_edits(pl: dict) -> list:
            er = pl.get("edits")
            if isinstance(er, list):
                return er
            out = []
            for item in pl.get("replacements") or []:
                if isinstance(item, dict):
                    out.append(
                        {
                            "old": item.get("old"),
                            "new": item.get("new"),
                            "action": "rewrite",
                            "flag_reason": "",
                            "meaning_job": "",
                            "decision": "legacy replacements[]",
                        }
                    )
            return out

        edits_raw = _coerce_edits(payload)

        def _apply_edits(items: list) -> tuple[dict[str, str], list[dict[str, str]], dict[str, int]]:
            mp: dict[str, str] = {}
            elog: list[dict[str, str]] = []
            cnt = {"rewrite": 0, "compress": 0, "delete": 0, "keep": 0, "other": 0}
            for item in items:
                if not isinstance(item, dict):
                    continue
                old = str(item.get("old") or "").strip()
                if not old:
                    continue
                action = str(item.get("action") or "rewrite").strip().lower()
                new = str(item.get("new") or "")
                applied_new = old
                if action == "delete":
                    mp[old] = ""
                    applied_new = ""
                    cnt["delete"] += 1
                elif action == "keep":
                    # keep на чужом языке → принудительный rewrite-перевод
                    if not sentence_matches_language(old, lang):
                        action = "rewrite"
                        if new.strip() and sentence_matches_language(new.strip(), lang):
                            mp[old] = new.strip()
                            applied_new = new.strip()
                            cnt["rewrite"] += 1
                        else:
                            # пометим — ниже ретрай
                            mp[old] = new.strip() or old
                            applied_new = mp[old]
                            cnt["rewrite"] += 1
                    else:
                        cnt["keep"] += 1
                elif action in ("rewrite", "compress"):
                    if new.strip() and new.strip() != old:
                        mp[old] = new.strip()
                        applied_new = new.strip()
                        cnt[action] += 1
                    else:
                        cnt["keep"] += 1
                        action = "keep"
                else:
                    if new.strip() and new.strip() != old:
                        mp[old] = new.strip()
                        applied_new = new.strip()
                        cnt["other"] += 1
                    else:
                        cnt["keep"] += 1
                        action = "keep"
                elog.append(
                    {
                        "old": old,
                        "new": applied_new,
                        "action": action,
                        "flag_reason": str(item.get("flag_reason") or ""),
                        "meaning_job": str(item.get("meaning_job") or ""),
                        "decision": str(item.get("decision") or ""),
                    }
                )
            return mp, elog, cnt

        mapping, edit_log, counts = _apply_edits(edits_raw)

        # language guard: rewrite/compress new на чужом языке → один ретрай
        bad_news = [
            ed
            for ed in edit_log
            if ed.get("action") in ("rewrite", "compress", "other")
            and ed.get("new")
            and not sentence_matches_language(str(ed["new"]), lang)
        ]
        if bad_news:
            log(
                f"{page_id}: {len(bad_news)} edit(s) wrong language for `{lang}` — retry"
            )
            bad_block = "\n".join(
                f"- old: {ed['old']}\n  bad_new: {ed['new']}" for ed in bad_news
            )
            retry_msgs = {
                "system": (
                    f"You fix ZeroGPT editorial JSON. "
                    f"Every `new` must be in {lang_opt['name_en']} (`{lang}`) only. "
                    f"No Cyrillic if target is Latin-script. Return JSON only."
                ),
                "user": (
                    f"Target language: {lang_opt['name_en']} (`{lang}`).\n"
                    f"These `new` values are WRONG language. Translate each into "
                    f"{lang_opt['name_en']}, keep action rewrite/compress, same meaning.\n"
                    f"{bad_block}\n\n"
                    f'Return JSON: {{"edits":[{{"old":"...","action":"rewrite",'
                    f'"new":"... in {lang_opt["name_en"]}"}}]}}'
                ),
            }
            raw2 = _chat(
                llm,
                retry_msgs,
                temperature=0.35,
                max_tokens=min(2500, int(getattr(cfg, "max_tokens", 4096) or 4096)),
            ).strip()
            try:
                payload2 = _parse_llm_json_object(raw2)
                fixes = {
                    str(it.get("old") or "").strip(): str(it.get("new") or "").strip()
                    for it in _coerce_edits(payload2)
                    if isinstance(it, dict)
                    and str(it.get("old") or "").strip()
                    and str(it.get("new") or "").strip()
                }
                for ed in edit_log:
                    old = ed["old"]
                    if old in fixes and sentence_matches_language(fixes[old], lang):
                        ed["new"] = fixes[old]
                        ed["decision"] = (
                            (ed.get("decision") or "") + " · language fix"
                        ).strip(" ·")
                        mapping[old] = fixes[old]
            except (json.JSONDecodeError, ValueError) as exc:
                log(f"{page_id}: language retry parse fail: {exc}")

        if not edit_log:
            return SitePageResult(
                ok=False,
                page_id=page_id,
                phase="zerogpt_fix",
                error="Пустой edits[] / replacements[]",
                text=raw,
            )
        if not mapping and counts["keep"] == len(edit_log):
            summary = (
                f"Все {counts['keep']} флагов → keep (ложные срабатывания?). "
                f"Текст не менялся · lang=`{lang}`"
                + (f"; ZeroGPT был {zg_score}%" if zg_score is not None else "")
            )
            report = {
                "ai_percent": zg_score,
                "highlighted": usable,
                "edits": edit_log,
                "counts": counts,
                "language": lang,
            }
            report, _after, after_note = _recheck_and_store(
                page, section_id, prev, report
            )
            summary += after_note
            reports = dict(page.get("zerogpt_reports") or {})
            reports[section_id] = report
            page["zerogpt_reports"] = reports
            pages_mod.save_page(page_id, page)
            return SitePageResult(
                ok=True,
                page_id=page_id,
                phase="zerogpt_fix",
                text=prev,
                error=summary,
            )

        safe_h = "".join(
            c if c.isalnum() or c in "-_" else "_"
            for c in str(section.get("heading") or section_id)
        )[:40]
        pre_path = guide_path_for_page(
            page_id,
            language=lang,
            suffix=f".section_{section_id}_{safe_h}.pre_zerogpt",
        )
        pre_path.parent.mkdir(parents=True, exist_ok=True)
        pre_path.write_text(prev, encoding="utf-8")

        new_text = apply_sentence_replacements(prev, mapping) if mapping else prev
        new_text = _preserve_structured_format(prev, new_text)
        new_text = normalize_section_list_markup(new_text)
        drafts[section_id] = new_text
        page["sections_draft"] = drafts
        report = {
            "ai_percent": zg_score,
            "highlighted": usable,
            "edits": edit_log,
            "counts": counts,
            "replacements": mapping,
            "language": lang,
        }
        # сначала сохраним драфт, потом re-check по уже записанному тексту
        reports = dict(page.get("zerogpt_reports") or {})
        reports[section_id] = report
        page["zerogpt_reports"] = reports
        pages_mod.save_page(page_id, page)
        if new_text.strip() != prev.strip():
            pages_mod.append_section_revision(
                page_id,
                section_id,
                action="zerogpt",
                before=prev,
                after=new_text,
                model=f"{llm.config.provider}:{llm.config.model}",
                notes=pages_mod.get_section_notes(page, section_id),
            )

        out_path = guide_path_for_page(
            page_id, language=lang, suffix=f".section_{section_id}_{safe_h}"
        )
        out_path.write_text(new_text, encoding="utf-8")

        page = pages_mod.load_page(page_id) or page
        report, ai_after, after_note = _recheck_and_store(
            page, section_id, new_text, report
        )
        reports = dict(page.get("zerogpt_reports") or {})
        reports[section_id] = report
        page["zerogpt_reports"] = reports
        pages_mod.save_page(page_id, page)

        summary = (
            f"lang=`{lang}` · rewrite={counts['rewrite']} · compress={counts['compress']} · "
            f"delete={counts['delete']} · keep={counts['keep']}"
            + (f" · was {zg_score}% AI" if zg_score is not None else "")
            + after_note
        )
        log(f"{page_id}: {section_id} ZeroGPT editorial ok ({summary})")
        return SitePageResult(
            ok=True,
            page_id=page_id,
            phase="zerogpt_fix",
            text=new_text,
            path=out_path,
            sections=[section],
            error=summary,
        )
    except Exception as exc:  # noqa: BLE001
        return SitePageResult(
            ok=False, page_id=page_id, phase="zerogpt_fix", error=str(exc)
        )


def antia_pass_section(
    page_id: str,
    section_id: str,
    *,
    client: Optional[LLMClient] = None,
    config: Optional[LLMConfig] = None,
    language: str = DEFAULT_LANGUAGE,
    progress: Optional[ProgressCb] = None,
    force: bool = False,
    ensemble: bool = False,
) -> SitePageResult:
    """Второй цикл: жёсткий Anti-AI pass по одной секции."""
    from .anti_ai import scan_ai_patterns

    def log(msg: str) -> None:
        if progress:
            progress(msg)

    try:
        page = pages_mod.load_page(page_id)
        if not page:
            return SitePageResult(
                ok=False, page_id=page_id, phase="antia_pass", error="page not found"
            )
        outline = page.get("outline") or {}
        section = next(
            (
                s
                for s in (outline.get("sections") or [])
                if isinstance(s, dict) and s.get("id") == section_id
            ),
            None,
        )
        if not section:
            return SitePageResult(
                ok=False,
                page_id=page_id,
                phase="antia_pass",
                error=f"Секция {section_id} не найдена",
            )
        drafts = dict(page.get("sections_draft") or {})
        prev = str(drafts.get(section_id) or "").strip()
        if not prev:
            return SitePageResult(
                ok=False,
                page_id=page_id,
                phase="antia_pass",
                error=f"Нет драфта секции {section_id}",
            )

        patterns = scan_ai_patterns(prev)
        if not patterns and not force:
            log(f"{page_id}: {section_id} — явных паттернов нет, skip (force=off)")
            return SitePageResult(
                ok=True,
                page_id=page_id,
                phase="antia_pass",
                text=prev,
                sections=[section],
                error="",
            )

        cfg = config or load_settings()
        if ensemble:
            return rewrite_section_paragraphs(
                page_id,
                section_id,
                purpose="antia",
                client=client,
                config=cfg,
                language=language,
                progress=progress,
                ensemble=True,
            )

        llm = client or LLMClient(cfg)
        log(
            f"{page_id}: Anti-AI pass {section_id} "
            f"({len(patterns)} pattern(s)) "
            f"[{llm.config.provider}:{llm.config.model}] [{language}]…"
        )
        msgs = build_site_page_messages(
            page_id,
            phase="antia_pass",
            language=language,
            section=section,
            section_mode="antia_pass",
        )
        msgs["user"] = (
            (msgs.get("user") or "")
            + "\n\n## HARD FORMAT LOCK\n"
            "Preserve Markdown structure: headings, blank lines, and lists. "
            "Pros/Cons/Additional info must stay as lists (`- item` per line), "
            "never one long prose line.\n"
        )
        text = _chat_with_language_guard(
            llm, msgs, language=language, log=log, thinking_enabled=False
        ).strip()
        if len(text) < 40:
            return SitePageResult(
                ok=False,
                page_id=page_id,
                phase="antia_pass",
                error="Anti-AI pass вернул слишком короткий текст",
                text=text,
            )
        text = _preserve_structured_format(prev, text)
        text = normalize_section_list_markup(text)

        # sidecar до правки
        safe_h = "".join(
            c if c.isalnum() or c in "-_" else "_"
            for c in str(section.get("heading") or section_id)
        )[:40]
        pre_path = guide_path_for_page(
            page_id,
            language=language,
            suffix=f".section_{section_id}_{safe_h}.pre_antia",
        )
        pre_path.parent.mkdir(parents=True, exist_ok=True)
        pre_path.write_text(prev, encoding="utf-8")

        drafts[section_id] = text
        page["sections_draft"] = drafts
        pages_mod.save_page(page_id, page)
        pages_mod.append_section_revision(
            page_id,
            section_id,
            action="antia",
            before=prev,
            after=text,
            model=f"{llm.config.provider}:{llm.config.model}",
            notes=pages_mod.get_section_notes(page, section_id),
            patterns=patterns,
        )

        out_path = guide_path_for_page(
            page_id, language=language, suffix=f".section_{section_id}_{safe_h}"
        )
        out_path.write_text(text, encoding="utf-8")
        after = scan_ai_patterns(text)
        log(
            f"{page_id}: {section_id} Anti-AI done "
            f"(before={len(patterns)}, after={len(after)})"
        )
        return SitePageResult(
            ok=True,
            page_id=page_id,
            phase="antia_pass",
            text=text,
            path=out_path,
            sections=[section],
        )
    except Exception as exc:  # noqa: BLE001
        return SitePageResult(
            ok=False, page_id=page_id, phase="antia_pass", error=str(exc)
        )


def antia_pass_all_sections(
    page_id: str,
    *,
    client: Optional[LLMClient] = None,
    config: Optional[LLMConfig] = None,
    language: str = DEFAULT_LANGUAGE,
    progress: Optional[ProgressCb] = None,
    force: bool = True,
    only_with_patterns: bool = False,
    ensemble: bool = False,
) -> list[SitePageResult]:
    """Второй цикл по всем секциям с драфтом."""
    page = pages_mod.load_page(page_id) or {}
    results: list[SitePageResult] = []
    for sec in pages_mod.active_sections(page):
        sid = str(sec.get("id") or "")
        draft = str((page.get("sections_draft") or {}).get(sid) or "").strip()
        if not draft:
            continue
        use_force = force if not only_with_patterns else False
        res = antia_pass_section(
            page_id,
            sid,
            client=client,
            config=config,
            language=language,
            progress=progress,
            force=use_force,
            ensemble=ensemble,
        )
        results.append(res)
        if not res.ok:
            break
        page = pages_mod.load_page(page_id) or page
    return results


def generate_all_sections(
    page_id: str,
    *,
    only_missing: bool = True,
    mode: str = "write",
    client: Optional[LLMClient] = None,
    config: Optional[LLMConfig] = None,
    language: str = DEFAULT_LANGUAGE,
    progress: Optional[ProgressCb] = None,
    ensemble: Optional[bool] = None,
) -> list[SitePageResult]:
    page = pages_mod.load_page(page_id) or {}
    results: list[SitePageResult] = []
    for sec in pages_mod.active_sections(page):
        sid = str(sec.get("id") or "")
        if only_missing and pages_mod.section_status(page, sid) == "done":
            continue
        # reload page each time so neighbors update
        page = pages_mod.load_page(page_id) or page
        res = generate_section(
            page_id,
            sid,
            mode=mode,
            client=client,
            config=config,
            language=language,
            progress=progress,
            ensemble=ensemble,
        )
        results.append(res)
        if not res.ok:
            break
    return results


def assemble_page(
    page_id: str,
    *,
    language: str = DEFAULT_LANGUAGE,
    write_guide: bool = True,
) -> SitePageResult:
    page = pages_mod.load_page(page_id)
    if not page:
        return SitePageResult(
            ok=False, page_id=page_id, phase="assemble", error="page not found"
        )
    outline = page.get("outline") or {}
    meta = outline.get("meta") or {}
    drafts = page.get("sections_draft") or {}
    # удалённые секции не входят в итоговый текст
    sections = pages_mod.active_sections(page)
    missing = [
        s.get("id")
        for s in sections
        if isinstance(s, dict) and not str(drafts.get(s.get("id") or "") or "").strip()
    ]
    if missing:
        return SitePageResult(
            ok=False,
            page_id=page_id,
            phase="assemble",
            error=f"Нет драфта для секций: {', '.join(str(m) for m in missing)}",
        )
    if not sections:
        return SitePageResult(
            ok=False,
            page_id=page_id,
            phase="assemble",
            error="Нет активных секций (все удалены?)",
        )

    body_parts = []
    for sec in sections:
        if not isinstance(sec, dict):
            continue
        body = str(drafts.get(sec.get("id") or "") or "").strip()
        if body:
            body_parts.append(body)

    outline_lines = []
    for sec in sections:
        if not isinstance(sec, dict):
            continue
        outline_lines.append(
            f"- **{sec.get('heading', '')}** — {sec.get('role', '')}"
        )

    dropped = [
        s
        for s in (outline.get("sections") or [])
        if isinstance(s, dict) and pages_mod.is_section_removed(s)
    ]
    editor_notes = ["- Assembled from section pipeline"]
    if dropped:
        editor_notes.append(
            "- Dropped sections: "
            + ", ".join(
                f"{s.get('id')} ({s.get('heading')})" for s in dropped
            )
        )

    package = "\n".join(
        [
            "## Meta",
            f"- Title: {meta.get('title', '')}",
            f"- Description: {meta.get('description', '')}",
            f"- URL: {meta.get('url') or page.get('url') or ''}",
            f"- H1: {meta.get('h1', '')}",
            "",
            "## Page job (1–2 lines)",
            str(outline.get("page_job") or page.get("primary_job") or ""),
            "",
            "## Outline",
            *outline_lines,
            "",
            "## Full draft",
            "",
            "\n\n".join(body_parts),
            "",
            "## Internal links used",
            "- (review after publish)",
            "",
            "## Placeholders requiring facts",
            "- (scan Full draft for [PLACEHOLDER])",
            "",
            "## Editor notes",
            *editor_notes,
            "",
        ]
    )

    path = None
    if write_guide:
        path = guide_path_for_page(page_id, language=language)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(package, encoding="utf-8")

    return SitePageResult(
        ok=True,
        page_id=page_id,
        phase="assemble",
        text=package,
        path=path,
        sections=list(sections),
    )
