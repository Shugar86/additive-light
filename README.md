# Additive Light · GDI

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Tests: pytest](https://img.shields.io/badge/tests-pytest-blue.svg)](https://docs.pytest.org/)
[![CAD: OpenSCAD](https://img.shields.io/badge/CAD-OpenSCAD-orange.svg)](https://openscad.org/)
[![AI: OpenRouter](https://img.shields.io/badge/AI-OpenRouter-8A2BE2.svg)](https://openrouter.ai/)

> **Из текста и 3D-скана — в параметрическую модель, которую можно напечатать.**

**Additive Light** — это R&D-площадка для генеративного 3D-моделирования и обратного инжиниринга сканов. Она объединяет два трека:

- **ADDITIVE_LAB** — клиентское веб-приложение: текстовый запрос → AI → SolidPython2 → OpenSCAD WASM → STL прямо в браузере.
- **GDI (Generative Design Intelligence)** — Python-пайплайн: STL-скан → сенсоры → RANSAC-аппроксимация → LLM → Judge → параметрическая CAD-модель → G-code.

Проект исследовательский: код рабочий, но часть решений — MVP. Если нужна глубина, смотри [`ARCHITECTURE.md`](./ARCHITECTURE.md), [`DEPLOY.md`](./DEPLOY.md) и [`ROADMAP.md`](./ROADMAP.md).

---

## ✨ Возможности

### Веб-приложение ADDITIVE_LAB

- 🧠 Генерация кода на **SolidPython2** по текстовому промпту через **OpenRouter** (Gemini, Claude, Grok и другие coder-модели).
- 🔒 **Трёхуровневая валидация** AI-кода: скобки, `compile()` в Pyodide, полный рендер в OpenSCAD.
- 🖥️ **Рендеринг OpenSCAD WASM** в Web Worker — интерфейс не зависает на сложной геометрии.
- 🎨 **3D-просмотрщик** на Three.js с орбитальной камерой, автоцентрированием и bounding box.
- 💾 **Скачивание** `.scad` и `.stl` одним кликом.
- 🏠 **Local-first**: тяжёлые файлы отдаются локально, интернет нужен только для AI-генерации.

### Десктоп и пайплайн GDI

- 📐 **Мультиосевой слайсинг** STL через Trimesh + Shapely.
- 📊 **RANSAC-аппроксимация зон** с честной confidence-оценкой.
- 🤖 **LLM-оркестратор** для принятия решений по геометрии.
- ⚖️ **Двухфазный Judge**: синтаксис → IoU.
- 🛠️ **Параметризация и бьютификация** CAD-кода.
- 📁 **YAML-контракт v1.0** между датчиками и LLM.
- 🖨️ **Экспорт G-code** через FreeCAD Path.

---

## 🚀 Быстрый старт

### 1. Клонировать репозиторий

```bash
git clone git@github.com:Shugar86/additive-light.git
cd additive-light
```

### 2. Веб-версия (рекомендуется для знакомства)

```bash
# Python 3.11+
python server.py
```

Открой в браузере: **http://localhost:8001**

> Для Windows есть [`start-server.bat`](./start-server.bat).  
> Сервер проставляет заголовки `Cross-Origin-Opener-Policy: same-origin` и `Cross-Origin-Embedder-Policy: require-corp`, необходимые для SharedArrayBuffer / WASM. Подробнее — в [`DEPLOY.md`](./DEPLOY.md).

### 3. Десктоп-версия OpenSCAD AI

```bash
pip install -r requirements.txt
python launch_gui.py
# или
python -m gdi_app.gui.main_window
```

> Для Windows есть [`start-desktop.bat`](./start-desktop.bat).

### 4. GDI pipeline (CLI)

```bash
pip install -r requirements.txt

python -m gdi_app.cli.main process benchmark_kit/ideal/ideal_cylinder.stl \
  --output output/ \
  --axis Z \
  --step 0.1 \
  --confidence 0.7
```

Доступные команды:

```bash
python -m gdi_app.cli.main --help
python -m gdi_app.cli.main info
python -m gdi_app.cli.main validate output/ideal_cylinder_telemetry.yaml
python -m gdi_app.cli.main batch benchmark_kit/ideal/ --output output/
```

---

## 🏗️ Архитектура / стек

| Область | Технология | Назначение |
|---------|------------|------------|
| Веб-фронтенд | Vanilla JS, HTML5/CSS3, CodeMirror, Three.js | UI, редактор кода, 3D-вьювер |
| Браузерный Python | Pyodide (WebAssembly), SolidPython2 (`solid2`) | Исполнение AI-кода в браузере |
| CAD-ядро (веб) | OpenSCAD WASM | CSG-рендеринг и экспорт STL |
| AI-шлюз | OpenRouter API | Доступ к coder-моделям |
| Desktop / pipeline | Python 3.11+, Trimesh, Shapely, Pydantic, LangGraph, Typer, PyQt6 | Скан → CAD pipeline |
| Web backend | FastAPI, Celery, Redis, S3 (Phase 2) | Масштабируемое API |
| Тесты | pytest, black, mypy | Качество и консистентность |

Подробная архитектура, потоки данных и ключевые решения — в [`ARCHITECTURE.md`](./ARCHITECTURE.md).

---

## 📁 Структура проекта

```text
additive-light/
├── index.html              # Главная страница веб-приложения
├── script.js               # UI, Pyodide, AI, Three.js, OpenSCADManager
├── worker.js               # Web Worker для OpenSCAD WASM
├── style.css / style_new.css  # Стили
├── server.py               # Локальный dev-сервер с заголовками COOP/COEP
├── openscad.min.js         # JS-обёртка OpenSCAD WASM
├── requirements.txt        # Python-зависимости
│
├── OpenSCAD_AI/            # Десктопный GUI-ассистент
├── gdi_core/               # Ядро пайплайна GDI
│   ├── api.py              # Публичный API
│   ├── sensors/            # Слайсинг и выравнивание
│   ├── approximator/       # Детекция зон и confidence
│   ├── synthesis/          # Генерация кода через LLM
│   ├── judge/              # Валидация и IoU
│   ├── optimizer/          # Оптимизация CAD-кода
│   ├── sandbox/            # Песочница исполнения
│   └── models/             # YAML-контракт и Pydantic-модели
├── gdi_app/                # CLI и GUI для GDI
│   ├── cli/main.py         # Typer CLI
│   └── gui/                # PyQt6 GUI
├── web/                    # Web backend/frontend (Phase 2)
│   ├── backend/            # FastAPI + Celery
│   ├── frontend/           # Frontend-артефакты
│   └── sandbox/            # Песочница для backend
├── benchmark_kit/          # Тестовые STL: ideal / noise / corrupt / real_scans
├── tests/                  # Юнит- и интеграционные тесты
│
├── ARCHITECTURE.md         # Архитектура и data flow
├── DEPLOY.md               # Инструкция по деплою
├── ROADMAP.md              # Планы и UX-долги
├── CHANGELOG.md            # История изменений
├── CONTRIBUTING.md         # Как участвовать
├── AGENTS.md               # Контракт для агента-разработчика
└── LICENSE                 # MIT
```

---

## 📝 Примеры

### Веб: ваза из текста

1. Открой **http://localhost:8001**.
2. В поле запроса напиши: `Ваза с витой геометрией, высота 100 мм`.
3. Нажми **Сгенерировать**, затем **Скомпилировать**.
4. Когда модель появится в 3D-вьювере, скачай `.scad` или `.stl`.

> Для работы AI-генерации нужен ключ OpenRouter. В MVP он временно задаётся в `script.js`; перед продакшеном вынеси его в backend-прокси и переменные окружения.

### GDI: анализ скана из Python

```python
from gdi_core import GDIAPI

api = GDIAPI(slice_step=0.1, confidence_threshold=0.7)
manifest = api.run_pipeline(
    stl_file="benchmark_kit/real_scans/кольцо.stl",
    base_axis="Z"
)

print(manifest.status)
print(manifest.approximation_result.global_confidence)
```

### CLI: пакетная обработка

```bash
python -m gdi_app.cli.main batch benchmark_kit/ideal/ \
  --output output/ \
  --pattern "*.stl" \
  --confidence 0.7
```

---

## 🛠️ Разработка

```bash
# Установить зависимости
pip install -r requirements.txt

# Запустить тесты
pytest tests/ -v

# Форматирование
black gdi_core/ gdi_app/ web/

# Типизация
mypy gdi_core/

# Локальный веб-сервер
python server.py
```

---

## 🗺️ Дорожная карта и история

- Что дальше — в [`ROADMAP.md`](./ROADMAP.md).
- Что изменилось — в [`CHANGELOG.md`](./CHANGELOG.md).

## 🤝 Участие

См. [`CONTRIBUTING.md`](./CONTRIBUTING.md). Идеи, баг-репорты и PR приветствуются, но крупные изменения лучше сначала обсудить в issues.

## 🎭 Характер проекта

**Вайб:** `precise & honest` — инженерная честность исследовательского стенда.

1. **Честность о зрелости.** Где решение MVP — так и написано; confidence-оценки не приукрашиваются.
2. **Валидация прежде результата.** Код от AI проходит три уровня проверки и Judge — не отдаём то, что не отрендерилось.
3. **Local-first.** Тяжёлые файлы остаются на машине; сеть нужна только для AI-генерации.

---

## 📄 Лицензия

[MIT](./LICENSE) © 2026 Shugar86.
