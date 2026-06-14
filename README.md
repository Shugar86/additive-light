# Additive Light · GDI

**Из текста и 3D-скана — в параметрическую модель, которую можно напечатать.**

Additive Light — это экспериментальная площадка для генеративного 3D-моделирования. Она объединяет два направления:

- **ADDITIVE_LAB** — клиентское веб-приложение: пишешь текстовый запрос, AI генерирует Python-код на SolidPython2, OpenSCAD WASM рендерит STL прямо в браузере.
- **GDI (Generative Design Intelligence)** — Python-пайплайн: берёт STL-скан, анализирует геометрию датчиками, аппроксимирует зоны, собирает параметрическую CAD-модель и выводит G-code.

> Это R&D-репозиторий. Код рабочий, но часть решений — исследовательские. Если что-то непонятно, смотри `ARCHITECTURE.md`, `DEPLOY.md` и `ROADMAP.md`.

## Что умеет

### Веб-часть (ADDITIVE_LAB)

- 🧠 Генерация SolidPython2-кода по текстовому промпту через OpenRouter (Gemini, Claude, Grok и другие coder-модели).
- 🔒 Трёхуровневая валидация AI-кода: скобки, `compile()` в Pyodide, полный рендер в OpenSCAD.
- 🖥️ Рендеринг OpenSCAD прямо в браузере через WASM + Web Worker — интерфейс не зависает.
- 🎨 3D-просмотрщик на Three.js с орбитальной камерой, автоцентрированием и bounding box.
- 💾 Скачивание `.scad` и `.stl` одним кликом.
- 🏠 Local-first: тяжёлые файлы (`openscad.min.js`, `worker.js`, стили) отдаются локально.

### Десктоп / pipeline (GDI)

- 📐 Мультиосевой слайсинг STL через Trimesh + Shapely.
- 📊 RANSAC-аппроксимация зон с confidence-оценкой.
- 🤖 LLM-оркестратор для принятия решений по геометрии.
- ⚖️ Двухфазный Judge: синтаксис → IoU.
- 🛠️ Параметризация и бьютификация CAD-кода.
- 📁 YAML-контракт v1.0 между датчиками и LLM.
- 🖨️ Экспорт G-code через FreeCAD Path.

## Быстрый старт

### Веб-версия (рекомендуется)

```bash
# 1. Перейти в папку проекта
cd /home/shugar/dev/additive-light

# 2. Запустить локальный сервер (Python 3.10+)
python server.py

# 3. Открыть в браузере
open http://localhost:8001
```

> Для Windows есть `start-server.bat`.
> Для корректной работы WASM сервер проставляет заголовки `COOP: same-origin` и `COEP: require-corp`. Подробнее — в `DEPLOY.md`.

### Десктоп-версия OpenSCAD AI

```bash
# Установить зависимости
pip install -r requirements.txt

# Запустить GUI
python launch_gui.py
# или
python -m gdi_app.gui.main_window
```

> Для Windows есть `start-desktop.bat`.

### GDI pipeline (CLI)

```bash
pip install -r requirements.txt

cd gdi_app/cli
python -m main process /path/to/file.stl --output output/
```

## Архитектура / стек

| Область | Технологии |
|---------|------------|
| Веб-фронтенд | Vanilla JS, HTML5/CSS3, CodeMirror, Three.js |
| Браузерный Python | Pyodide (WebAssembly), SolidPython2 (`solid2`) |
| CAD-ядро | OpenSCAD WASM |
| AI | OpenRouter API |
| Desktop / pipeline | Python 3.11+, Trimesh, Shapely, Pydantic, LangGraph, Typer, PyQt6 |
| Web backend | FastAPI, Celery, Redis, S3 (Phase 2) |
| Тесты | pytest |

## Структура проекта

```text
additive-light/
├── index.html              # Главная страница веб-приложения
├── script.js               # Основная логика: UI, Pyodide, AI, Three.js
├── worker.js               # Web Worker для OpenSCAD WASM
├── style.css / style_new.css  # Стили
├── server.py               # Локальный dev-сервер с правильными заголовками
├── openscad.min.js         # JS-обёртка OpenSCAD WASM
├── requirements.txt        # Python-зависимости
│
├── OpenSCAD_AI/            # Десктопный GUI-ассистент (Python)
├── gdi_core/               # Ядро пайплайна GDI
├── gdi_app/                # CLI и GUI для GDI
├── web/                    # Web backend/frontend (Phase 2)
├── benchmark_kit/          # Тестовые STL: ideal / noise / corrupt / real_scans
├── tests/                  # Юнит- и интеграционные тесты
│
├── ARCHITECTURE.md         # Подробная архитектура
├── DEPLOY.md               # Как выложить в прод
├── ROADMAP.md              # Планы и UX-долги
├── CHANGELOG.md            # История изменений
├── CONTRIBUTING.md         # Как участвовать
└── LICENSE                 # MIT
```

## Примеры

### Веб: ваза из текста

1. Открой `http://localhost:8001`.
2. В поле запроса напиши: `Ваза с витой геометрией, высота 100 мм`.
3. Нажми **Сгенерировать**, затем **Скомпилировать**.
4. Когда модель появится в 3D-вьювере, скачай `.scad` или `.stl`.

### GDI: анализ скана

```python
from gdi_core import GDIAPI

api = GDIAPI(slice_step=0.1, confidence_threshold=0.7)
manifest = api.run_pipeline(stl_file="model.stl", base_axis="Z")

print(manifest.status)
print(manifest.approximation_result.global_confidence)
```

## Разработка

```bash
# Тесты
pytest tests/ -v

# Форматирование
black gdi_core/ gdi_app/ web/

# Типизация
mypy gdi_core/
```

## Лицензия

[MIT](./LICENSE) © Shugar86.

## Участие

См. [CONTRIBUTING.md](./CONTRIBUTING.md). Проект исследовательский — идеи и PR приветствуются, но сначала лучше обсудить в issues.
