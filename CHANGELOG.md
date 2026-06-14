# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Vibe-first documentation pass: `README.md`, `AGENTS.md`, `LICENSE`, `CONTRIBUTING.md`, `CHANGELOG.md`.
- Project identity documents: `PROJECT.md`, `COCKPIT.md`, `SPOTLIGHT.md`, `STATE.md`.

### Changed
- `README.md` updated with badges, project structure, and links to governance docs.
- License moved from "Internal Use Only" to Apache-2.0.

## [0.4.0] — Sprint 0-4: Sber500 demo pack

### Added
- End-to-end deterministic revolution-body pipeline (`backend/pipeline/deterministic_shaft.py`).
- Spike Generator: out-of-scope detection via `phi_variance` → structured `SkillRequest`.
- 36 STL benchmark fixtures across `ideal/`, `noise/`, `corrupt/`, and `real_scans/`.
- `benchmark_kit/expected_results.yaml` with ground-truth per fixture.
- `scripts/run_benchmark_matrix.py` for one-command batch benchmarking.
- `python -m backend.benchmark` one-command demo entry point.
- `docs/sber500_deck.md` pitch skeleton.
- R&D artefacts: spiroid winglet reconstruction, alternative parametric scripts, experimental CAPP direction.

### Fixed
- STEP export path and `build123d` imports.
- Deterministic arc-gap fitting for conical shafts.
- PCA-degenerate alignment via RANSAC refinement.

## [0.3.0] — Deterministic revolution bodies (Phase 0-5)

### Added
- Deterministic fitting for cylinder, cone, arc, and spline zones.
- Zone segmentation on `r(z)` profile.
- `backend/sensors/align_open3d.py`, `shaft_axis.py`, `slice_trimesh.py`, `shaft_profile.py`, `revolution_fitting.py`.
- `backend/agents/coder_agent.py` build123d script generation with arc discretisation for fillets/chamfers.
- `tests/test_revolution_baseline.py`, `tests/test_math_enhancements.py`, `tests/test_out_of_scope_detector.py` (30/30 acceptance).

### Changed
- Shifted hero path from LLM-driven swarm to deterministic sensors-first pipeline.

## [0.2.0] — Shaft Reverse Engineering MVP

### Added
- `backend/main.py` facade with `process_stl()` API.
- `backend/core/state.py` Pydantic models: `CADState`, `ShaftConstructionPlan`, `SkillRequest`.
- `backend/core/graph.py` LangGraph orchestration with parallel sensors and reflection loop.
- `backend/core/agent_contracts.py` + `SpecLoader` for YAML agent specs.
- `backend/validators/ast_validator.py` and `backend/executor/secure_executor.py` for sandboxed codegen.
- `backend/agents/coordinator_agent.py`, `sensor_agent.py`, `vibeguard_agent.py`.
- `config/agents/*.yaml` and `config/swarm_policy.yaml`.
- `OpenSCAD_AI/` GUI app and SCAD-AI bridge (experimental).

## [0.1.0] — CAD swarm architecture

### Added
- Policy-driven multi-agent contracts (`CADAgentSpec`, `SwarmPolicy`, `ExecutionPolicy`).
- Skill Library scaffold (`backend/skills/skill_library.py`) for Voyager-style tool growth.
- Local git pre-push hook (`.github/workflows/` and hook management).
- Initial project structure, `requirements.txt`, and README.
