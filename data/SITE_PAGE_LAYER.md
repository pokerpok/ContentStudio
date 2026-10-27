# Content Studio — слой генерации страниц

## Флоу

1. **Вводные** — существующая страница (URL / текст) или «новая»; свободные вводные; brief бренда.
2. **Структура** — зафиксировать MD с заголовками или сгенерировать Meta + Outline.
3. **Контент** — посекционно: generate / ensemble / heavy_flow → improve → Anti-AI → ZeroGPT.
4. **Готовая страница** — сборка → `output/guides/site_page/{lang}_….md`.

## Файлы

| Путь | Назначение |
|------|------------|
| `data/prompts/site_page_*.md` | фазы пайплайна |
| `data/pages/*.json` | спека страницы + драфты |
| `data/briefs/*.json` | универсальный project brief (`default` из коробки) |
| `data/strategies/site_page.json` | стратегия + phase_prompts |
| `src/content/site_page_pipeline.py` | оркестрация |
| `src/content/zerogpt.py` | браузерная проверка (лимит 15 000 симв.) |
| `src/content/fetch_page.py` | URL → текст |

## Brief

Подставьте свой бренд в `data/briefs/default.json` или создайте новый id и укажите его в `data/strategies/site_page.json` → `project_brief`.
