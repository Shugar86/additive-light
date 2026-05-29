# PROJECT — additive-light _dev

Anchor (immutable core). Changing meaning = new project.

## Mission (1-2 sentences, north star)

Превращать 3D-сканы (STL) в редактируемые параметрические CAD-модели с измеримой точностью — детерминированной математикой, без LLM в критическом пути. Когда геометрия выходит за рамки текущего инструментария, система явно формулирует запрос на новый навык, а не «размазывает» ошибку.

## Immutable core (3-6 principles that cannot break)

1. **Детерминированные инструменты решают.** RMSE, IoU, axis confidence, `phi_variance`, fit residual — только математика, без LLM на пути STL → STEP.
2. **Гипотезы явные.** Невозможная реконструкция → структурированный `SkillRequest` с именем недостающего инструмента и причиной. Без тихих fallback'ов.
3. **Редактируемый параметрический выход.** Каждый прогон даёт build123d-скрипт (контракт) и STEP B-Rep (артефакт).
4. **Bench-driven R&D.** Спринты и регрессии опираются на `docs/baseline_results.json` и матрицу бенчмарков, а не на интуицию.
5. **YAGNI.** Фичи только под измеримую deeptech/demo-ценность; Text-to-CAD и произвольные UI заморожены.
6. **Слепой инженер с растущим набором инструментов.** Сначала измерить и понять, потом эскалировать в swarm/skill library.

## Key technical decisions (table: Decision | Why)

| Decision | Why |
|---|---|
| Детерминированный pipeline для тел вращения (v1) | Воспроизводимость, измеримая точность, доверие инженера; LLM-CAD даёт mesh без параметров |
| Open3D + Trimesh + Shapely + SciPy | Проверенный стек для mesh alignment, slicing, 2D-анализа и fitting без GPU |
| build123d (subprocess) → STEP B-Rep | Редактируемый parametric Python + OCCT solid, открывается в любом CAD |
| Spike Generator (`phi_variance` → `SkillRequest`) | Явная граница scope: шпоночные пазы, поперечные отверстия, плоскости не усредняются |
| LangGraph swarm — слой v2, не поверх v1 | Оркестрация активируется только когда детерминированного ядра недостаточно |
| Skill Library (Voyager-style bootstrapper) | Рост инструментария по запросу, а не монолитный парсер «на все случаи» |
| `manufacturing_intent` placeholder в report.json | Задел под CAPP-lite (v3) без блокировки v1 |
| Text-to-CAD заморожен | См. `docs/DECISION_MEMO_TEXT2CAD.md` — нет гарантий точности для инженерного RE |

## Stack (languages, frameworks, key libs)

- **Язык:** Python 3.11+
- **Mesh / geometry:** `open3d==0.18.0`, `trimesh`, `shapely`, `scipy>=1.11`, `numpy`, `networkx`
- **CAD generation:** `build123d`, `ocp-vscode`
- **Swarm (v2, опционально):** `langgraph`, `langchain`, `pydantic`, `pydantic-settings`
- **Config / infra:** `pyyaml`, `httpx`
- **Testing:** `pytest`, `pytest-asyncio`
- **CI / hooks:** локальный pre-push hook (`.github` [uncertain — детали в репо])

## Key files / entry points

| Path | Назначение |
|---|---|
| `backend/pipeline/deterministic_shaft.py` | Главная точка входа: STL → STEP + parametric script + report.json |
| `backend/sensors/` | Детерминированные сенсоры: align, axis, slice, profile, fitting |
| `backend/agents/coder_agent.py` | Генерация build123d-кода (arc discretisation для FILLET/CHAMFER) |
| `backend/core/state.py` | Pydantic-модели: `ShaftConstructionPlan`, `SkillRequest`, `OutOfScopeRegion` |
| `backend/skills/controlled_bootstrapper.py` | Bootstrapper навыков (v2, не активирован по умолчанию) |
| `backend/main.py` | Точка входа LangGraph swarm [uncertain — используется при активации v2] |
| `scripts/run_benchmark_matrix.py` | Пакетный прогон бенчмарков |
| `python -m backend.benchmark` | One-command demo (Sprint 4) |
| `benchmark_kit/` | 36 STL-фикстур: `ideal/`, `noise/`, `corrupt/`, `real_scans/` |
| `config/agents/*.yaml`, `config/swarm_policy.yaml` | Спеки агентов и политика swarm |
| `requirements.txt` | Зависимости проекта |

## Documentation (existing docs links)

| Документ | Ссылка |
|---|---|
| README (обзор, TL;DR, baseline) | [README.md](README.md) |
| Архитектура (3 слоя v1/v2/v3) | [docs/architecture.md](docs/architecture.md) |
| Roadmap | [docs/ROADMAP.md](docs/ROADMAP.md) |
| План тел вращения | [docs/BODIES_OF_REVOLUTION_PLAN.md](docs/BODIES_OF_REVOLUTION_PLAN.md) |
| R&D стратегия RE | [docs/RND_REVERSE_STRATEGY.md](docs/RND_REVERSE_STRATEGY.md) |
| Skill Library | [docs/skills_library.md](docs/skills_library.md) |
| Инвентарь бенча | [docs/bench_inventory.md](docs/bench_inventory.md) |
| Baseline метрики | [docs/baseline_results.json](docs/baseline_results.json) |
| Sber500 deck | [docs/sber500_deck.md](docs/sber500_deck.md) |
| CAPP-lite направление | [docs/EXPERIMENTAL_CAPP_DIRECTION.md](docs/EXPERIMENTAL_CAPP_DIRECTION.md) |
| Memo: Text-to-CAD frozen | [docs/DECISION_MEMO_TEXT2CAD.md](docs/DECISION_MEMO_TEXT2CAD.md) |
| VibeCraft personas | [docs/Vibe_contract/VibeCraft_personas.md](docs/Vibe_contract/VibeCraft_personas.md) |
| Backend README (swarm) | [backend/README.md](backend/README.md) |
| R&D spiroid winglet | [research/spiroid_reconstruction/](research/spiroid_reconstruction/) |

## Health (how to check it works)

```bash
# 1. Установка
pip install -r requirements.txt

# 2. Быстрый acceptance-suite (Sprint 0–3 baseline)
pytest tests/test_revolution_baseline.py \
       tests/test_math_enhancements.py \
       tests/test_out_of_scope_detector.py -v
# Ожидание: 30 passed

# 3. Один прогон RE
python -m backend.pipeline.deterministic_shaft \
       benchmark_kit/ideal/ideal_short_disc_shaft.stl \
       -o temp/demo_short_disc
# Ожидание: shaft.step, *_parametric.py, *_report.json

# 4. Полная матрица бенча
python scripts/run_benchmark_matrix.py
# Результаты: temp/bench_matrix/<timestamp>/{results.json, summary.md}
```

**Hero-метрики (v1):** `ideal_short_disc_shaft` RMSE 0.003 mm; реальный скан `Кнопка_2.stl` RMSE 0.042 mm (источник: `docs/baseline_results.json`).
