# Content Studio

Универсальный инструмент генерации и редактуры текстов страниц сайта.

Отдельный проект: **без** генерации карт/столов, глоссария и прочих покерных модулей.

## Возможности

- Fetch URL → clean copy
- Outline: parse / generate / import / enrich
- Разрез existing copy на секции + seed драфтов
- Генерация: `section` / `ensemble` (Hydra) / `heavy_flow`
- Editorial improve, Anti-AI pass
- ZeroGPT check + точечная JSON-редакция (лимит **15 000** символов)
- Assemble финального Markdown

## Быстрый старт (локально)

```bat
cd D:\JackPoker\ContentStudio
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
streamlit run app.py
```

Или `run.bat`.

## Ключи LLM

В сайдбаре укажите провайдер / Base URL / Model / API key и нажмите **Сохранить LLM-настройки**.

Ключи пишутся в `.env` (в git не попадает) и `data/settings.json` (без секретов).

Для ансамбля абзацев нужен отдельный ключ Hydra (`HYDRA_API_KEY`).

## Brief бренда

Из коробки: `data/briefs/default.json`. Отредактируйте под свой сайт или создайте новый brief и смените `project_brief` в `data/strategies/site_page.json`.

## ZeroGPT

- Проверка идёт через Playwright на zerogpt.com (headless по умолчанию).
- На cloud worker всегда используйте headless.
- Текст длиннее 15 000 символов отклоняется — работайте посекционно.

## Тесты

```bat
python -m pytest tests -q
```

## Streamlit Community Cloud

1. Репозиторий на GitHub (этот проект).
2. [share.streamlit.io](https://share.streamlit.io) → **New app**
   - Repository: ваш fork/clone
   - Branch: `master` (или `main`)
   - Main file: `app.py`
3. **Advanced settings → Secrets** (TOML):

```toml
DEEPSEEK_API_KEY = "sk-..."
HYDRA_API_KEY = "sk-hydra-ai-..."
```

4. Deploy.

ZeroGPT: при первом check приложение само ставит Chromium (`playwright install chromium`).
Если билд Cloud снова упадёт на `packages.txt` — напишите, откатим apt-зависимости.

См. также `DEPLOY_CLOUDFLARE.md` (Containers / Paid plan).
