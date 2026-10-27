"""Content Studio — флоу внутренних страниц сайта."""

from __future__ import annotations

import sys
from pathlib import Path
import os

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.content import briefs as briefs_mod
from src.content import pages as pages_mod
from src.content.languages import DEFAULT_LANGUAGE, LANGUAGES, language_choices
from src.llm import (
    PROVIDER_PRESETS,
    LLMConfig,
    apply_provider_preset,
    block_model_options,
    client_for_block_model,
    load_settings,
    save_settings,
)

st.set_page_config(
    page_title="Content Studio",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _load_cloud_secrets() -> None:
    """Streamlit Community Cloud: Secrets → os.environ для LLMClient."""
    try:
        secrets = st.secrets  # type: ignore[attr-defined]
    except Exception:
        return
    for key in (
        "DEEPSEEK_API_KEY",
        "HYDRA_API_KEY",
        "OPENAI_API_KEY",
        "LLM_API_KEY",
    ):
        try:
            val = secrets.get(key) if hasattr(secrets, "get") else secrets[key]
        except Exception:
            continue
        if val:
            os.environ.setdefault(key, str(val).strip())


def init_state() -> None:
    _load_cloud_secrets()
    if "llm_cfg" not in st.session_state:
        cfg = load_settings()
        if not cfg.api_key:
            cfg.api_key = os.getenv(cfg.api_key_env, "") or ""
        if not getattr(cfg, "ensemble_api_key", ""):
            cfg.ensemble_api_key = os.getenv(
                getattr(cfg, "ensemble_api_key_env", None) or "HYDRA_API_KEY", ""
            ) or ""
        st.session_state.llm_cfg = cfg


def render_llm_sidebar() -> LLMConfig:
    st.sidebar.title("Content Studio")
    cfg: LLMConfig = st.session_state.llm_cfg

    st.sidebar.markdown("### LLM")
    provider = st.sidebar.selectbox(
        "Провайдер",
        options=list(PROVIDER_PRESETS.keys()),
        index=list(PROVIDER_PRESETS.keys()).index(cfg.provider)
        if cfg.provider in PROVIDER_PRESETS
        else 0,
        format_func=lambda p: {
            "local": "Local (LM Studio / OpenAI-compatible)",
            "deepseek": "DeepSeek",
            "openai_compatible": "OpenAI / другой API",
            "hydra": "HydraAI (gpt-6-luna)",
        }.get(p, p),
        key="llm_provider",
    )
    if provider != cfg.provider:
        cfg = apply_provider_preset(cfg, provider)
        st.session_state.llm_cfg = cfg
        st.session_state.llm_base_url = cfg.base_url
        st.session_state.llm_model = cfg.model
        st.session_state.llm_api_key_env = cfg.api_key_env

    if "llm_base_url" not in st.session_state:
        st.session_state.llm_base_url = cfg.base_url
    if "llm_model" not in st.session_state:
        st.session_state.llm_model = cfg.model
    if "llm_api_key_env" not in st.session_state:
        st.session_state.llm_api_key_env = cfg.api_key_env

    if "llm_api_key" not in st.session_state:
        st.session_state.llm_api_key = cfg.api_key or os.getenv(cfg.api_key_env, "")

    cfg.provider = provider  # type: ignore[assignment]
    cfg.base_url = st.sidebar.text_input("Base URL", key="llm_base_url")
    cfg.model = st.sidebar.text_input("Model", key="llm_model")
    cfg.api_key_env = st.sidebar.text_input("Env var for API key", key="llm_api_key_env")
    cfg.api_key = st.sidebar.text_input(
        "API key",
        type="password",
        key="llm_api_key",
        help="При сохранении пишется в .env (файл в .gitignore).",
    )
    cfg.temperature = st.sidebar.slider("Temperature", 0.0, 1.5, float(cfg.temperature), 0.05)
    cfg.max_tokens = st.sidebar.number_input("Max tokens", 256, 16384, int(cfg.max_tokens), 128)
    cfg.delay_seconds = st.sidebar.number_input(
        "Delay between terms (s)", 0.0, 30.0, float(cfg.delay_seconds), 0.5
    )
    cfg.thinking_enabled = st.sidebar.checkbox(
        "DeepSeek Thinking mode",
        value=bool(cfg.thinking_enabled),
        help="У V4 thinking включён по умолчанию. Оставьте выкл. для статей — иначе в файл попадёт reasoning.",
    )
    if cfg.provider == "deepseek" and cfg.thinking_enabled:
        st.sidebar.warning("Thinking ON: нужны большие max_tokens, иначе статья обрежется.")

    st.sidebar.markdown("### Ансамбль абзацев")
    cfg.ensemble_enabled = st.sidebar.checkbox(
        "Чередовать модели по абзацам",
        value=bool(getattr(cfg, "ensemble_enabled", False)),
        help="При «Сгенерировать» / все секции: ¶0 primary, ¶1 Hydra gpt-6-luna, ¶2 primary…",
        key="llm_ensemble_enabled",
    )
    if "llm_ensemble_model" not in st.session_state:
        st.session_state.llm_ensemble_model = getattr(cfg, "ensemble_model", "gpt-6-luna") or "gpt-6-luna"
    if "llm_ensemble_base_url" not in st.session_state:
        st.session_state.llm_ensemble_base_url = (
            getattr(cfg, "ensemble_base_url", "") or "https://api.hydraai.ru/v1"
        )
    if "llm_ensemble_api_key_env" not in st.session_state:
        st.session_state.llm_ensemble_api_key_env = (
            getattr(cfg, "ensemble_api_key_env", "HYDRA_API_KEY") or "HYDRA_API_KEY"
        )
    if "llm_ensemble_api_key" not in st.session_state:
        ens_env = st.session_state.llm_ensemble_api_key_env
        st.session_state.llm_ensemble_api_key = (
            getattr(cfg, "ensemble_api_key", "") or os.getenv(ens_env, "")
        )
    cfg.ensemble_provider = "hydra"
    cfg.ensemble_base_url = st.sidebar.text_input(
        "Ensemble Base URL", key="llm_ensemble_base_url"
    )
    cfg.ensemble_model = st.sidebar.text_input("Ensemble model", key="llm_ensemble_model")
    cfg.ensemble_api_key_env = st.sidebar.text_input(
        "Ensemble env var", key="llm_ensemble_api_key_env"
    )
    cfg.ensemble_api_key = st.sidebar.text_input(
        "Ensemble API key (Hydra)",
        type="password",
        key="llm_ensemble_api_key",
        help="Из smimon/Gemini (.env OPENAI_API_KEY при BASE_URL=hydraai). Пишется в HYDRA_API_KEY.",
    )
    cfg.ensemble_max_paragraphs = int(
        st.sidebar.number_input(
            "Макс. абзацев (ансамбль)",
            min_value=2,
            max_value=16,
            value=int(getattr(cfg, "ensemble_max_paragraphs", 8) or 8),
            key="llm_ensemble_max_paras",
        )
    )
    if cfg.ensemble_enabled:
        from src.llm import ensemble_partner_config

        partner = ensemble_partner_config(cfg)
        if partner.resolved_api_key():
            st.sidebar.caption(
                f"Партнёр: `{partner.model}` @ `{partner.base_url}` · ключ OK"
            )
        else:
            st.sidebar.warning(f"Нет ключа `{partner.api_key_env}`")

    if st.sidebar.button("Сохранить LLM-настройки"):
        save_settings(cfg, persist_api_key=True)
        st.session_state.llm_cfg = cfg
        st.sidebar.success("Сохранено: settings.json + .env")

    return cfg


# ---------------------------------------------------------------------------
# Site pages flow
# ---------------------------------------------------------------------------

def _sync_ec_editor_from_disk(pid: str, text: str) -> None:
    """После записи existing_copy на диск — новый ключ виджета + сброс JSON-превью.

    Старый паттерн `st.session_state[ec_edit]=ec` перед text_area затирал
    несохранённые правки при повторных сейвах (Streamlit widget state).
    """
    pending_key = f"ec_edit_pending_{pid}"
    st.session_state[pending_key] = text
    # структура шага 2
    st.session_state[f"site_struct_fresh_{pid}"] = True
    # JSON-спека не должна откатывать existing_copy старым дампом
    st.session_state[f"page_json_bump_{pid}"] = True


def site_pages_flow() -> None:
    """Флоу внутренних страниц: вводные → структура → контент → выход."""
    import importlib
    import json as _json

    from src.content import site_page_pipeline as spp
    from src.content import fetch_page as fetch_page_mod
    from src.llm import LLMClient

    # Streamlit кэширует модули между rerun — подхватываем свежий код пайплайна
    spp = importlib.reload(spp)
    fetch_page_mod = importlib.reload(fetch_page_mod)
    fetch_page_text = fetch_page_mod.fetch_page_text

    st.markdown("### Внутренние страницы сайта")
    st.caption(
        "Флоу: **1) вводные** (существующая страница / заметки) → "
        "**2) структура** (MD-заголовки или генерация) → "
        "**3) контент** (секции или целиком, с замечаниями) → "
        "**4) готовая страница**."
    )

    cfg = st.session_state.llm_cfg
    lang_codes = [c for c, _ in language_choices()]
    cur_lang = (
        cfg.content_language if cfg.content_language in lang_codes else DEFAULT_LANGUAGE
    )

    # --- page picker ---
    page_ids = pages_mod.list_pages()
    c_new, c_pick = st.columns([1, 2])
    with c_new:
        new_pid = st.text_input("Новый page_id", key="new_page_id", placeholder="RM-05")
        if st.button("Создать", key="site_create_page") and new_pid.strip():
            pid_n = new_pid.strip()
            if not pages_mod.load_page(pid_n):
                pages_mod.save_page(pid_n, pages_mod.empty_page(pid_n))
            st.session_state["page_select"] = pid_n
            st.rerun()
    with c_pick:
        if not page_ids:
            st.info("Создайте page_id (например RM-04).")
            return
        pid = st.selectbox("Страница", options=page_ids, key="page_select")

    page = pages_mod.load_page(pid) or pages_mod.empty_page(pid)
    sec_lang = st.selectbox(
        "Язык выхода (обязателен для LLM)",
        options=lang_codes,
        index=lang_codes.index(cur_lang),
        format_func=lambda c: LANGUAGES[c]["label"],
        key=f"site_flow_lang_{pid}",
        help="Итоговый текст (Meta, Outline, секции) пишется на этом языке. "
        "Язык existing_copy игнорируется — при необходимости модель переводит.",
    )
    cfg.content_language = sec_lang
    st.caption(
        f"Сейчас в промпт уходит: **{LANGUAGES[sec_lang]['name_en']}** "
        f"(`{sec_lang}`). Исходник на другом языке будет переведён."
    )

    step = st.radio(
        "Шаг",
        options=["1_inputs", "2_structure", "3_content", "4_output"],
        format_func=lambda s: {
            "1_inputs": "1 · Вводные",
            "2_structure": "2 · Структура",
            "3_content": "3 · Контент",
            "4_output": "4 · Готовая страница",
        }[s],
        horizontal=True,
        key=f"site_flow_step_{pid}",
    )

    # =====================================================================
    # STEP 1 — inputs
    # =====================================================================
    if step == "1_inputs":
        st.markdown("#### Что обогащаем / пишем")
        st.write(
            f"**URL спеки:** `{page.get('url') or '—'}` · "
            f"**action:** `{page.get('action')}` · "
            f"**job:** {page.get('primary_job') or '—'}"
        )

        mode = st.radio(
            "Тип задачи",
            ["rewrite", "write"],
            index=0 if page.get("action") == "rewrite" else 1,
            format_func=lambda a: (
                "Обогатить / переписать существующую"
                if a == "rewrite"
                else "Написать новую (страницы ещё нет)"
            ),
            horizontal=True,
            key=f"site_action_{pid}",
        )

        st.markdown("##### Существующий контент")
        src = st.radio(
            "Откуда взять",
            ["URL", "Вставить текст", "Уже в файле"],
            horizontal=True,
            key=f"site_src_{pid}",
        )
        if src == "URL":
            fetch_url = st.text_input(
                "URL живой страницы",
                value=str(page.get("source_url") or ""),
                key=f"site_url_{pid}",
            )
            st.caption(
                "Порядок: Firecrawl → Playwright → HTTP. "
                "Если Firecrawl не залогинен, для JS-сайтов нужен Playwright или вставка текста."
            )
            if st.button("Загрузить страницу", key=f"site_fetch_{pid}"):
                with st.spinner("Загрузка…"):
                    res = fetch_page_text(fetch_url)
                if not res.get("ok"):
                    st.error(res.get("error") or "Ошибка загрузки")
                    notes = res.get("notes") or []
                    if notes:
                        st.caption("Детали: " + " · ".join(str(n) for n in notes))
                else:
                    pages_mod.set_existing_copy(
                        pid,
                        res["text"],
                        source_url=res.get("url") or fetch_url,
                        action="rewrite",
                    )
                    seed = pages_mod.refresh_structure_seed(pid)
                    st.session_state[f"site_struct_pending_{pid}"] = seed
                    _sync_ec_editor_from_disk(pid, res["text"])
                    st.success(
                        f"Загружено {res.get('chars')} символов ({res.get('source')})"
                    )
                    st.rerun()
        elif src == "Вставить текст":
            paste = st.text_area(
                "Текст / markdown текущей страницы (без меню и футера)",
                height=200,
                key=f"site_paste_{pid}",
            )
            if st.button("Сохранить текст", key=f"site_paste_save_{pid}"):
                if not paste.strip():
                    st.warning("Пусто")
                else:
                    pages_mod.set_existing_copy(pid, paste.strip(), action="rewrite")
                    seed = pages_mod.refresh_structure_seed(pid)
                    st.session_state[f"site_struct_pending_{pid}"] = seed
                    _sync_ec_editor_from_disk(pid, paste.strip())
                    st.success(f"Сохранено {len(paste.strip())} символов")
                    st.rerun()

        # existing_copy: редактирование + LLM-очистка chrome
        page = pages_mod.load_page(pid) or page
        ec = str(page.get("existing_copy") or "")
        has_ec = bool(ec.strip() and ec.strip().lower() != "none")
        if not has_ec:
            for k in list(st.session_state.keys()):
                if k.startswith(f"ec_edit_{pid}"):
                    st.session_state.pop(k, None)
            st.session_state.pop(f"ec_edit_pending_{pid}", None)
            st.session_state.pop(f"ec_edit_ver_{pid}", None)
        if has_ec:
            st.caption(
                f"existing_copy на диске: **{len(ec)}** симв. · "
                f"source=`{page.get('source_url') or '—'}` · action=`{page.get('action')}`"
            )
            looks_raw = (
                sum(1 for ln in ec.splitlines() if "[" in ln or "]" in ln) > 40
                or "Все права защищены" in ec[:2000]
            )
            if looks_raw:
                st.warning(
                    "Похоже на сырой скрейп (меню/футер). "
                    "Отредактируйте поле ниже или нажмите «LLM: убрать меню/футер»."
                )

            ver_key = f"ec_edit_ver_{pid}"
            pending_key = f"ec_edit_pending_{pid}"
            if ver_key not in st.session_state:
                st.session_state[ver_key] = 0
            # Внешнее обновление с диска → новый widget key (не затираем активный).
            if pending_key in st.session_state:
                st.session_state[ver_key] = int(st.session_state[ver_key]) + 1
                wkey_new = f"ec_edit_{pid}_v{st.session_state[ver_key]}"
                st.session_state[wkey_new] = st.session_state.pop(pending_key)
            wkey = f"ec_edit_{pid}_v{st.session_state[ver_key]}"
            if wkey not in st.session_state:
                st.session_state[wkey] = ec

            with st.expander(
                "Редактировать existing_copy",
                expanded=looks_raw or src == "Уже в файле",
            ):
                # form: текст + submit атомарно (повторные сейвы не откатываются)
                with st.form(
                    key=f"ec_edit_form_{pid}_v{st.session_state[ver_key]}",
                    clear_on_submit=False,
                ):
                    edited_ec = st.text_area(
                        "Текст страницы (можно чистить руками)",
                        height=320,
                        key=wkey,
                    )
                    c_save, c_llm, c_wipe = st.columns(3)
                    with c_save:
                        save_ec = st.form_submit_button(
                            "Сохранить правки",
                            type="primary",
                            use_container_width=True,
                        )
                    with c_llm:
                        llm_ec = st.form_submit_button(
                            "LLM: убрать меню/футер",
                            use_container_width=True,
                            help="Удаляет навигацию/футер/chrome, основной текст не переписывает.",
                        )
                    with c_wipe:
                        wipe_ec = st.form_submit_button(
                            "Стереть existing_copy",
                            use_container_width=True,
                        )

                if save_ec:
                    body = (edited_ec or "").strip()
                    pages_mod.set_existing_copy(
                        pid,
                        body,
                        source_url=str(page.get("source_url") or ""),
                        action=str(page.get("action") or "rewrite"),
                    )
                    disk = pages_mod.load_page(pid) or {}
                    disk_ec = str(disk.get("existing_copy") or "")
                    if disk_ec != body:
                        st.error(
                            "Сейв не подтвердился на диске "
                            f"(ожидали {len(body)} симв., на диске {len(disk_ec)}). "
                            "Попробуйте ещё раз."
                        )
                    else:
                        seed = pages_mod.refresh_structure_seed(pid)
                        st.session_state[f"site_struct_pending_{pid}"] = seed
                        _sync_ec_editor_from_disk(pid, disk_ec)
                        st.success(f"Сохранено на диск: {len(disk_ec)} символов")
                        st.rerun()
                elif llm_ec:
                    body = (edited_ec or "").strip()
                    if body and body != ec.strip():
                        pages_mod.set_existing_copy(
                            pid,
                            body,
                            source_url=str(page.get("source_url") or ""),
                            action=str(page.get("action") or "rewrite"),
                        )
                    client = LLMClient(cfg)
                    ok, msg = client.ping()
                    if not ok:
                        st.error(msg)
                    else:
                        box = st.empty()
                        with st.spinner("Чистим existing_copy…"):
                            res = spp.clean_existing_copy(
                                pid,
                                client=client,
                                config=cfg,
                                progress=lambda m: box.caption(m),
                            )
                        if res.ok:
                            seed = pages_mod.refresh_structure_seed(pid)
                            st.session_state[f"site_struct_pending_{pid}"] = seed
                            _sync_ec_editor_from_disk(pid, res.text)
                            st.success(
                                f"Очищено: было {len(ec)} → стало {len(res.text)} симв. "
                                f"(снимок: `{res.path.name if res.path else '—'}`)"
                            )
                            st.rerun()
                        else:
                            st.error(res.error)
                elif wipe_ec:
                    pages_mod.set_existing_copy(
                        pid, "none", source_url="", action="write"
                    )
                    _sync_ec_editor_from_disk(pid, "none")
                    st.rerun()
        elif src == "Уже в файле":
            st.info("В спеке пока нет existing_copy — загрузите URL или вставьте текст.")

        st.markdown("##### Вводные редактора")
        st.caption(
            "Свободные требования: блоки, факты, tone, что добавить/убрать. "
            "Сюда же можно вставить подготовленные заголовки раздела — "
            "на шаге 2 их можно зафиксировать как структуру."
        )
        editor_inputs = st.text_area(
            "Вводные",
            value=str(page.get("editor_inputs") or ""),
            height=160,
            key=f"site_editor_inputs_{pid}",
        )
        page_notes = st.text_area(
            "Замечания ко всей странице (для перегенерации)",
            value=str(page.get("page_notes") or ""),
            height=100,
            key=f"site_page_notes_{pid}",
            placeholder="Напр.: убрать hype, усилить cash-first, FAQ короче…",
        )

        if st.button("Сохранить вводные", type="primary", key=f"site_save_inputs_{pid}"):
            page = pages_mod.load_page(pid) or page
            page["action"] = mode
            page["editor_inputs"] = editor_inputs
            page["page_notes"] = page_notes
            pages_mod.save_page(pid, page)
            # пересобрать черновик структуры для шага 2
            seed = pages_mod.refresh_structure_seed(pid)
            st.session_state[f"site_struct_pending_{pid}"] = seed
            st.session_state[f"site_struct_fresh_{pid}"] = True
            n_head = seed.count("- **")
            st.success(
                f"Сохранено. Для шага 2 подготовлен черновик структуры"
                + (f" ({n_head} заголовков из страницы)." if n_head else ".")
            )
            st.rerun()

        with st.expander("JSON спеки / brief (для тонкой настройки)", expanded=False):
            briefs = briefs_mod.list_briefs() or ["default"]
            bid = st.selectbox("Brief", options=briefs, key="brief_select")
            brief = briefs_mod.load_brief(bid)
            brief_text = st.text_area(
                "JSON brief",
                value=_json.dumps(brief, ensure_ascii=False, indent=2),
                height=200,
                key=f"brief_json_{bid}",
            )
            if st.button("Сохранить brief", key=f"site_save_brief_{bid}"):
                try:
                    briefs_mod.save_brief(bid, _json.loads(brief_text))
                    st.success("OK")
                except Exception as exc:  # noqa: BLE001
                    st.error(str(exc))

            # Versioned JSON editor: иначе после правки existing_copy старый
            # дамп в session_state откатывал файл при «Сохранить JSON page».
            pj_ver_key = f"page_json_ver_{pid}"
            if pj_ver_key not in st.session_state:
                st.session_state[pj_ver_key] = 0
            if st.session_state.pop(f"page_json_bump_{pid}", False):
                st.session_state[pj_ver_key] = int(st.session_state[pj_ver_key]) + 1
            pj_key = f"page_json_{pid}_v{st.session_state[pj_ver_key]}"
            fresh_page = pages_mod.load_page(pid) or page
            if pj_key not in st.session_state:
                st.session_state[pj_key] = _json.dumps(
                    fresh_page, ensure_ascii=False, indent=2
                )
            page_text = st.text_area(
                "JSON page",
                height=260,
                key=pj_key,
            )
            if st.button("Сохранить JSON page", key=f"site_save_json_{pid}"):
                try:
                    parsed = _json.loads(page_text)
                    pages_mod.save_page(pid, parsed)
                    disk_ec = str(
                        (pages_mod.load_page(pid) or {}).get("existing_copy") or ""
                    )
                    seed = pages_mod.refresh_structure_seed(pid)
                    st.session_state[f"site_struct_pending_{pid}"] = seed
                    _sync_ec_editor_from_disk(pid, disk_ec)
                    st.success(
                        f"OK · existing_copy на диске: {len(disk_ec)} симв."
                    )
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.error(str(exc))

    # =====================================================================
    # STEP 2 — structure
    # =====================================================================
    elif step == "2_structure":
        st.markdown("#### Структура и содержание страницы")
        st.caption(
            "Черновик ниже: **existing_copy** (заголовки) + **вводные**. "
            "Для живой страницы: **Обогатить структуру (ресёрч)** — уточняет роли "
            "и добавляет пробелы must_include/job; затем на шаге 3 — "
            "**Точечный проход**. «С нуля» — только если дерево не годится."
        )
        page = pages_mod.load_page(pid) or page
        outline = page.get("outline") or {}
        sections = outline.get("sections") or []

        # Отдельное хранилище текста + версия key виджета (иначе Streamlit
        # запрещает писать в session_state после text_area).
        data_key = f"site_struct_data_{pid}"
        ver_key = f"site_struct_ver_{pid}"
        pending_key = f"site_struct_pending_{pid}"

        if ver_key not in st.session_state:
            st.session_state[ver_key] = 0

        def _set_struct_md(text: str) -> None:
            st.session_state[pending_key] = text if text is not None else ""

        # Применить отложенное обновление ДО создания text_area
        if pending_key in st.session_state:
            st.session_state[data_key] = st.session_state.pop(pending_key)
            st.session_state[ver_key] = int(st.session_state[ver_key]) + 1
        elif st.session_state.pop(f"site_struct_fresh_{pid}", False):
            st.session_state[data_key] = str(
                page.get("structure_seed")
                or pages_mod.build_structure_seed(page, prefer_outline=False)
                or ""
            )
            st.session_state[ver_key] = int(st.session_state[ver_key]) + 1
        elif data_key not in st.session_state:
            st.session_state[data_key] = pages_mod.build_structure_seed(page)

        widget_key = f"site_struct_md_{pid}_v{st.session_state[ver_key]}"
        if widget_key not in st.session_state:
            st.session_state[widget_key] = st.session_state.get(data_key, "")

        ec = str(page.get("existing_copy") or "")
        has_copy = ec.strip() and ec.strip().lower() != "none"
        inputs = str(page.get("editor_inputs") or "").strip()
        st.info(
            f"Вводные: **{len(inputs)}** симв. · existing_copy: "
            f"**{len(ec) if has_copy else 0}** симв. · action=`{page.get('action')}`"
        )
        if sections:
            st.warning(
                f"Уже зафиксирована структура (**{len(sections)}** секций). "
                "Поле ниже можно заменить черновиком из existing_copy "
                "(кнопка «Подтянуть…»), затем снова «Зафиксировать»."
            )

        c_pull, c_inputs, c_clear = st.columns(3)
        with c_pull:
            if st.button(
                "Подтянуть из existing_copy + вводных",
                use_container_width=True,
                key=f"site_pull_struct_{pid}",
                disabled=not (has_copy or inputs),
            ):
                _set_struct_md(pages_mod.refresh_structure_seed(pid))
                st.rerun()
        with c_inputs:
            if st.button(
                "Только вводные → поле",
                use_container_width=True,
                key=f"site_pull_inputs_{pid}",
                disabled=not inputs,
            ):
                _set_struct_md(
                    f"## Editor notes\n{inputs}\n\n## Outline\n"
                    "- **…** — роль секции"
                )
                st.rerun()
        with c_clear:
            if st.button(
                "Очистить поле MD",
                use_container_width=True,
                key=f"site_clear_struct_md_{pid}",
            ):
                _set_struct_md("")
                st.rerun()

        md_in = st.text_area(
            "MD структуры (## Outline или список заголовков)",
            height=280,
            key=widget_key,
        )
        # синхронизируем data_key с тем, что пользователь набрал
        st.session_state[data_key] = md_in

        b1, b2, b3, b4 = st.columns(4)
        with b1:
            if st.button(
                "Зафиксировать MD как структуру",
                type="primary",
                use_container_width=True,
                key=f"site_lock_md_{pid}",
            ):
                try:
                    o = pages_mod.import_outline_md(pid, md_in)
                    p = pages_mod.load_page(pid) or page
                    p["structure_seed"] = md_in
                    pages_mod.save_page(pid, p)
                    st.success(f"Секций: {len(o['sections'])}")
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.error(str(exc))
        with b2:
            if st.button(
                "Обогатить структуру (ресёрч)",
                use_container_width=True,
                key=f"site_enrich_outline_{pid}",
                help="Текущие заголовки + must_include / job / objections / "
                "package из спеки → обновлённый outline. Драфты сохраняются "
                "по совпадению заголовков.",
            ):
                if md_in.strip():
                    p = pages_mod.load_page(pid) or page
                    p["structure_seed"] = md_in.strip()
                    pages_mod.save_page(pid, p)
                client = LLMClient(cfg)
                ok, msg = client.ping()
                if not ok:
                    st.error(msg)
                else:
                    box = st.empty()
                    with st.spinner("Обогащаем структуру ресёрчем…"):
                        res = spp.enrich_outline_from_research(
                            pid,
                            client=client,
                            language=sec_lang,
                            draft_md=md_in,
                            progress=lambda m: box.caption(m),
                        )
                    if res.ok:
                        _set_struct_md(res.text)
                        st.success(
                            f"Обогащено: {len(res.sections)} секций → `{res.path}` "
                            "(драфты rematch по заголовкам)"
                        )
                        st.rerun()
                    else:
                        st.error(res.error)
                        if res.text:
                            st.code(res.text[:4000])
        with b3:
            if st.button(
                "Сгенерировать структуру с нуля (LLM)",
                use_container_width=True,
                key=f"site_gen_outline_{pid}",
                help="Greenfield outline из спеки. Для правки действующей "
                "страницы лучше «Обогатить структуру».",
            ):
                p = pages_mod.load_page(pid) or page
                if md_in.strip():
                    p["structure_seed"] = md_in
                    note = str(p.get("editor_inputs") or "").strip()
                    if md_in.strip() not in note:
                        p["editor_inputs"] = (
                            (note + "\n\n" if note else "")
                            + "Structure draft from editor:\n"
                            + md_in.strip()
                        )
                    pages_mod.save_page(pid, p)
                client = LLMClient(cfg)
                ok, msg = client.ping()
                if not ok:
                    st.error(msg)
                else:
                    box = st.empty()
                    with st.spinner("Outline…"):
                        res = spp.generate_outline(
                            pid,
                            client=client,
                            language=sec_lang,
                            progress=lambda m: box.caption(m),
                        )
                    if res.ok:
                        _set_struct_md(res.text)
                        st.success(f"{len(res.sections)} секций → `{res.path}`")
                        st.rerun()
                    else:
                        st.error(res.error)
                        if res.text:
                            st.code(res.text[:4000])
        with b4:
            if st.button(
                "Сбросить зафиксированную структуру",
                use_container_width=True,
                key=f"site_reset_outline_{pid}",
            ):
                p = pages_mod.load_page(pid) or page
                p["outline"] = {}
                p["sections_draft"] = {}
                p["section_edit_history"] = {}
                pages_mod.save_page(pid, p)
                _set_struct_md(pages_mod.refresh_structure_seed(pid))
                st.rerun()

        page = pages_mod.load_page(pid) or page
        outline = page.get("outline") or {}
        sections = outline.get("sections") or []
        if sections:
            st.success(f"Структура зафиксирована: **{len(sections)}** секций")
            meta = outline.get("meta") or {}
            if meta:
                st.caption(
                    f"Title: {meta.get('title') or '—'} · H1: {meta.get('h1') or '—'}"
                )
            if outline.get("page_job"):
                st.markdown(f"**Page job:** {outline['page_job']}")
            ec_now = str(page.get("existing_copy") or "").strip()
            if ec_now and ec_now.lower() != "none":
                sc1, sc2 = st.columns(2)
                with sc1:
                    if st.button(
                        "Разложить existing_copy по секциям",
                        key=f"seed_from_ec_{pid}",
                        use_container_width=True,
                        help="Нарезает сохранённый текст по заголовкам outline → sections_draft "
                        "для точечного improve (не с нуля).",
                    ):
                        info = pages_mod.seed_section_drafts_from_existing(
                            pid, overwrite=False
                        )
                        if info.get("ok"):
                            st.success(
                                f"Засеяно: {info.get('seeded')} · "
                                f"пропущено (уже есть): {info.get('skipped')} · "
                                f"без матча: {len(info.get('unmatched_sections') or [])}"
                            )
                            if info.get("unmatched_sections"):
                                st.caption(
                                    "Не найдены в тексте: "
                                    + ", ".join(info["unmatched_sections"])
                                )
                            st.rerun()
                        else:
                            st.error(info.get("error") or "Не удалось")
                with sc2:
                    if st.button(
                        "Перезаписать драфты из existing",
                        key=f"seed_overwrite_{pid}",
                        use_container_width=True,
                    ):
                        info = pages_mod.seed_section_drafts_from_existing(
                            pid, overwrite=True
                        )
                        if info.get("ok"):
                            st.success(f"Перезаписано секций: {info.get('seeded')}")
                            st.rerun()
                        else:
                            st.error(info.get("error") or "Не удалось")
            for sec in sections:
                if not isinstance(sec, dict):
                    continue
                sid_o = str(sec.get("id") or "")
                removed = pages_mod.is_section_removed(sec)
                drafts_now = page.get("sections_draft") or {}
                has_draft = bool(str(drafts_now.get(sid_o) or "").strip())
                seeded_mark = " · из existing" if sec.get("seeded_from_existing") else ""
                draft_mark = " · draft" if has_draft and not removed else ""
                label = (
                    f"- ~~`{sid_o}` **{sec.get('heading')}** — "
                    f"{sec.get('role') or '_без роли_'}~~ _(удалена)_"
                    if removed
                    else (
                        f"- `{sid_o}` **{sec.get('heading')}** — "
                        f"{sec.get('role') or '_без роли_'}"
                        f"{draft_mark}{seeded_mark}"
                    )
                )
                c_lab, c_btn = st.columns([5, 1])
                with c_lab:
                    st.markdown(label)
                with c_btn:
                    if removed:
                        if st.button(
                            "Вернуть",
                            key=f"restore_o_{pid}_{sid_o}",
                            use_container_width=True,
                        ):
                            pages_mod.restore_section(pid, sid_o)
                            st.rerun()
                    else:
                        if st.button(
                            "Удалить",
                            key=f"rm_o_{pid}_{sid_o}",
                            use_container_width=True,
                        ):
                            pages_mod.remove_section(pid, sid_o)
                            st.rerun()
        else:
            st.warning(
                "Структура ещё не зафиксирована. Отредактируйте MD выше и нажмите "
                "«Зафиксировать», либо «Сгенерировать структуру (LLM)»."
            )
    # =====================================================================
    # STEP 3 — content
    # =====================================================================
    elif step == "3_content":
        st.markdown("#### Генерация контента по структуре")
        page = pages_mod.load_page(pid) or page
        outline = page.get("outline") or {}
        sections = outline.get("sections") or []
        drafts = page.get("sections_draft") or {}

        def _flush_notes_from_ui() -> str:
            """Сбросить замечания из session_state на диск до генерации."""
            pn_key = f"site_c_page_notes_{pid}"
            pn = str(st.session_state.get(pn_key, page.get("page_notes") or ""))
            p = pages_mod.load_page(pid) or page
            p["page_notes"] = pn.strip()
            pages_mod.save_page(pid, p)
            for sec in sections:
                if not isinstance(sec, dict):
                    continue
                sid_f = str(sec.get("id") or "")
                if not sid_f:
                    continue
                nkey = f"sec_note_{pid}_{sid_f}"
                if nkey in st.session_state:
                    pages_mod.set_section_notes(
                        pid, sid_f, str(st.session_state.get(nkey) or "")
                    )
            return pn.strip()

        if not sections:
            st.warning("Сначала шаг 2 — структура.")
        else:
            pn_key = f"site_c_page_notes_{pid}"
            if pn_key not in st.session_state:
                st.session_state[pn_key] = str(page.get("page_notes") or "")
            page_notes = st.text_area(
                "Замечания ко всей странице (учитываются при любой перегенерации)",
                height=80,
                key=pn_key,
            )
            if st.button("Сохранить замечания страницы", key=f"save_pn_{pid}"):
                p = pages_mod.load_page(pid) or page
                p["page_notes"] = page_notes
                pages_mod.save_page(pid, p)
                st.success("OK")

            gen_mode = st.radio(
                "Режим",
                ["sections", "full"],
                format_func=lambda m: (
                    "Посекционно"
                    if m == "sections"
                    else "Целиком (один проход Full draft)"
                ),
                horizontal=True,
                key=f"site_gen_mode_{pid}",
            )
            _bm_opts = block_model_options(cfg)
            _bm_vals = [v for v, _ in _bm_opts]
            _bm_default = (
                "ensemble"
                if getattr(cfg, "ensemble_enabled", False) and "ensemble" in _bm_vals
                else "primary"
            )
            page_block_model = st.selectbox(
                "Модель для генерации / Anti-AI / перегенерации (по умолчанию)",
                options=_bm_vals,
                index=_bm_vals.index(_bm_default)
                if _bm_default in _bm_vals
                else 0,
                format_func=lambda v: dict(_bm_opts).get(v, v),
                key=f"site_block_model_{pid}",
                help="Primary = сайдбар LLM · Hydra = gpt-6-luna · "
                "Ансамбль = чередование абзацев. В каждом блоке можно переопределить.",
            )
            if page_block_model == "ensemble":
                st.caption(
                    f"Ансамбль: `{cfg.model}` ↔ "
                    f"`{getattr(cfg, 'ensemble_model', 'gpt-6-luna')}` "
                    f"(макс. {getattr(cfg, 'ensemble_max_paragraphs', 8)} ¶ на write)."
                )

            if gen_mode == "full":
                if st.button(
                    "Сгенерировать всю страницу",
                    type="primary",
                    key=f"site_full_gen_{pid}",
                ):
                    _flush_notes_from_ui()
                    client = LLMClient(cfg)
                    ok, msg = client.ping()
                    if not ok:
                        st.error(msg)
                    else:
                        with st.spinner("Full package…"):
                            msgs = spp.build_site_page_messages(
                                pid, phase="full", language=sec_lang
                            )
                            text = spp._chat_with_language_guard(
                                client,
                                msgs,
                                language=sec_lang,
                            )
                            path = spp.guide_path_for_page(pid, language=sec_lang)
                            path.parent.mkdir(parents=True, exist_ok=True)
                            path.write_text(text, encoding="utf-8")
                        st.success(f"Сохранено → `{path}` · lang=`{sec_lang}`")
                        st.markdown(text[:8000])
            else:
                st.markdown("##### Пакетные режимы")
                plan = pages_mod.preview_editorial_plan(pid)
                plan_rows = plan.get("sections") or []
                counts = plan.get("counts") or {}
                # bulk select ДО чекбоксов (после виджета key менять нельзя)
                bulk_sel = st.session_state.pop(f"edit_plan_bulk_{pid}", None)
                if bulk_sel is not None and plan_rows:
                    for row in plan_rows:
                        sid_b = str(row.get("id") or "")
                        key_b = f"edit_plan_incl_{pid}_{sid_b}"
                        if bulk_sel == "all":
                            st.session_state[key_b] = bool(row.get("will_touch"))
                        else:
                            st.session_state[key_b] = False
                with st.expander(
                    "План точечного прохода — что будет правиться",
                    expanded=True,
                ):
                    st.caption(
                        f"improve: **{counts.get('improve', 0)}** · "
                        f"seed→improve: **{counts.get('seed_then_improve', 0)}** · "
                        f"пропуск (NEW): **{counts.get('skip_new', 0)}** · "
                        f"пусто: **{counts.get('skip_empty', 0)}**. "
                        "Снимите галочку, чтобы **не** трогать секцию."
                    )
                    selected_ids: list[str] = []
                    if not plan_rows:
                        st.info("Нет активных секций — сначала шаг 2.")
                    else:
                        h1, h2, h3 = st.columns([0.8, 3.2, 3])
                        h1.markdown("**Вкл**")
                        h2.markdown("**Секция**")
                        h3.markdown("**Действие**")
                        for row in plan_rows:
                            sid_p = str(row.get("id") or "")
                            will = bool(row.get("will_touch"))
                            key_p = f"edit_plan_incl_{pid}_{sid_p}"
                            if key_p not in st.session_state:
                                st.session_state[key_p] = bool(
                                    row.get("default_include")
                                )
                            ck, c_sec, c_act = st.columns([0.8, 3.2, 3])
                            with ck:
                                on = st.checkbox(
                                    f"incl_{sid_p}",
                                    key=key_p,
                                    label_visibility="collapsed",
                                    disabled=not will,
                                )
                            with c_sec:
                                mark = "✏️" if will else "⏭"
                                st.markdown(
                                    f"{mark} `{sid_p}` **{row.get('heading') or '—'}**  \n"
                                    f"<span style='color:#888;font-size:0.85em'>"
                                    f"{row.get('reason') or ''}</span>",
                                    unsafe_allow_html=True,
                                )
                            with c_act:
                                st.caption(str(row.get("action_label") or ""))
                            if on and will:
                                selected_ids.append(sid_p)
                        c_sel_all, c_sel_none = st.columns(2)
                        with c_sel_all:
                            if st.button(
                                "Выбрать все правимые",
                                key=f"edit_plan_all_{pid}",
                                use_container_width=True,
                            ):
                                st.session_state[f"edit_plan_bulk_{pid}"] = "all"
                                st.rerun()
                        with c_sel_none:
                            if st.button(
                                "Снять все",
                                key=f"edit_plan_none_{pid}",
                                use_container_width=True,
                            ):
                                st.session_state[f"edit_plan_bulk_{pid}"] = "none"
                                st.rerun()

                c_edit, c_all, c_miss = st.columns(3)
                with c_edit:
                    run_n = len(selected_ids) if plan_rows else 0
                    if st.button(
                        f"Точечный проход ({run_n})",
                        type="primary",
                        use_container_width=True,
                        key=f"site_editorial_pass_{pid}",
                        disabled=run_n == 0,
                        help="Только отмеченные секции: seed из existing при необходимости "
                        "→ improve (сохранить текст, дописать пробелы ресёрча).",
                    ):
                        _flush_notes_from_ui()
                        bulk_client, bulk_ens = client_for_block_model(
                            cfg, page_block_model
                        )
                        box = st.empty()
                        with st.spinner(
                            f"Точечный проход: {run_n} секций…"
                        ):
                            results = spp.editorial_improve_pass(
                                pid,
                                client=bulk_client,
                                config=cfg,
                                language=sec_lang,
                                progress=lambda m: box.caption(m),
                                ensemble=bulk_ens,
                                seed_from_existing=True,
                                only_with_draft=True,
                                auto_gap_notes=True,
                                section_ids=selected_ids,
                            )
                        fails = [r for r in results if not r.ok]
                        ok_n = sum(1 for r in results if r.ok)
                        if fails and not ok_n:
                            st.error(fails[0].error)
                        elif fails:
                            st.warning(
                                f"Частично: OK {ok_n}, ошибка — {fails[0].error}"
                            )
                            st.rerun()
                        elif not results:
                            st.warning(
                                "Ничего не сделано. Отметьте секции в плане "
                                "или сначала разложите existing_copy."
                            )
                        else:
                            st.success(f"Точечный проход: {ok_n} секций")
                            st.rerun()
                with c_all:
                    if st.button(
                        "Все секции заново",
                        use_container_width=True,
                        key=f"site_all_secs_{pid}",
                    ):
                        _flush_notes_from_ui()
                        bulk_client, bulk_ens = client_for_block_model(
                            cfg, page_block_model
                        )
                        box = st.empty()
                        with st.spinner("Все секции…"):
                            # clear drafts statuses by regenerating all
                            p = pages_mod.load_page(pid) or page
                            p["sections_draft"] = {}
                            p["section_edit_history"] = {}
                            pages_mod.save_page(pid, p)
                            results = spp.generate_all_sections(
                                pid,
                                only_missing=False,
                                mode="write",
                                client=bulk_client,
                                config=cfg,
                                language=sec_lang,
                                progress=lambda m: box.caption(m),
                                ensemble=bulk_ens,
                            )
                        fails = [r for r in results if not r.ok]
                        if fails:
                            st.error(fails[0].error)
                        else:
                            st.success(f"Готово: {len(results)}")
                            st.rerun()
                with c_miss:
                    if st.button(
                        "Только недостающие",
                        use_container_width=True,
                        key=f"site_miss_secs_{pid}",
                    ):
                        _flush_notes_from_ui()
                        bulk_client, bulk_ens = client_for_block_model(
                            cfg, page_block_model
                        )
                        box = st.empty()
                        with st.spinner("Недостающие…"):
                            results = spp.generate_all_sections(
                                pid,
                                only_missing=True,
                                mode="write",
                                client=bulk_client,
                                config=cfg,
                                language=sec_lang,
                                progress=lambda m: box.caption(m),
                                ensemble=bulk_ens,
                            )
                        fails = [r for r in results if not r.ok]
                        if fails:
                            st.error(fails[0].error)
                        else:
                            st.success(f"Готово: {len(results)}")
                            st.rerun()

                st.markdown("##### 2-й цикл: жёсткий Anti-AI pass")
                st.caption(
                    "Локальные правила + **IGTL AI-Humanizer** "
                    "([IGTL-SKILLS](https://github.com/igamingtextlab/IGTL-SKILLS), CC BY 4.0): "
                    "маркеры, iGaming-лексикон, ритм, checklist. "
                    "Не синонимизировать пену — факт из брифа или вырезка / `[PLACEHOLDER]`. "
                    "Эвристики → точечная правка. Черновик: `*.pre_antia.md`. "
                    "Модель — из селектора выше (Hydra / Ансамбль по абзацам)."
                )
                force_deai = st.checkbox(
                    "Гнать все секции, даже без явных паттернов",
                    value=True,
                    key=f"site_antia_force_{pid}",
                )
                c_deai_all, c_scan = st.columns(2)
                with c_deai_all:
                    if st.button(
                        "Anti-AI pass · все секции",
                        type="primary",
                        use_container_width=True,
                        key=f"site_antia_all_{pid}",
                    ):
                        antia_client, antia_ens = client_for_block_model(
                            cfg, page_block_model
                        )
                        ok, msg = antia_client.ping()
                        if not ok:
                            st.error(msg)
                        else:
                            box = st.empty()
                            with st.spinner(
                                "Anti-AI ensemble…"
                                if antia_ens
                                else f"Anti-AI · {antia_client.config.model}…"
                            ):
                                results = spp.antia_pass_all_sections(
                                    pid,
                                    client=antia_client,
                                    config=cfg,
                                    language=sec_lang,
                                    progress=lambda m: box.caption(m),
                                    force=bool(force_deai),
                                    only_with_patterns=not bool(force_deai),
                                    ensemble=antia_ens,
                                )
                            fails = [r for r in results if not r.ok]
                            if fails:
                                st.error(fails[0].error)
                            else:
                                st.success(f"Anti-AI pass: {len(results)} секций")
                                st.rerun()
                with c_scan:
                    if st.button(
                        "Только сканировать паттерны",
                        use_container_width=True,
                        key=f"site_antia_scan_{pid}",
                    ):
                        from src.content.anti_ai import scan_ai_patterns

                        p = pages_mod.load_page(pid) or page
                        lines = []
                        for sec in (p.get("outline") or {}).get("sections") or []:
                            if not isinstance(sec, dict):
                                continue
                            sid = str(sec.get("id") or "")
                            body = str((p.get("sections_draft") or {}).get(sid) or "")
                            pats = scan_ai_patterns(body)
                            lines.append(
                                f"`{sid}` {sec.get('heading')}: "
                                + (", ".join(pats) if pats else "чисто")
                            )
                        st.code("\n".join(lines) or "нет драфтов")

                st.markdown("##### ZeroGPT: редактура по жёлтым")
                st.caption(
                    "Браузер забирает жёлтые спаны с [zerogpt.com](https://www.zerogpt.com/). "
                    "Дальше не «переписать всё жёлтое», а оценка: "
                    "**зачем флаг → нужен ли смысл → rewrite / compress / delete / keep**. "
                    f"Язык `new`: **{LANGUAGES[sec_lang]['name_en']}** (`{sec_lang}`). "
                    "Лимит проверки: **15 000** символов на секцию. "
                    "После редакции сразу повторный ZeroGPT и показ %. "
                    "Пену лучше удалить, чем синонимизировать."
                )
                zg_headless = st.checkbox(
                    "ZeroGPT headless (без окна браузера)",
                    value=True,
                    key=f"zg_headless_{pid}",
                )
                if st.button(
                    "Установить / починить Playwright Chromium",
                    key=f"zg_install_pw_{pid}",
                    help="Нужно один раз на Cloud после деплоя, если ZeroGPT пишет про Playwright.",
                ):
                    from src.content.zerogpt import ensure_playwright_chromium

                    with st.spinner("playwright install chromium… (1–3 мин)"):
                        ok_pw, msg_pw = ensure_playwright_chromium(force=True)
                    if ok_pw:
                        st.success(msg_pw)
                    else:
                        st.error(msg_pw)
                zg_manual = st.text_area(
                    "Ручные highlights (если браузер недоступен)",
                    height=100,
                    key=f"zg_manual_{pid}",
                    placeholder="Одно подсвеченное предложение на строку…",
                )
                zg_sid = st.selectbox(
                    "Секция для ZeroGPT",
                    options=[
                        str(s.get("id"))
                        for s in pages_mod.active_sections(page)
                        if str((drafts.get(str(s.get("id"))) or "")).strip()
                    ]
                    or [""],
                    key=f"zg_sid_{pid}",
                )
                z1, z2, z3 = st.columns(3)
                with z1:
                    if st.button(
                        "Проверить в браузере",
                        use_container_width=True,
                        key=f"zg_check_{pid}",
                        disabled=not zg_sid,
                    ):
                        from src.content.zerogpt import check_text_via_browser

                        body = str(drafts.get(zg_sid) or "")
                        with st.spinner(
                            "ZeroGPT… (если первый раз — качаем Chromium)"
                        ):
                            zg = check_text_via_browser(
                                body, headless=bool(zg_headless)
                            )
                        if not zg.ok:
                            st.error(zg.error)
                        else:
                            st.session_state[f"zg_result_{pid}_{zg_sid}"] = {
                                "ai_percent": zg.ai_percent,
                                "highlighted": zg.highlighted,
                            }
                            st.success(
                                f"{zg.ai_percent}% AI · "
                                f"{len(zg.highlighted)} подсвеченных предложений"
                            )
                            st.code("\n\n".join(zg.highlighted) or "(пусто)")
                with z2:
                    if st.button(
                        "Редакторский проход",
                        type="primary",
                        use_container_width=True,
                        key=f"zg_fix_{pid}",
                        disabled=not zg_sid,
                    ):
                        from src.content.zerogpt import parse_manual_highlights

                        cached = st.session_state.get(f"zg_result_{pid}_{zg_sid}") or {}
                        highlights = list(cached.get("highlighted") or [])
                        if zg_manual.strip():
                            highlights = parse_manual_highlights(zg_manual)
                        client = LLMClient(cfg)
                        box = st.empty()
                        with st.spinner(
                            "Оценка флагов → rewrite → повторный ZeroGPT…"
                        ):
                            res = spp.zerogpt_rewrite_section(
                                pid,
                                zg_sid,
                                highlighted=highlights,
                                client=client,
                                language=sec_lang,
                                headless_browser=bool(zg_headless),
                                run_browser_check=not bool(highlights),
                                recheck_after=True,
                                progress=lambda m: box.caption(m),
                            )
                        if res.ok:
                            rep = (
                                (pages_mod.load_page(pid) or {}).get("zerogpt_reports")
                                or {}
                            ).get(zg_sid) or {}
                            after = rep.get("ai_percent_after")
                            if after is not None:
                                st.session_state[f"zg_result_{pid}_{zg_sid}"] = {
                                    "ai_percent": after,
                                    "highlighted": list(
                                        rep.get("highlighted_after") or []
                                    ),
                                }
                                st.session_state[f"zg_flash_{pid}"] = (
                                    f"После редакции **{zg_sid}**: "
                                    f"**{after}%** AI"
                                    + (
                                        f" (было {rep.get('ai_percent')}%)"
                                        if rep.get("ai_percent") is not None
                                        else ""
                                    )
                                )
                            else:
                                st.session_state[f"zg_flash_{pid}"] = (
                                    res.error or "OK"
                                ) + (
                                    f" · re-check: {rep.get('recheck_error')}"
                                    if rep.get("recheck_error")
                                    else ""
                                )
                            st.rerun()
                        else:
                            st.error(res.error)
                with z3:
                    if st.button(
                        "Check + редакция (авто)",
                        use_container_width=True,
                        key=f"zg_auto_{pid}",
                        disabled=not zg_sid,
                    ):
                        client = LLMClient(cfg)
                        box = st.empty()
                        with st.spinner(
                            "ZeroGPT → редакция → повторный ZeroGPT…"
                        ):
                            res = spp.zerogpt_rewrite_section(
                                pid,
                                zg_sid,
                                highlighted=[],
                                client=client,
                                language=sec_lang,
                                headless_browser=bool(zg_headless),
                                run_browser_check=True,
                                recheck_after=True,
                                progress=lambda m: box.caption(m),
                            )
                        if res.ok:
                            rep = (
                                (pages_mod.load_page(pid) or {}).get("zerogpt_reports")
                                or {}
                            ).get(zg_sid) or {}
                            after = rep.get("ai_percent_after")
                            if after is not None:
                                st.session_state[f"zg_result_{pid}_{zg_sid}"] = {
                                    "ai_percent": after,
                                    "highlighted": list(
                                        rep.get("highlighted_after") or []
                                    ),
                                }
                                st.session_state[f"zg_flash_{pid}"] = (
                                    f"После редакции **{zg_sid}**: "
                                    f"**{after}%** AI"
                                    + (
                                        f" (было {rep.get('ai_percent')}%)"
                                        if rep.get("ai_percent") is not None
                                        else ""
                                    )
                                )
                            else:
                                st.session_state[f"zg_flash_{pid}"] = (
                                    res.error or "OK"
                                )
                            st.rerun()
                        else:
                            st.error(res.error)

                flash = st.session_state.pop(f"zg_flash_{pid}", None)
                if flash:
                    st.success(flash)

                # последний отчёт по решениям
                zg_rep = ((pages_mod.load_page(pid) or {}).get("zerogpt_reports") or {}).get(
                    zg_sid or ""
                )
                if isinstance(zg_rep, dict) and (
                    zg_rep.get("edits")
                    or zg_rep.get("ai_percent") is not None
                    or zg_rep.get("ai_percent_after") is not None
                ):
                    before_pct = zg_rep.get("ai_percent")
                    after_pct = zg_rep.get("ai_percent_after")
                    if after_pct is not None or before_pct is not None:
                        st.info(
                            "ZeroGPT: "
                            + (
                                f"до редакции **{before_pct}%**"
                                if before_pct is not None
                                else "до редакции —"
                            )
                            + " → "
                            + (
                                f"после **{after_pct}%**"
                                if after_pct is not None
                                else (
                                    f"re-check: {zg_rep.get('recheck_error')}"
                                    if zg_rep.get("recheck_error")
                                    else "после — нет данных"
                                )
                            )
                        )
                    if zg_rep.get("edits"):
                        with st.expander(
                            "Последние решения ZeroGPT-редакции", expanded=False
                        ):
                            counts = zg_rep.get("counts") or {}
                            st.caption(
                                f"rewrite={counts.get('rewrite', 0)} · "
                                f"compress={counts.get('compress', 0)} · "
                                f"delete={counts.get('delete', 0)} · "
                                f"keep={counts.get('keep', 0)}"
                                + (
                                    f" · was {zg_rep.get('ai_percent')}%"
                                    if zg_rep.get("ai_percent") is not None
                                    else ""
                                )
                                + (
                                    f" · now {zg_rep.get('ai_percent_after')}%"
                                    if zg_rep.get("ai_percent_after") is not None
                                    else ""
                                )
                            )
                            lines = []
                            for ed in zg_rep.get("edits") or []:
                                if not isinstance(ed, dict):
                                    continue
                                lines.append(
                                    f"[{ed.get('action')}] {ed.get('flag_reason') or '—'}\n"
                                    f"  job: {ed.get('meaning_job') or '—'}\n"
                                    f"  why: {ed.get('decision') or '—'}\n"
                                    f"  old: {ed.get('old') or ''}\n"
                                    f"  new: {ed.get('new') or '(deleted)'}"
                                )
                            st.code("\n\n".join(lines) or "(пусто)")

                st.markdown("##### Секции")
                st.caption(
                    "Лишний блок — **Удалить**. "
                    "Редактура существующего: пакетный **Точечный проход (ресёрч)** "
                    "или посекционно **Перегенерировать с замечаниями**. "
                    "«Сгенерировать с нуля» / «Все секции заново» — полный rewrite."
                )
                ec_c = str(page.get("existing_copy") or "").strip()
                if ec_c and ec_c.lower() != "none":
                    if st.button(
                        "Разложить existing_copy → драфты секций",
                        key=f"seed_content_{pid}",
                    ):
                        info = pages_mod.seed_section_drafts_from_existing(
                            pid, overwrite=False
                        )
                        if info.get("ok"):
                            st.success(
                                f"Засеяно {info.get('seeded')}, "
                                f"пропущено {info.get('skipped')}, "
                                f"без матча {len(info.get('unmatched_sections') or [])}"
                            )
                            st.rerun()
                        else:
                            st.error(info.get("error") or "fail")
                for sec in sections:
                    if not isinstance(sec, dict):
                        continue
                    sid = str(sec.get("id") or "")
                    heading = str(sec.get("heading") or "")
                    role = str(sec.get("role") or "")
                    status = pages_mod.section_status(page, sid)
                    draft = str(drafts.get(sid) or "")
                    removed = status == "removed"
                    with st.expander(
                        f"[{status}] {sid}: {heading}",
                        expanded=(status == "pending"),
                    ):
                        if removed:
                            st.warning(
                                "Секция удалена из структуры — не входит в итоговый текст. "
                                "Драфт на диске сохранён."
                            )
                            if st.button(
                                "Вернуть секцию",
                                key=f"restore_c_{pid}_{sid}",
                                use_container_width=True,
                            ):
                                pages_mod.restore_section(pid, sid)
                                st.rerun()
                            if draft:
                                with st.expander("Черновик (не в сборке)", expanded=False):
                                    st.markdown(
                                        draft[:3000]
                                        + ("…" if len(draft) > 3000 else "")
                                    )
                            continue
                        st.caption(role or "—")
                        if draft:
                            from src.content.anti_ai import scan_ai_patterns

                            pats = scan_ai_patterns(draft)
                            if pats:
                                st.warning("Паттерны: " + "; ".join(pats))
                            else:
                                st.caption("Эвристики: явных LLM-паттернов не видно")
                            overlap = spp.scan_cross_section_overlap(
                                draft, page, sid
                            )
                            if overlap:
                                st.warning(
                                    "Смысловые повторы с другими секциями: "
                                    + "; ".join(overlap)
                                )
                        note_val = pages_mod.get_section_notes(page, sid)
                        note_key = f"sec_note_{pid}_{sid}"
                        if note_key not in st.session_state:
                            st.session_state[note_key] = note_val
                        note = st.text_area(
                            "Замечания к этой секции (обязательны при генерации / improve)",
                            height=80,
                            key=note_key,
                            placeholder="Что поправить / добавить / убрать в этой секции…",
                        )
                        if note.strip():
                            st.caption(f"В промпт уйдёт замечание ({len(note.strip())} симв.)")
                        hist_n = len(
                            pages_mod.get_section_edit_history(page, sid)
                        )
                        if hist_n:
                            st.caption(
                                f"История правок: **{hist_n}** проход(ов) "
                                "уйдёт в промпт (Anti-AI / improve / ZeroGPT)."
                            )
                        sec_model = st.selectbox(
                            "Модель блока",
                            options=_bm_vals,
                            index=_bm_vals.index(page_block_model)
                            if page_block_model in _bm_vals
                            else 0,
                            format_func=lambda v: dict(_bm_opts).get(v, v),
                            key=f"sec_model_{pid}_{sid}",
                        )
                        if draft:
                            # списки Pros/Cons как markdown `- `, иначе st.markdown схлопывает строки
                            shown = pages_mod.normalize_section_list_markup(draft)
                            st.markdown(
                                shown[:5000] + ("…" if len(shown) > 5000 else "")
                            )
                        bw, bi, ba, bs, bd = st.columns(5)
                        with bd:
                            if st.button(
                                "Удалить блок",
                                key=f"rm_c_{pid}_{sid}",
                                use_container_width=True,
                            ):
                                pages_mod.remove_section(pid, sid)
                                st.rerun()
                        with bw:
                            if draft.strip():
                                st.caption(
                                    "Есть драфт — для точечных правок лучше "
                                    "«Перегенерировать с замечаниями»."
                                )
                            gen_label = (
                                "Ансамбль ¶"
                                if sec_model == "ensemble"
                                else "Сгенерировать с нуля"
                            )
                            if st.button(
                                gen_label, key=f"w_{pid}_{sid}", use_container_width=True
                            ):
                                pn = _flush_notes_from_ui()
                                act_client, ens_on = client_for_block_model(
                                    cfg, sec_model
                                )
                                with st.spinner(
                                    f"{sid} · ensemble…"
                                    if ens_on
                                    else f"{sid} · {act_client.config.model}…"
                                ):
                                    res = spp.generate_section(
                                        pid,
                                        sid,
                                        mode="write",
                                        client=act_client,
                                        config=cfg,
                                        language=sec_lang,
                                        section_notes=note,
                                        page_notes=pn,
                                        ensemble=ens_on,
                                    )
                                if res.ok:
                                    st.rerun()
                                else:
                                    st.error(res.error)
                        with bi:
                            if st.button(
                                "Перегенерировать с замечаниями",
                                key=f"i_{pid}_{sid}",
                                use_container_width=True,
                            ):
                                pn = _flush_notes_from_ui()
                                act_client, ens_on = client_for_block_model(
                                    cfg, sec_model
                                )
                                with st.spinner(
                                    f"{sid} · improve ens…"
                                    if ens_on
                                    else f"{sid} · {act_client.config.model}…"
                                ):
                                    res = spp.generate_section(
                                        pid,
                                        sid,
                                        mode="improve",
                                        client=act_client,
                                        config=cfg,
                                        language=sec_lang,
                                        section_notes=note,
                                        page_notes=pn,
                                        ensemble=ens_on,
                                    )
                                if res.ok:
                                    st.rerun()
                                else:
                                    st.error(res.error)
                        with ba:
                            if st.button(
                                "Anti-AI pass",
                                key=f"a_{pid}_{sid}",
                                use_container_width=True,
                                disabled=not draft.strip(),
                            ):
                                _flush_notes_from_ui()
                                pages_mod.set_section_notes(pid, sid, note)
                                act_client, ens_on = client_for_block_model(
                                    cfg, sec_model
                                )
                                with st.spinner(
                                    f"Anti-AI {sid} ens…"
                                    if ens_on
                                    else f"Anti-AI {sid} · {act_client.config.model}…"
                                ):
                                    res = spp.antia_pass_section(
                                        pid,
                                        sid,
                                        client=act_client,
                                        config=cfg,
                                        language=sec_lang,
                                        force=True,
                                        ensemble=ens_on,
                                    )
                                if res.ok:
                                    st.rerun()
                                else:
                                    st.error(res.error)
                        with bs:
                            if st.button(
                                "Сохранить замечание",
                                key=f"n_{pid}_{sid}",
                                use_container_width=True,
                            ):
                                pages_mod.set_section_notes(pid, sid, note)
                                st.success("OK")

        with st.expander(
            "Эксперимент · тяжёлый флоу (не для продакшена)",
            expanded=False,
        ):
            st.warning(
                "По предложениям + динамическая temp на практике даёт **выше** "
                "AI-score, чем обычная генерация секции. "
                "Рабочий путь: Сгенерировать → Anti-AI → ZeroGPT."
            )
            st.caption(
                f"Язык: **{LANGUAGES[sec_lang]['name_en']}** (`{sec_lang}`). "
                "Код оставлен для сравнения, не для основного флоу."
            )
            hf_opts = [
                str(s.get("id")) for s in pages_mod.active_sections(page)
            ] or [""]
            hf_c1, hf_c2, hf_c3 = st.columns([2, 1, 1])
            with hf_c1:
                hf_sid = st.selectbox(
                    "Секция",
                    options=hf_opts,
                    key=f"hf_sid_{pid}",
                )
            with hf_c2:
                hf_max = st.number_input(
                    "Макс. предложений",
                    min_value=4,
                    max_value=24,
                    value=12,
                    key=f"hf_max_{pid}",
                )
            with hf_c3:
                st.write("")
                st.write("")
                if st.button(
                    "Запустить эксперимент",
                    use_container_width=True,
                    key=f"hf_run_{pid}",
                    disabled=not hf_sid,
                ):
                    client = LLMClient(cfg)
                    ok, msg = client.ping()
                    if not ok:
                        st.error(msg)
                    else:
                        box = st.empty()
                        with st.spinner(f"Heavy flow {hf_sid}…"):
                            res = spp.generate_section_heavy_flow(
                                pid,
                                hf_sid,
                                client=client,
                                language=sec_lang,
                                max_sentences=int(hf_max),
                                progress=lambda m: box.caption(m),
                            )
                        if res.ok:
                            meta = (pages_mod.load_page(pid) or {}).get(
                                "heavy_flow_meta", {}
                            ).get(hf_sid, {})
                            st.success(
                                f"OK · lang=`{meta.get('language', sec_lang)}` · "
                                f"{meta.get('sentence_count', '?')} предл. · "
                                f"temps={meta.get('temps')}"
                            )
                            st.rerun()
                        else:
                            st.error(res.error)

    # =====================================================================
    # STEP 4 — output
    # =====================================================================
    elif step == "4_output":
        st.markdown("#### Готовая страница")
        page = pages_mod.load_page(pid) or page
        outline = page.get("outline") or {}
        sections = outline.get("sections") or []
        drafts = page.get("sections_draft") or {}
        active = pages_mod.active_sections(page)
        done_n = sum(
            1
            for s in active
            if pages_mod.section_status(page, str(s.get("id"))) == "done"
        )
        dropped_n = len(sections) - len(active)
        st.caption(
            f"Активных с текстом: **{done_n}/{len(active)}**"
            + (f" · удалено: {dropped_n}" if dropped_n else "")
            + f" · язык `{sec_lang}`"
        )

        if st.button(
            "Собрать из секций → файл",
            type="primary",
            key=f"site_assemble_{pid}",
        ):
            res = spp.assemble_page(pid, language=sec_lang, write_guide=True)
            if res.ok:
                st.success(f"Готово → `{res.path}`")
                st.download_button(
                    "Скачать MD",
                    data=res.text.encode("utf-8"),
                    file_name=res.path.name if res.path else f"{pid}.md",
                    mime="text/markdown",
                )
                st.markdown(res.text[:12000])
            else:
                st.error(res.error)

        path = spp.guide_path_for_page(pid, language=sec_lang)
        if path.exists():
            st.markdown(f"Текущий файл: `{path}`")
            text = path.read_text(encoding="utf-8")
            st.download_button(
                "Скачать текущий MD",
                data=text.encode("utf-8"),
                file_name=path.name,
                mime="text/markdown",
                key=f"dl_cur_{pid}",
            )
            with st.expander("Превью файла", expanded=True):
                st.markdown(text[:15000])
        else:
            st.info("Файла выхода ещё нет — соберите из секций или сгенерируйте целиком на шаге 3.")

    with st.expander("Превью промптов (отладка)", expanded=False):
        dbg_page = pages_mod.load_page(pid) or {}
        dbg_ec = str(dbg_page.get("existing_copy") or "")
        st.caption(
            f"Диск сейчас: existing_copy **{len(dbg_ec)}** симв. · "
            f"начало: `{dbg_ec[:120].replace(chr(10), ' ')}…`"
            if dbg_ec.strip() and dbg_ec.strip().lower() != "none"
            else "Диск: existing_copy пуст"
        )
        phase = st.selectbox(
            "Фаза",
            ["outline", "section", "full"],
            key="site_dbg_phase",
        )
        section_arg = None
        if phase == "section":
            secs = (dbg_page.get("outline") or {}).get("sections") or []
            section_arg = secs[0] if secs else {"id": "s1", "heading": "Demo", "role": "demo"}
        try:
            msgs = spp.build_site_page_messages(
                pid, phase=phase, language=sec_lang, section=section_arg, section_mode="improve"
            )
            st.caption(f"{msgs.get('system_file')} / {msgs.get('user_file')}")
            st.code(msgs["user"][:6000], language="markdown")
        except Exception as exc:  # noqa: BLE001
            st.error(str(exc))

def main() -> None:
    init_state()
    render_llm_sidebar()
    site_pages_flow()


if __name__ == "__main__":
    main()
