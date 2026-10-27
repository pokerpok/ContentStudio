"""Реестр стратегий генерации контента."""

from __future__ import annotations

from typing import Any

from .store import STRATEGIES_DIR, read_json, write_json


def list_strategies() -> list[dict[str, Any]]:
    STRATEGIES_DIR.mkdir(parents=True, exist_ok=True)
    result = []
    for path in sorted(STRATEGIES_DIR.glob("*.json")):
        data = read_json(path)
        if data:
            result.append(data)
    return result


def get_strategy(strategy_id: str) -> dict[str, Any] | None:
    path = STRATEGIES_DIR / f"{strategy_id}.json"
    return read_json(path)


def save_strategy(data: dict[str, Any]) -> None:
    sid = data["id"]
    write_json(STRATEGIES_DIR / f"{sid}.json", data)


def create_strategy(
    strategy_id: str,
    name: str,
    *,
    description: str = "",
    user_prompt: str | None = None,
    system_prompt: str | None = None,
    extract_hands: bool = False,
) -> dict[str, Any]:
    sid = strategy_id.strip().lower().replace(" ", "_")
    data = {
        "id": sid,
        "name": name.strip() or sid,
        "description": description,
        "terms_key": sid,
        "user_prompt": user_prompt or f"{sid}_user.md",
        "system_prompt": system_prompt or f"{sid}_system.md",
        "output_subdir": sid,
        "extract_hands": extract_hands,
    }
    save_strategy(data)
    from .prompt_store import load_prompt, save_prompt

    if not load_prompt(data["user_prompt"]):
        save_prompt(
            data["user_prompt"],
            'Write a clear page section about "{Poker_Term}".\n',
        )
    if not load_prompt(data["system_prompt"]):
        save_prompt(
            data["system_prompt"],
            "You are an editorial content writer. Write clear, accurate pages.\n",
        )
    return data


def delete_strategy(strategy_id: str) -> None:
    path = STRATEGIES_DIR / f"{strategy_id}.json"
    if path.exists():
        path.unlink()
