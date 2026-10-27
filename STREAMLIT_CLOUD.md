# Streamlit Community Cloud

## Сейчас в `requirements.txt` НЕТ Playwright

На **Python 3.14** Cloud ломает установку `greenlet` (зависимость Playwright).  
Поэтому дефолтный деплой — без Playwright: LLM-флоу работает, ZeroGPT — ручные highlights.

## Вариант A — быстрый деплой (без ZeroGPT-браузера)

1. Reboot / Redeploy текущего app (после пуша без playwright).
2. Secrets:

```toml
DEEPSEEK_API_KEY = "..."
HYDRA_API_KEY = "..."
```

## Вариант B — с Playwright / ZeroGPT

1. **Удали** app.
2. **New app** → `pokerpok/ContentStudio`, branch `main`, `app.py`.
3. **Advanced settings → Python version = 3.12** (не 3.14!).
4. Secrets + Deploy.
5. В репо временно сделай `requirements.txt` = содержимое `requirements-playwright.txt`  
   (или скажи агенту — вернём playwright в дефолт под 3.12).
6. В UI: **«Установить / починить Playwright Chromium»**.

Версию Python после деплоя **нельзя сменить** — только удалить и задеплоить заново.
