"""Project brief: универсальный контекст бренда/сайта для генерации страниц."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .store import DATA_DIR, read_json, write_json

BRIEFS_DIR = DATA_DIR / "briefs"


def briefs_dir() -> Path:
    BRIEFS_DIR.mkdir(parents=True, exist_ok=True)
    return BRIEFS_DIR


def list_briefs() -> list[str]:
    return sorted(p.stem for p in briefs_dir().glob("*.json"))


def brief_path(brief_id: str) -> Path:
    return briefs_dir() / f"{brief_id}.json"


def load_brief(brief_id: str) -> dict[str, Any]:
    if not brief_id:
        return {}
    data = read_json(brief_path(brief_id), default={})
    return data if isinstance(data, dict) else {}


def save_brief(brief_id: str, data: dict[str, Any]) -> None:
    data = {**data, "id": brief_id}
    write_json(brief_path(brief_id), data)


def brief_to_prompt_block(brief: dict[str, Any]) -> str:
    """Человекочитаемый блок для вставки в system/user."""
    if not brief:
        return ""

    lines: list[str] = ["# Project brief (authoritative for this run)"]
    brand = brief.get("brand_name") or brief.get("id") or "Brand"
    lines.append(f"- Brand: {brand}")
    if brief.get("site_url"):
        lines.append(f"- Site: {brief['site_url']}")
    if brief.get("site_type"):
        lines.append(f"- Site type: {brief['site_type']}")
    if brief.get("voice"):
        lines.append(f"- Voice: {brief['voice']}")
    if brief.get("default_locale"):
        lines.append(f"- Default locale: {brief['default_locale']}")
    markets = brief.get("focus_markets") or []
    if markets:
        lines.append(f"- Focus markets: {', '.join(markets)}")
    pri = brief.get("product_priority") or []
    if pri:
        lines.append(f"- Product priority: {', '.join(pri)}")
    adj = brief.get("adjacent_products") or []
    if adj:
        lines.append(f"- Adjacent (do not steal job unless page asks): {', '.join(adj)}")
    oos = brief.get("out_of_scope_default") or []
    if oos:
        lines.append(f"- Default out of scope: {', '.join(oos)}")
    if brief.get("audience"):
        lines.append(f"- Audience: {brief['audience']}")
    if brief.get("objection_policy"):
        lines.append(f"- Objection policy: {brief['objection_policy']}")

    comp = brief.get("compliance") or {}
    if comp:
        lines.append("- Compliance:")
        if comp.get("vertical"):
            lines.append(f"  - Vertical: {comp['vertical']}")
        if comp.get("require_age_gate_copy"):
            lines.append(f"  - Age label: {comp.get('age_label', '18+')}")
        forbid = comp.get("forbid_unverified_claims") or []
        if forbid:
            lines.append(f"  - Forbidden unless verified facts provided: {', '.join(forbid)}")

    for rule in brief.get("ia_rules") or []:
        lines.append(f"- IA: {rule}")
    for note in brief.get("style_notes") or []:
        lines.append(f"- Style: {note}")

    return "\n".join(lines).strip() + "\n"


def load_brief_prompt_block(brief_id: str) -> str:
    return brief_to_prompt_block(load_brief(brief_id))
