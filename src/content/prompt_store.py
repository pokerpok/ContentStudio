"""Загрузка и рендер шаблонов промптов."""

from __future__ import annotations

from typing import Any

from .languages import DEFAULT_LANGUAGE, prompt_vars_for_language
from .store import PROMPTS_DIR


def prompt_path(filename: str):
    return PROMPTS_DIR / filename


def load_prompt(filename: str) -> str:
    path = prompt_path(filename)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def save_prompt(filename: str, text: str) -> None:
    path = prompt_path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def render_prompt(template: str, *, poker_term: str, **extra: str) -> str:
    """Подстановка {Poker_Term} (topic label), {Language*} и доп. плейсхолдеров.

    Два прохода: чтобы плейсхолдеры внутри вложенных блоков тоже заменились.
    Имя аргумента `poker_term` сохранено для совместимости шаблонов.
    """
    mapping = {"Poker_Term": poker_term, **extra}
    result = template
    for _ in range(2):
        for key, value in mapping.items():
            result = result.replace("{" + key + "}", str(value))
    return result


def _strategy_wants_anti_ai(strategy: dict) -> bool:
    if "include_anti_ai" in strategy:
        return bool(strategy.get("include_anti_ai"))
    sid = str(strategy.get("id", ""))
    sys_file = str(strategy.get("system_prompt", ""))
    return "styled" in sid or "styled" in sys_file or strategy.get("mode") == "site_page"


def build_messages_for_term(
    strategy: dict,
    term: str,
    *,
    language: str = DEFAULT_LANGUAGE,
    greenstein_context: str = "",
    page: dict[str, Any] | None = None,
    extra_vars: dict[str, str] | None = None,
) -> dict[str, str]:
    """Собирает итоговые system/user сообщения, как уйдут в LLM."""
    from .anti_ai import load_anti_ai_style
    from .briefs import load_brief_prompt_block
    from .pages import load_page, page_to_prompt_vars

    lang_vars = prompt_vars_for_language(language)
    brief_id = str(strategy.get("project_brief") or "")
    brief_block = load_brief_prompt_block(brief_id) if brief_id else ""
    anti_block = load_anti_ai_style() if _strategy_wants_anti_ai(strategy) else ""

    extra: dict[str, str] = {
        "Greenstein_Context": greenstein_context or "",
        "Project_Brief": brief_block,
        "Anti_AI_Style": anti_block,
    }

    page_data = page
    if page_data is None and strategy.get("mode") == "site_page":
        page_data = load_page(term)
        if not page_data:
            page_data = load_page(term.replace(" ", "_"))
    if page_data:
        extra.update(page_to_prompt_vars(page_data))
        extra["Project_Brief"] = brief_block
        extra["Anti_AI_Style"] = anti_block
        term = str(page_data.get("term") or page_data.get("page_id") or term)

    # явные extra_vars побеждают (усечённый existing_copy / notes для section)
    if extra_vars:
        extra.update(extra_vars)

    user_tmpl = load_prompt(strategy["user_prompt"])
    system_tmpl = load_prompt(strategy.get("system_prompt", ""))
    system = (
        render_prompt(system_tmpl, poker_term=term, **lang_vars, **extra)
        if system_tmpl
        else ""
    )
    user = render_prompt(user_tmpl, poker_term=term, **lang_vars, **extra)

    if brief_block and "{Project_Brief}" not in system_tmpl and brief_block not in system:
        system = (brief_block + "\n" + system).strip()

    if anti_block and "{Anti_AI_Style}" not in system_tmpl and "Анти-AI стиль" not in system:
        system = (system.rstrip() + "\n\n" + anti_block).strip() + "\n"

    if greenstein_context and "{Greenstein_Context}" not in (system_tmpl + user_tmpl):
        system = (system + "\n" + greenstein_context).strip()

    return {
        "system": system,
        "user": user,
        "system_file": strategy.get("system_prompt", ""),
        "user_file": strategy.get("user_prompt", ""),
        "language": language,
        "language_label": lang_vars["Language_Label"],
        "greenstein": bool(greenstein_context.strip()),
        "project_brief": brief_id,
        "anti_ai": bool(anti_block),
        "page_id": (page_data or {}).get("page_id", ""),
    }


def list_prompt_files() -> list[str]:
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(p.name for p in PROMPTS_DIR.glob("*.md"))
