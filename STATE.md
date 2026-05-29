# STATE — additive-light _dev

*Updated: 2026-05-30*

## Status (active/paused/experimental/archived + why)

**Active / experimental.** Детерминированное ядро v1 (Sprint 0–4, Sber500) завершено и стабильно; проект в фазе перехода к v2 (активация swarm + fulfilment `SkillRequest`). Параллельно ведётся R&D (spiroid winglet, CAPP-lite) без смены основного фокуса.

## What is happening now (branch, commits focus, uncommitted)

- **Ветка:** `develop` → `vds/develop`, HEAD `4c21d6ab` — *feat(sber500): Sprint 0-4 complete — deterministic revolution RE + Spike Generator + demo pack*
- **Недавний фокус коммитов:** детерминированный pipeline тел вращения (Phase 0–5), benchmark kit (8+ STL revolution bodies), Spike Generator, STEP/build123d fixes, R&D-артефакты (spiroid, CAPP direction)
- **Uncommitted (рабочее дерево):**
  - Удалены `__pycache__/*.pyc` (артефакты сборки)
  - Изменены: `backend/agents/coder_agent.py`, `backend/core/state.py`, `backend/sensors/align_open3d.py`, `backend/sensors/slice_trimesh.py`, `benchmark_kit/expected_results.yaml`, `requirements.txt`, `tests/test_math_enhancements.py`
  - По `git diff -w`: **содержательных изменений логики нет** — diff сводится к line endings / форматированию [проверено локально]
  - Коммит не сделан; ветка синхронизирована с remote на последнем коммите

## Blockers (what blocks progress)

| Блокер | Влияние |
|---|---|
| Swarm v2 не подключён к Spike Generator | `SkillRequest` пишется в report, но `controlled_bootstrapper.py` не fulfil'ит автоматически |
| Нет навыков `feature_detector_for_keyway` / `feature_detector_for_transverse_hole` | Acceptance v2 (шпонка + поперечное отверстие в STEP) не достигнут |
| Сложная геометрия вне тел вращения | Фланцы, 2.5D-bracket, lattice — только через будущие skills, не v1 |
| `manufacturing_intent` — placeholder | CAPP-lite (v3) не активирован |
| Text-to-CAD / UI заморожены | Нет browser/desktop demo path в текущем фокусе |
| Internal Use Only | Публикация и patent — post-Sber500 demo (см. roadmap) |

## Last release / milestone

**Sprint 0–4 (Sber500 roadmap) — complete** (2026-05-12 по `docs/ROADMAP.md`):

- Метрики end-to-end, bench inventory (36 STL), RANSAC alignment, arc-gap fix
- Spike Generator (`phi_variance` → `SkillRequest` / `OutOfScopeRegion`)
- One-command demo (`python -m backend.benchmark`), README rewrite, `docs/sber500_deck.md`
- **30/30** acceptance tests (`test_revolution_baseline`, `test_math_enhancements`, `test_out_of_scope_detector`)

## Planned (next 3-5 concrete steps)

1. **v2 kickoff:** связать `SkillRequest.needs_tool` с `controlled_bootstrapper.py`
2. Реализовать первый bootstrapped skill: `feature_detector_for_keyway`
3. Второй skill: `feature_detector_for_transverse_hole`
4. Персистентность навыков в `backend/skills/library/`, reuse между прогонами
5. Активировать LangGraph coordinator после стабилизации bootstrapper; acceptance — STEP с явными вырезами keyway + cross-hole

*Дальше (v3):* наполнение `manufacturing_intent` (process family, stock, datum) — см. `docs/examples/manufacturing_intent.example.yaml`
