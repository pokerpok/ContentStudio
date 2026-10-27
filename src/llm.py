"""OpenAI-compatible LLM клиент: local / deepseek / custom."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional

import requests
from dotenv import load_dotenv

from .content.store import SETTINGS_PATH, read_json, write_json

load_dotenv()

Provider = Literal["local", "deepseek", "openai_compatible", "hydra"]

PROVIDER_PRESETS: dict[str, dict[str, str]] = {
    "local": {
        "base_url": "http://localhost:1234/v1",
        "model": "qwen2.5-14b-instruct",
        "api_key_env": "LLM_API_KEY",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "api_key_env": "DEEPSEEK_API_KEY",
    },
    "openai_compatible": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "api_key_env": "OPENAI_API_KEY",
    },
    "hydra": {
        "base_url": "https://api.hydraai.ru/v1",
        "model": "gpt-6-luna",
        "api_key_env": "HYDRA_API_KEY",
    },
}

# Партнёр по умолчанию для ансамбля абзацев (HydraAI)
ENSEMBLE_DEFAULT_PROVIDER = "hydra"
ENSEMBLE_DEFAULT_MODEL = "gpt-6-luna"


@dataclass
class LLMConfig:
    provider: Provider = "local"
    base_url: str = "http://localhost:1234/v1"
    model: str = "qwen2.5-14b-instruct"
    api_key_env: str = "LLM_API_KEY"
    api_key: str = ""
    temperature: float = 0.5
    max_tokens: int = 2048
    delay_seconds: float = 1.0
    generate_images: bool = False
    generate_gif: bool = False
    content_language: str = "ru"
    # DeepSeek V4: thinking включён по умолчанию на стороне API — гасим явно
    thinking_enabled: bool = False
    use_greenstein: bool = False
    # Ансамбль: разные абзацы секции пишут primary + partner (Hydra gpt-6-luna)
    ensemble_enabled: bool = False
    ensemble_provider: str = ENSEMBLE_DEFAULT_PROVIDER
    ensemble_base_url: str = ""
    ensemble_model: str = ENSEMBLE_DEFAULT_MODEL
    ensemble_api_key_env: str = "HYDRA_API_KEY"
    ensemble_api_key: str = ""
    ensemble_max_paragraphs: int = 8
    extra: dict[str, Any] = field(default_factory=dict)

    def resolved_api_key(self) -> str:
        if self.api_key:
            return self.api_key
        return os.getenv(self.api_key_env, "") or os.getenv("LLM_API_KEY", "")

    def resolved_ensemble_api_key(self) -> str:
        if self.ensemble_api_key.strip():
            return self.ensemble_api_key.strip()
        env_name = (self.ensemble_api_key_env or "HYDRA_API_KEY").strip()
        return os.getenv(env_name, "") or ""


def ensemble_partner_config(cfg: LLMConfig) -> LLMConfig:
    """Конфиг второй модели для ансамбля абзацев (обычно Hydra gpt-6-luna)."""
    provider = (cfg.ensemble_provider or ENSEMBLE_DEFAULT_PROVIDER).strip()
    preset = PROVIDER_PRESETS.get(provider, PROVIDER_PRESETS["hydra"])
    base_url = (cfg.ensemble_base_url or "").strip() or preset["base_url"]
    model = (cfg.ensemble_model or "").strip() or preset["model"]
    api_key_env = (cfg.ensemble_api_key_env or "").strip() or preset["api_key_env"]
    api_key = cfg.resolved_ensemble_api_key() or os.getenv(api_key_env, "")
    return LLMConfig(
        provider=provider,  # type: ignore[arg-type]
        base_url=base_url,
        model=model,
        api_key_env=api_key_env,
        api_key=api_key,
        temperature=float(cfg.temperature),
        max_tokens=int(cfg.max_tokens),
        delay_seconds=float(cfg.delay_seconds),
        thinking_enabled=False,
        use_greenstein=bool(cfg.use_greenstein),
        content_language=cfg.content_language,
    )


# Выбор модели в блоках секций / Anti-AI / improve
BlockModelChoice = Literal["primary", "partner", "ensemble"]


def block_model_options(cfg: LLMConfig) -> list[tuple[str, str]]:
    """(value, label) для UI выбора модели в блоках."""
    partner = ensemble_partner_config(cfg)
    return [
        ("primary", f"Primary · {cfg.model}"),
        ("partner", f"Hydra · {partner.model}"),
        ("ensemble", f"Ансамбль · {cfg.model} ↔ {partner.model}"),
    ]


def resolve_block_model(
    cfg: LLMConfig, choice: str
) -> tuple[LLMConfig, bool]:
    """Вернуть (конфиг клиента, использовать_ансамбль)."""
    c = (choice or "primary").strip().lower()
    if c in ("ensemble", "ens", "both", "ансамбль"):
        return cfg, True
    if c in ("partner", "hydra", "luna", "secondary", "партнёр", "партнер"):
        return ensemble_partner_config(cfg), False
    return cfg, False


def load_settings() -> LLMConfig:
    raw = read_json(SETTINGS_PATH, default={}) or {}
    provider = raw.get("provider", "local")
    preset = PROVIDER_PRESETS.get(provider, PROVIDER_PRESETS["local"])
    ens_preset = PROVIDER_PRESETS.get(
        raw.get("ensemble_provider") or ENSEMBLE_DEFAULT_PROVIDER,
        PROVIDER_PRESETS["hydra"],
    )
    return LLMConfig(
        provider=provider,
        base_url=raw.get("base_url") or preset["base_url"],
        model=raw.get("model") or preset["model"],
        api_key_env=raw.get("api_key_env") or preset["api_key_env"],
        api_key=raw.get("api_key", ""),
        temperature=float(raw.get("temperature", 0.5)),
        max_tokens=int(raw.get("max_tokens", 2048)),
        delay_seconds=float(raw.get("delay_seconds", 1.0)),
        generate_images=bool(raw.get("generate_images", False)),
        generate_gif=bool(raw.get("generate_gif", False)),
        content_language=str(raw.get("content_language", "ru")),
        thinking_enabled=bool(raw.get("thinking_enabled", False)),
        use_greenstein=bool(raw.get("use_greenstein", False)),
        ensemble_enabled=bool(raw.get("ensemble_enabled", False)),
        ensemble_provider=str(
            raw.get("ensemble_provider") or ENSEMBLE_DEFAULT_PROVIDER
        ),
        ensemble_base_url=str(raw.get("ensemble_base_url") or ens_preset["base_url"]),
        ensemble_model=str(raw.get("ensemble_model") or ens_preset["model"]),
        ensemble_api_key_env=str(
            raw.get("ensemble_api_key_env") or ens_preset["api_key_env"]
        ),
        ensemble_api_key=str(raw.get("ensemble_api_key") or ""),
        ensemble_max_paragraphs=int(raw.get("ensemble_max_paragraphs", 8)),
    )


def save_settings(cfg: LLMConfig, *, persist_api_key: bool = True) -> None:
    write_json(
        SETTINGS_PATH,
        {
            "provider": cfg.provider,
            "base_url": cfg.base_url,
            "model": cfg.model,
            "api_key_env": cfg.api_key_env,
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_tokens,
            "delay_seconds": cfg.delay_seconds,
            "generate_images": cfg.generate_images,
            "generate_gif": cfg.generate_gif,
            "content_language": cfg.content_language,
            "thinking_enabled": cfg.thinking_enabled,
            "use_greenstein": cfg.use_greenstein,
            "ensemble_enabled": cfg.ensemble_enabled,
            "ensemble_provider": cfg.ensemble_provider,
            "ensemble_base_url": cfg.ensemble_base_url,
            "ensemble_model": cfg.ensemble_model,
            "ensemble_api_key_env": cfg.ensemble_api_key_env,
            "ensemble_max_paragraphs": cfg.ensemble_max_paragraphs,
        },
    )
    if persist_api_key and cfg.api_key.strip():
        _upsert_dotenv(cfg.api_key_env, cfg.api_key.strip())
        os.environ[cfg.api_key_env] = cfg.api_key.strip()
    if persist_api_key and cfg.ensemble_api_key.strip():
        env_name = (cfg.ensemble_api_key_env or "HYDRA_API_KEY").strip()
        _upsert_dotenv(env_name, cfg.ensemble_api_key.strip())
        os.environ[env_name] = cfg.ensemble_api_key.strip()


def _upsert_dotenv(key: str, value: str) -> Path:
    """Пишет/обновляет KEY=value в .env (не в git)."""
    from .content.store import PROJECT_ROOT

    env_path = PROJECT_ROOT / ".env"
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    prefix = f"{key}="
    found = False
    new_lines: list[str] = []
    for line in lines:
        if line.startswith(prefix) or line.startswith(f"export {prefix}"):
            new_lines.append(f"{key}={value}")
            found = True
        else:
            new_lines.append(line)
    if not found:
        if new_lines and new_lines[-1].strip():
            new_lines.append("")
        new_lines.append(f"{key}={value}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    load_dotenv(env_path, override=True)
    return env_path


def apply_provider_preset(cfg: LLMConfig, provider: Provider) -> LLMConfig:
    preset = PROVIDER_PRESETS[provider]
    cfg.provider = provider
    cfg.base_url = preset["base_url"]
    cfg.model = preset["model"]
    cfg.api_key_env = preset["api_key_env"]
    # подтянуть ключ из окружения для нового провайдера
    env_val = os.getenv(cfg.api_key_env, "")
    if env_val:
        cfg.api_key = env_val
    return cfg


class LLMClient:
    """Единый клиент chat/completions."""

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or load_settings()
        self.last_finish_reason: str = ""
        self.last_truncated: bool = False

    def ping(self, timeout: float = 5.0) -> tuple[bool, str]:
        """Быстрая проверка доступности API."""
        url = self.config.base_url.rstrip("/") + "/models"
        headers = {"Content-Type": "application/json"}
        api_key = self.config.resolved_api_key()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            if response.status_code < 500:
                return True, f"OK ({response.status_code}) {self.config.base_url}"
            return False, f"HTTP {response.status_code}: {response.text[:200]}"
        except requests.RequestException as exc:
            # /models может отсутствовать — пробуем короткий chat
            try:
                self.generate(
                    prompt="Reply with exactly: pong",
                    system_prompt="You are a connectivity check. Reply with one word.",
                    max_tokens=8,
                    temperature=0,
                )
                return True, f"OK chat {self.config.base_url}"
            except Exception as chat_exc:
                return False, (
                    f"LLM недоступен ({self.config.provider}): {exc}. "
                    f"Chat fallback: {chat_exc}"
                )

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        thinking_enabled = kwargs.pop("thinking_enabled", self.config.thinking_enabled)
        raise_on_truncate = bool(kwargs.pop("raise_on_truncate", False))

        payload: dict[str, Any] = {
            "model": kwargs.pop("model", self.config.model),
            "messages": messages,
            "temperature": kwargs.pop("temperature", self.config.temperature),
            "max_tokens": kwargs.pop("max_tokens", self.config.max_tokens),
            **kwargs,
        }

        # DeepSeek V4: thinking ON by default — отключаем явно, иначе
        # reasoning съедает max_tokens и в content приходит пустота.
        # https://api-docs.deepseek.com/guides/thinking_mode
        if self.config.provider == "deepseek" or "deepseek" in (
            self.config.base_url or ""
        ).lower():
            payload["thinking"] = {
                "type": "enabled" if thinking_enabled else "disabled"
            }

        headers = {"Content-Type": "application/json"}
        api_key = self.config.resolved_api_key()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        url = self.config.base_url.rstrip("/") + "/chat/completions"
        # section/outline могут быть долгими; 180с мало для загруженного API
        req_timeout = int(kwargs.pop("timeout", 300))
        try:
            response = requests.post(
                url, headers=headers, json=payload, timeout=req_timeout
            )
            response.raise_for_status()
        except requests.Timeout as exc:
            raise RuntimeError(
                f"LLM timeout after {req_timeout}s ({self.config.provider}). "
                "Повторите или уменьшите контекст (existing_copy)."
            ) from exc
        except requests.RequestException as exc:
            raise RuntimeError(
                f"LLM request failed ({self.config.provider} @ {url}): {exc}"
            ) from exc

        data = response.json()
        if isinstance(data, dict) and data.get("error"):
            err = data["error"]
            msg = err.get("message") if isinstance(err, dict) else str(err)
            raise RuntimeError(f"LLM API error: {msg}")
        try:
            choice = data["choices"][0]
            message = choice["message"]
            content = message.get("content")
            reasoning = message.get("reasoning_content") or ""
            text = (content or "").strip()
            finish_reason = str(choice.get("finish_reason") or "")
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected LLM response: {data}") from exc

        self.last_finish_reason = finish_reason
        self.last_truncated = finish_reason == "length"

        # Никогда не подставляем reasoning как статью — это и был Big_Bet1.md
        if not text:
            hint = ""
            if reasoning:
                hint = (
                    " API вернул только reasoning_content (thinking). "
                    "Отключите Thinking в сайдбаре или увеличьте max_tokens."
                )
            raise RuntimeError(
                f"LLM вернул пустой content (model={payload.get('model')}).{hint} "
                f"Raw keys: {list(message.keys()) if isinstance(message, dict) else message}"
            )
        if self.last_truncated and raise_on_truncate:
            raise RuntimeError(
                f"LLM ответ обрезан (finish_reason=length, max_tokens={payload.get('max_tokens')}). "
                "Увеличьте max_tokens."
            )
        return text


def client_for_block_model(cfg: LLMConfig, choice: str) -> tuple[LLMClient, bool]:
    """LLMClient + флаг ансамбля для действия в блоке."""
    action_cfg, use_ensemble = resolve_block_model(cfg, choice)
    return LLMClient(action_cfg), use_ensemble
