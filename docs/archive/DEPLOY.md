# Инструкция по развертыванию (Deployment)

Приложение является статическим (**Static Web App**), что делает его развертывание простым и дешёвым. В продакшене не нужен сервер приложений (Node.js, Python, PHP) — достаточно веб‑сервера для раздачи HTML/CSS/JS/WASM.

## Требования к хостингу

1. **Поддержка статики:** HTML, CSS, JS, WASM.
2. **HTTPS:** Рекомендуется (для безопасного контекста и корректной работы современных браузеров).
3. **Заголовки (Headers):** Критичны для работы WebAssembly (OpenSCAD WASM, Pyodide).

## Важные HTTP‑заголовки

Для корректной работы `openscad.wasm` и (при необходимости) `pyodide` в современных браузерах сервер **должен** отдавать следующие заголовки для всех файлов (минимум для HTML и JS/WASM):

```http
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Embedder-Policy: require-corp
```

А также правильный MIME‑тип для `.wasm`‑файлов:

```http
Content-Type: application/wasm
```

Эти же заголовки уже проставляет локальный `server.py`, так что локальная разработка максимально приближена к продакшену.

## Варианты развертывания

### 1. GitHub Pages (простой, с ограничениями)

1. Создайте репозиторий на GitHub.
2. Загрузите все файлы проекта (кроме `__pycache__`, временных файлов и т.п.).
3. В настройках репозитория (Settings → Pages) включите GitHub Pages из ветки `main` или `docs`.
4. **Нюанс:** GitHub Pages не даёт просто настраивать COOP/COEP‑заголовки.
   - **Вариант:** использовать [`coi-serviceworker`](https://github.com/gzuidhof/coi-serviceworker) — Service Worker, который эмулирует нужные заголовки.
   - **Или:** перенести проект на Cloudflare Pages / Vercel / Netlify (рекомендуется).

### 2. Vercel / Netlify (рекомендуемые статики)

Эти платформы позволяют бесплатно хостить статику и настраивать заголовки через конфигурационный файл.

**Пример для Vercel (`vercel.json`):**

```json
{
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        {
          "key": "Cross-Origin-Opener-Policy",
          "value": "same-origin"
        },
        {
          "key": "Cross-Origin-Embedder-Policy",
          "value": "require-corp"
        }
      ]
    }
  ]
}
```

**Пример для Netlify (`netlify.toml`):**

```toml
[[headers]]
  for = "/*"
  [headers.values]
    Cross-Origin-Opener-Policy = "same-origin"
    Cross-Origin-Embedder-Policy = "require-corp"
```

### 3. Свой сервер (Nginx)

Если вы разворачиваете на VPS или bare‑metal, конфигурация Nginx может выглядеть так:

```nginx
server {
    listen 80;
    server_name your-domain.com;
    root /var/www/additive-lab;
    index index.html;

    location / {
        add_header Cross-Origin-Opener-Policy same-origin;
        add_header Cross-Origin-Embedder-Policy require-corp;
        try_files $uri $uri/ =404;
    }

    # Правильный MIME тип для WASM
    types {
        application/wasm wasm;
    }
}
```

Не забудьте настроить HTTPS (например, через Let’s Encrypt) и перенаправление с HTTP на HTTPS.

## Локальный запуск (Development)

Для локальной разработки используйте входящий в комплект скрипт `server.py`, который уже настроен правильно (MIME‑типы и заголовки):

```bash
python server.py
```

По умолчанию сервер поднимается на порту `8001`:  
[http://localhost:8001](http://localhost:8001)

## Переменные окружения и секреты (AI‑ключи)

В проекте используется API‑ключ для OpenRouter (`OPENROUTER_API_KEY` в `script.js`).  
⚠️ **Важно:** в текущей версии ключ зашит в клиентский JS‑код. Это приемлемо для локальной разработки и ограниченных демо, но небезопасно для публичного продакшена — любой пользователь может извлечь ключ из бандла.

### Рекомендуемый продакшен‑паттерн

1. **Выносить ключ на backend‑proxy:**
   - Vercel Functions / Netlify Functions;
   - Cloudflare Workers / Pages Functions;
   - простой backend на Python/Node.js.
2. **Хранить ключ только в переменных окружения backend‑сервиса**, а фронтенд слать запросы на собственный `/api/generate`, который уже ходит в OpenRouter.
3. Ограничить ключ в панели OpenRouter (лимиты по домену/квоте), даже если используется proxy.

### Ограничения без backend‑proxy

Если вы всё же разворачиваете чистую статику без backend‑части:
- используйте отдельный тестовый ключ с жёсткими лимитами;
- учитывайте, что ключ может утечь и использоваться третьими лицами;
- периодически ротуйте ключи и следите за статистикой использования в панели OpenRouter.

## Связанный десктоп‑проект OpenSCAD_AI

Отдельно существует десктопный ассистент `OpenSCAD_AI` (Python + customtkinter), который разворачивается как обычное Python‑приложение (см. его `README`/`requirements.txt`). Он не участвует в деплое веб‑части, но концептуально использует те же AI‑ключи и OpenSCAD, поэтому:
- продакшен‑ключи лучше разделять на "web" и "desktop";
- для корпоративных установок можно держать оба приложения за одним внутренним прокси к OpenRouter.

