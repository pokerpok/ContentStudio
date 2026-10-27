# Streamlit Community Cloud

## Важно: Python 3.12 (не 3.14)

Сейчас Cloud по умолчанию может поставить **Python 3.14**.  
Playwright → `greenlet` на 3.14 **не собирается** (ошибка `_PyInterpreterFrame` / wheel).

### Что сделать

1. В share.streamlit.io **удали** текущее приложение.
2. **New app** → repo `pokerpok/ContentStudio`, branch `main`, file `app.py`.
3. Открой **Advanced settings**.
4. **Python version → 3.12** (обязательно).
5. Secrets:

```toml
DEEPSEEK_API_KEY = "..."
HYDRA_API_KEY = "..."
```

6. **Deploy**.

Версию Python после деплоя **нельзя сменить** — только удалить и задеплоить заново  
(см. [docs](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/upgrade-python)).

## После успешного билда

В приложении: **«Установить / починить Playwright Chromium»** один раз, затем ZeroGPT.
