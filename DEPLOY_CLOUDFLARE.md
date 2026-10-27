# Деплой Content Studio на Cloudflare

## Важно

| Что вы дали | Что это |
|-------------|---------|
| API Token | Доступ к аккаунту Cloudflare |
| `…r2.cloudflarestorage.com` | **R2** = объектное хранилище (файлы), **не** хостинг приложения |

Классический **Worker** (V8) **не запускает** Streamlit/Playwright. Нужны **Cloudflare Containers** (Docker-образ + Worker-прокси).

### Блокеры на момент подготовки

1. **Workers Paid** — Containers требуют платный план Workers.  
   Сейчас API отвечает: *Unauthorized: You do not have access to Cloudflare Containers*.
2. **Docker Desktop** — локально не установлен; `wrangler deploy` с `image = "./Dockerfile"` без Docker не соберёт образ.

## После апгрейда плана + установки Docker

```bat
cd D:\JackPoker\ContentStudio
set CLOUDFLARE_API_TOKEN=ваш_токен

cd worker
npm install
cd ..

npx wrangler secret put DEEPSEEK_API_KEY
npx wrangler secret put HYDRA_API_KEY

npx wrangler deploy
```

URL будет вида: `https://content-studio.<subdomain>.workers.dev`

Первый деплой может занять несколько минут (провижининг контейнера).

### Ограничения в облаке

- Данные `data/pages` в контейнере **эфемерны** (после sleep/redeploy пропадут), пока не подключим R2/volume.
- ZeroGPT (Playwright) тяжёлый; на Containers может упираться в лимиты образа/памяти — проверять после деплоя.
- `sleepAfter = 30m` — простой контейнер гасится; следующий заход холодный старт.

## R2 (позже)

Endpoint `https://b597e3b60eba0e17d1cbeb47ea07e77b.r2.cloudflarestorage.com` можно использовать для персистентных `pages` / `output` — отдельная задача после того, как Containers заработают.

## Безопасность

Токен из чата лучше **отозвать и выпустить новый** в Dashboard → API Tokens. Не коммитьте токен в git.
