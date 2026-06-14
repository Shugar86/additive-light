# additive-light — контракт для AI-агента

**Версия:** 1.0 · **Вайб:** professional — тихо делает свою работу · **Ветка:** `develop`

---

## 0. Режим работы

- **pair-programmer**, не автономный продакт. Пользователь задаёт приоритеты; агент исполняет, проверяет, сужает неопределённость.
- **Язык:** русский — для внутренней документации и отчётов; английский — для `README.md`, коммитов, кода и публичных артефактов.
- **Тон:** `professional` — сухо, точно, без магии. Метрики говорят громче слов.

## 1. Продукт

**additive-light** — детерминированный reverse-engineering движок: STL-скан → редактируемый параметрический CAD (STEP + `build123d`-скрипт) + JSON-отчёт с метриками.

Для тел вращения (валы, фаски, скругления, конусы, бочки) pipeline полностью детерминирован. Для внешнего scope (шпонки, поперечные отверстия, плоскости) pipeline явно формулирует `SkillRequest`, а не «размазывает» ошибку.

Ключевые ценности:

- измеримая точность (RMSE, IoU, axis confidence);
- воспроизводимость без LLM в критическом пути;
- параметрический выход как контракт с инженером;
- bench-driven разработка.

## 2. Вайб

- **Тон:** `professional` — тихо делает свою работу.
- **Фраза:** «Метрики говорят громче слов."
- **3 правила:**
  1. Цифры и метрики впереди слов — RMSE, IoU, axis confidence, `phi_variance`.
  2. Не обещай того, что делает swarm v2; v1 — это детерминированное ядро.
  3. Явные границы scope: out-of-scope → `SkillRequest`, никаких тихих fallback.

## 3. Стек и архитектура

| Область | Технология |
|---|---|
| Язык | Python 3.11+ |
| Mesh / geometry | `open3d==0.18.0`, `trimesh`, `shapely`, `scipy>=1.11`, `numpy`, `networkx` |
| CAD generation | `build123d`, `ocp-vscode` |
| Swarm (v2, опционально) | `langgraph`, `langchain`, `pydantic`, `pydantic-settings` |
| Config | `pyyaml`, `httpx` |
| Testing | `pytest`, `pytest-asyncio` |

Ключевые точки входа:

- `python -m backend.pipeline.deterministic_shaft <stl> -o <out>` — герой v1;
- `python -m backend.benchmark` — one-command demo;
- `python scripts/run_benchmark_matrix.py` — пакетный бенчмарк;
- `pytest tests/test_revolution_baseline.py tests/test_math_enhancements.py tests/test_out_of_scope_detector.py -v` — acceptance suite.

## 4. Инженерная дисциплина

- **KISS / минимальный diff / YAGNI.** Не пиши код «на будущее».
- **Не ломай:** если не уверен на 100% — спроси, не делай предположений.
- **Не коммить** `.env`, `*.pem`, `id_*`, токены, пароли, `node_modules/`, `__pycache__/`, `temp/` артефакты.
- **Deterministic tools decide:** никогда не используй LLM для расчёта координат, радиусов, углов или проверки геометрии. Математику делают инструменты; LLM решает, *какие* инструменты применить и *как* интерпретировать результат.
- **100% type hints** и Google-style docstrings для публичных функций/классов.
- **Обработка ошибок:** только конкретные исключения; голый `except:` запрещён.
- **Тесты:** для нетривиальной бизнес-логики предложи `pytest`-тест на успешный и один граничный/провальный кейс.
- **Безопасность generated code:** сгенерированный `build123d`-скрипт проходит AST-валидацию и исполняется в изолированном subprocess с таймаутом.

## 5. Git workflow

- **Коммить результат задачи — часть работы.**
- **Пушь**, если пользователь просил или задача требует публикации.
- **Conventional commits:** `feat(scope):`, `fix(scope):`, `docs(scope):`, `test(scope):`, `chore(scope):`, `refactor(scope):`.
- **Текущая ветка:** `develop`.
- **Remotes:**
  - `origin` — `git@github.com:Shugar86/additive-light.git`;
  - `vds` — локальный VDS-зеркал: `vds-root:/root/git/additive-light _dev.git`.

## 6. Definition of Done

1. Релевантные тесты / lint проходят.
2. В отчёте: что изменилось, что запускал, риски.
3. Документация и комментарии соответствуют вайбу `professional`.
4. Нет утечек секретов и артефактов сборки в коммите.
5. Если изменения касаются архитектуры или публичного API — обновлены `README.md`, `AGENTS.md` и связанные `docs/`.

## 7. Эскалация

Спроси пользователя, если:

- нужно добавить/изменить секреты (`.env`, API-ключи, SSH);
- два равных архитектурных пути и нет явного критерия выбора;
- prod-деплой или публикация в открытый доступ;
- изменяешь `PROJECT.md`, `COCKPIT.md`, `STATE.md` или immutable core.

## 8. Связанные документы

- [`README.md`](./README.md) — обзор, быстрый старт, архитектура
- [`LICENSE`](./LICENSE) — Apache-2.0
- [`CONTRIBUTING.md`](./CONTRIBUTING.md) — как участвовать
- [`CHANGELOG.md`](./CHANGELOG.md) — история изменений
- [`PROJECT.md`](./PROJECT.md) — неизменное ядро проекта
- [`COCKPIT.md`](./COCKPIT.md) — личность, аудитории, эмоции
- [`SPOTLIGHT.md`](./SPOTLIGHT.md) — архитектурные жемчужины и риски
- [`STATE.md`](./STATE.md) — текущий фокус и блокеры
