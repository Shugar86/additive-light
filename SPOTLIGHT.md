# SPOTLIGHT — additive-light _dev

## Architecture pearls (2-3 files/decisions that make this project tick)

**1. `backend/main.py` — единая точка входа и контракт артефактов**

Функция `process_stl()` связывает всё в один вызов: валидация STL → сборка агентов через `create_agents_for_part_type()` → запуск `run_cad_recode()` из `backend/core/graph.py` → опциональная упаковка результатов в `_save_output_package()`. Паттерн **facade + factory**: CLI (`main()`) и тесты (`tests/test_shaft_pipeline.py`) вызывают один API, а внутренняя сложность LangGraph скрыта. Параметр `part_type` (`"generic"` | `"shaft"`) прокидывается в `create_coordinator_agent()` и `create_coder_agent()`, что задаёт **стратегию специализации без дублирования пайплайна**.

**2. `backend/core/graph.py` + `backend/core/state.py` — LangGraph + типизированное состояние**

`CADState` (Pydantic-модель в `state.py`) — центральный объект, через который проходят `sensor_reports`, `shaft_construction_plan`, метрики (`chamfer_distance`, `hausdorff_distance`) и ошибки (`validation_errors`, `geometric_errors`). `graph.py` строит граф агентов: динамические sensor-ноды через `_create_sensor_node_function()` и `_get_sensor_registry()`, координатор, кодер, `ASTValidator`, `SecureExecutor`, `VibeGuardAgent` с **reflection loop** (итерации до `SwarmPolicy.max_iterations`). Это классический паттерн **orchestrated multi-agent workflow** на LangGraph с patch-based обновлениями состояния.

**3. `backend/core/agent_contracts.py` + `SpecLoader` — policy-driven конфигурация**

Слой контрактов (`CADAgentSpec`, `SwarmPolicy`, `SensorRegistry`, `ExecutionPolicy`) описывает поведение роя в YAML, а `tests/test_contracts.py` фиксирует инварианты: дефолты `SwarmPolicy` (reflection, parallel sensors, tolerances), безопасность `ExecutionPolicy` (`network_access=False`), кэширование спеков в `SpecLoader`. Паттерн **declarative agent specs + Pydantic validation** отделяет политику от кода и позволяет менять агентов без перекомпиляции графа.

---

## Hidden risks (1-2 places that could bite)

**1. Хрупкая связка executor → артефакты STEP/STL (`backend/main.py`)**

В `_save_output_package()` пути к STEP-файлам ищутся эвристически: `mesh_path.parent / "shaft.step"` и `output_{id(state.final_output)}.step`. Это **tight coupling** к внутренней реализации `SecureExecutor` [uncertain — точное имя выходных файлов зависит от executor]. При смене naming convention preview STL и STEP могут silently не попасть в output package, хотя `test_artifact_count()` в `tests/test_shaft_pipeline.py` ожидает до 5 артефактов, но проходит уже при ≥3.

**2. Разрыв между DoD тестов и реальной надёжностью пайплайна**

`tests/test_shaft_pipeline.py` декларирует DoD «8/10 fixtures», но `test_minimum_pass_rate()` проверяет `passed >= 7` из 9 (исключая `failure_case`). E2E-тесты вызывают полный `process_stl()` с `max_iterations=1` — при отсутствии LLM-клиента поведение координатора/кодера [uncertain]. `TestSelfHealing.test_error_correction_retry()` — **концептуальный** тест reflection JSON, а не реальный retry-loop через `run_cad_recode()`. Риск: зелёные тесты при частично работающем self-healing.

**3. Зависимости без жёстких пинов (`requirements.txt`)**

Только `open3d==0.18.0` и `scipy>=1.11` зафиксированы; `trimesh`, `langchain`, `langgraph`, `build123d` — без версий. При обновлении LangGraph/LangChain API в `graph.py` (условный импорт `HAS_LANGGRAPH`) возможны **недетерминированные поломки** CI и E2E.

---

## Reuse gold (what could be copied to another project)

| Паттерн | Где | Зачем копировать |
|--------|-----|------------------|
| **Pydantic state + patch updates** | `CADState`, `SliceReport`, `ShaftConstructionPlan` | Типобезопасный state machine для любого multi-step pipeline |
| **YAML agent specs + cache** | `SpecLoader`, `get_prompt_compiler()` с fallback | Конфигурируемые промпты/роли без redeploy |
| **AST sandbox перед exec** | `ASTValidator` + `SecureExecutor(execution_policy=...)` | Безопасный codegen: whitelist imports, subprocess sandbox |
| **Детерминированные domain sensors** | `backend/sensors/shaft_axis.py`, `shaft_profile.py`, `shaft_features.py` | Геометрический RE без LLM: axis detection → profile → features |
| **Parameter contract validation** | `research/spiroid_reconstruction/extract_wing_tip_parameters.py` (`validate_parameters`) + `build_parametric_tip()` | JSON-контракт → валидация → parametric mesh; переносимо на любую деталь |
| **Acceptance test matrix** | `tests/test_shaft_pipeline.py` (10 fixtures, artifact checklist, metrics) | Шаблон DoD для reverse-engineering MVP |

Стек из `requirements.txt` явно заточен под **mesh → parametric CAD**: `open3d`/`trimesh`/`shapely` (геометрия), `build123d` (B-Rep codegen), `langgraph` (оркестрация), `pydantic-settings` (конфиг).

---

## Key commits vibe (if git history visible)

История (`git log --oneline -20`) показывает **фазовую эволюцию**, а не хаотичные коммиты:

1. **Архитектурный pivot** — `974693b5 refactor: migrate to CAD swarm architecture with policy-driven contracts`
2. **Вертикальный MVP** — `a2533f57 feat: Shaft Reverse Engineering MVP` → `c510f964 fix: Sprint bug fixes`
3. **Deterministic track параллельно LLM-swarm** — `5ec4f5ca feat(rev-eng): deterministic revolution bodies pipeline — Phase 0-5` → benchmark kit
4. **Research spikes** — spiroid winglet, CAPP docs, alternative scripts в `research/`
5. **Productization burst** — `4c21d6ab feat(sber500): Sprint 0-4 complete` + unified docs (`828ee1e2`)

Стиль: **conventional commits** (`feat`, `fix`, `docs`, `test`, `chore`), scope в скобках (`rev-eng`, `benchmark`, `sber500`). Ритм — спринтовый: большие feature-коммиты + отдельные fix/docs, чередование **инженерного кода** и **исследовательских артефактов**. [uncertain] remote `vds/develop` — локальная ветка `develop` опережает на 1 коммит.

---

## Questions for the author

1. **Какой путь «production default»**: LLM-driven swarm (`run_cad_recode` + coordinator/coder agents) или детерминированные ветки (`part_type="shaft"`, revolution bodies в benchmark_kit)? Связь между `create_default_agents()` (с `SkillLibrary`, но без `part_type`) и `create_agents_for_part_type()` неочевидна — `SkillLibrary` создаётся, но не передаётся в фабрики [uncertain].

2. **Интеграция `research/spiroid_reconstruction/` с `backend/`**: wing tip contract (`validate_parameters`, `build_parametric_tip`) живёт отдельно от `CADState`/`ShaftConstructionPlan`. Планируется ли унификация через общий `ParameterContract` слой или это намеренно изолированный spike?

3. **Границы self-healing**: reflection loop в `graph.py` использует `VibeGuardAgent.generate_json_reflection()` — но где именно geometric_errors из reflection **мутируют** `ShaftConstructionPlan` перед следующей итерацией? Тесты проверяют JSON-формат, не автокоррекцию радиуса/зоны.
