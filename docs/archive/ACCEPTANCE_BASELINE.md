# GDI Acceptance Baseline
## Документ базовой линии приемки

**Дата создания:** 2026-03-03  
**Версия плана:** gdi-desktop-web-plan-v2_89310dd9  
**Статус:** IN_PROGRESS

---

## 1. Окружение и версии

### Python
- **Версия:** 3.13.6

### Ключевые пакеты
| Пакет | Версия | Назначение |
|-------|--------|------------|
| trimesh | 4.11.2 | Mesh processing |
| shapely | 2.1.2 | 2D geometry operations |
| scipy | 1.16.1 | RANSAC, optimization |
| pydantic | 2.11.7 | YAML contract validation |
| langgraph | 1.0.10 | LLM orchestration |
| langchain | 1.2.10 | LLM framework |
| fastapi | 0.116.1 | Web API |
| celery | 5.6.2 | Task queue |
| redis | 7.2.1 | Message broker |
| typer | 0.16.0 | CLI framework |

---

## 2. Тестовые датасеты

### Benchmark Kit структура
```
benchmark_kit/
├── ideal/                    # Идеальные модели (8 файлов)
│   ├── ideal_cylinder.stl
│   ├── ideal_stepped_shaft.stl
│   ├── ideal_flange.stl
│   ├── ideal_bracket_2.5d.stl
│   ├── ideal_nema17_mount.stl
│   ├── ideal_helical_gear.stl
│   ├── ideal_heat_sink.stl
│   └── ideal_lattice_block.stl
├── noise/                    # Синтетический шум (ожидается)
├── corrupt/                  # Частично поврежденные (ожидается)
└── real_scans/               # Реальные сканы (1 файл)
    └── Кнопка_2.stl
```

### Исходные сканы (mesh/)
- mesh_Scan 1.stl
- mesh_развертка.stl
- УГОЛОК.stl
- Кнопка_2.stl
- тойота.stl

---

## 3. Конфигурационные пороги

### Из expected_results.yaml

| Модель | Min IoU | Confidence Floor | Тип геометрии |
|--------|---------|------------------|---------------|
| ideal_cylinder | 0.99 | 0.95 | Constant_Profile (Circle) |
| ideal_stepped_shaft | 0.99 | 0.92 | 2 зоны Constant_Profile |
| ideal_flange | 0.98 | 0.90 | Constant_Profile_with_Holes |
| ideal_bracket_2.5d | 0.97 | 0.88 | Constant_Profile_with_Holes (Rectangle) |
| ideal_nema17_mount | 0.96 | 0.85 | Constant_Profile_with_Holes |
| noise_* | 0.96 | 0.80 | С допуском ±0.5мм |
| corrupt_* | 0.80 | 0.40 | Partial recognition |

### Пороги системы
- **Confidence Threshold:** 0.7 (fallback to manual review)
- **IoU Threshold:** 0.98 (judge acceptance)
- **Max Retries:** 3
- **Slice Step:** 0.1 mm

---

## 4. Источники истины

### Планы
1. [gdi-desktop-web-plan-v2_89310dd9.plan.md](c:/Users/Преподаватель/.cursor/plans/gdi-desktop-web-plan-v2_89310dd9.plan.md) - Основной план
2. [gdi-acceptance-check-plan_817767dc.plan.md](c:/Users/Преподаватель/.cursor/plans/gdi-acceptance-check-plan_817767dc.plan.md) - План приемки

### Артефакты кода
1. [gdi_core/models/yaml_contract.py](e:/additive-light _dev/gdi_core/models/yaml_contract.py) - YAML v1.0 contract
2. [gdi_core/api.py](e:/additive-light _dev/gdi_core/api.py) - Core API
3. [gdi_app/cli/main.py](e:/additive-light _dev/gdi_app/cli/main.py) - CLI interface
4. [gdi_app/gui/main_window.py](e:/additive-light _dev/gdi_app/gui/main_window.py) - GUI interface
5. [web/backend/app/main.py](e:/additive-light _dev/web/backend/app/main.py) - Web API

### Тестовые данные
1. [benchmark_kit/expected_results.yaml](e:/additive-light _dev/benchmark_kit/expected_results.yaml) - Ожидаемые результаты

---

## 5. Архитектура системы (проверка наличия модулей)

### Core модули (gdi_core/)
- [x] models/ - YAML contract, pydantic models
- [x] sensors/ - Multi-axis slicer
- [x] approximator/ - Zone detection with confidence
- [x] judge/ - 2-phase validation
- [x] synthesis/ - LLM orchestration (LangGraph)
- [x] optimizer/ - Code beautification
- [x] cam/ - G-code export
- [x] utils/ - Manifest & logging
- [x] api.py - Clean API boundary

### Desktop (gdi_app/)
- [x] cli/ - Typer CLI
- [x] gui/ - PyQt6 GUI

### Web (web/)
- [x] backend/app/ - FastAPI
- [x] backend/app/worker/ - Celery tasks
- [x] backend/app/core/ - Config & models
- [x] frontend/src/ - React components
- [x] sandbox/ - Docker sandbox

---

## 6. Контрольные точки приемки

### Quality Gates (обязательные)
1. IoU на целевых кейсах >= порогов из expected_results.yaml
2. Pipeline не падает на шумных/поврежденных моделях
3. 100% запусков имеют валидный run manifest
4. YAML v1.0 строго валидируется
5. Desktop и Web используют общий core-контур

### План проверки
1. Предприемка артефактов (этот документ) - **COMPLETE**
2. Проверка YAML-контракта
3. Функциональная проверка Desktop
4. Качество распознавания (IoU/confidence)
5. Проверка Judge и retry-логики
6. Аудит Run Manifest
7. Приемка Web фазы
8. Финальный sign-off

---

## 7. Чеклист готовности к приемке

- [x] Baseline собран
- [ ] Проверка контрактов
- [ ] Desktop функционал
- [ ] Quality gates
- [ ] Judge аудит
- [ ] Manifest аудит
- [ ] Web приемка
- [ ] Финальный протокол

---

**Подготовил:** GDI Acceptance System  
**Статус:** Готов к началу приемочных испытаний
