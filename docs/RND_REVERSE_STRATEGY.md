# R&D Reverse Engineering Strategy

**Version:** 1.0
**Date:** 2026-03-22
**Track:** Deterministic Reverse Engineering — Bodies of Revolution

---

## 1. Strategic Position

### What we are building

A **neuro-symbolic reverse engineering pipeline** that converts STL mesh scans
of mechanical parts into parametric CAD models. The pipeline is primarily
deterministic (pure geometry math) with LLM as an optional enhancer for
ambiguous cases.

### Deeptech differentiation

Most "AI CAD" products are wrapper prompts around general-purpose LLMs. Our
differentiation is the **deterministic geometry core**:

```
sensor → profile extraction → zone fitting → deterministic revolve → STEP
```

This is reproducible, explainable, and measurable — a real engineering contribution,
not "GPT-4 writes OpenSCAD."

### Primary focus: bodies of revolution

Rotationally symmetric parts (shafts, cylinders, stepped shafts, flanges, knobs)
represent the largest single category of machined parts in mechanical engineering.
They are tractable with a deterministic profile-based approach and produce
convincing, demonstrable results quickly.

---

## 2. Pipeline Architecture

### Target deterministic pipeline

```
STL Input
  │
  ▼
[1] Alignment & Centering          align_open3d.py
  │  PCA centering, axis normalization
  │
  ▼
[2] Rotation Axis Detection         shaft_axis.py
  │  Symmetry analysis, slice circularity, inertia PCA
  │  → AxisInfo(direction, confidence, length)
  │
  ▼
[3] Axis Alignment to Z             shaft_axis.align_mesh_to_axis()
  │  Rotate mesh so rotation axis → world Z
  │
  ▼
[4] Radial Profile Sampling         shaft_profile.py → slice_trimesh.py
  │  100+ cross-sections along Z, boundary-based radius r(z)
  │  → ShaftProfile(samples, total_length, min/max_radius)
  │
  ▼
[5] Zone Segmentation               shaft_profile.segment_rotational_zones()
  │  Gradient/curvature analysis, zone boundary detection
  │  → [ShaftZone(type, start_pos, end_pos, radius, confidence), ...]
  │
  ▼
[6] Primitive Fitting per Zone      revolution_fitting.py
  │  Least-squares fit: cylinder (constant r), cone (linear r), arc (curved r)
  │  → [FitResult(primitive_type, params, residual_rms, confidence), ...]
  │
  ▼
[7] CAD Reconstruction              pipeline/deterministic_shaft.py
  │  ShaftConstructionPlan → build123d revolve() → STEP
  │
  ▼
[8] Quality Metrics                 pipeline/profile_metrics.py
  │  r(z) RMSE, max error, zone IoU proxy, overall confidence
  │  → ProfileMetrics(rmse_mm, max_error_mm, iou_proxy, confidence)
  │
  ▼
Output: STEP file + JSON report + profile comparison plot
```

### LLM integration points (deferred)

LLM is **NOT** in the critical path for bodies of revolution. It may be added later:
- As a fallback interpreter when deterministic confidence < 0.5
- For natural-language part description generation
- For non-revolution bodies (prismatic, freeform) where geometry is too complex

### Frozen modules (no active development)

| Module | Status | Reason |
|---|---|---|
| `backend/agents/coordinator_agent.py` | Frozen | LLM bottleneck; not needed for shafts |
| `backend/agents/sensor_agent.py` | Frozen | LLM wrapper; sensors work directly |
| `backend/core/graph.py` | Frozen | LangGraph overhead; use `deterministic_shaft.py` |
| `backend/skills/` | Frozen | Voyager skill system; not shaft-relevant |
| `backend/core/agent_prompt_compiler.py` | Frozen | VibeCraft persona system |
| `OpenSCAD_AI/` | Frozen | Legacy desktop prototype |

---

## 3. Zone Type Taxonomy

Bodies of revolution decompose into these primitive zone types:

| Zone Type | Description | Fitting Method | CAD Operation |
|---|---|---|---|
| CYLINDER | Constant radius section | `fit_cylinder()` — mean r | `revolve(Rectangle(...))` |
| CONE | Linearly varying radius (frustum) | `fit_cone()` — linear regression | `revolve(Polyline(...))` |
| FILLET | Smooth curved transition | `fit_arc()` — circle fit | `revolve(spline(...))` |
| CHAMFER | Short angled end transition | `fit_cone()` — linear | `revolve(Polyline(...))` |
| GROOVE | Circumferential groove | groove profile fit | `revolve(...)` subtract |
| STEP | Sharp radius discontinuity | boundary detection | implicit in profile |

---

## 4. Quality Metrics

### Primary metrics

| Metric | Formula | Target (ideal) | Target (noise) |
|---|---|---|---|
| Profile RMSE | `sqrt(mean((r_orig - r_recon)²))` | < 0.1mm | < 0.5mm |
| Profile max error | `max(|r_orig - r_recon|)` | < 0.5mm | < 2.0mm |
| IoU proxy | `1 - mean(|r_orig - r_recon| / max(r_orig, r_recon))` | > 0.98 | > 0.90 |
| Zone count accuracy | `detected_zones == expected_zones` | 100% | 90% |
| Radius accuracy | `|r_detected - r_ground_truth|` | < 0.2mm | < 0.8mm |

### Confidence scoring

Zone-level confidence (0–1) is computed from:
- Circularity of cross-sections (0 = rectangle, 1 = perfect circle)
- Fitting residual relative to zone radius
- Consistency of samples within zone

Overall pipeline confidence = weighted average of zone confidences.

---

## 5. Benchmark Coverage

### Current benchmark kit

| Category | Count | Notes |
|---|---|---|
| `ideal/` | 8 STLs | Perfect geometry; includes cylinder, stepped shaft, flange |
| `noise/` | 8 STLs | Gaussian noise added; tests robustness |
| `corrupt/` | 7 STLs | Partially missing geometry; tests graceful degradation |
| `real_scans/` | 7 STLs | Real scan data including Кнопка_2, кольцо |
| `tests/fixtures/` | 10 STLs | Shaft-specific synthetic fixtures |

### Revolution bodies subset

Priority bodies for R&D validation:
1. `ideal_cylinder.stl` — baseline sanity check (must pass at > 99% accuracy)
2. `ideal_stepped_shaft.stl` — zone segmentation (must detect 2 zones correctly)
3. `noise_cylinder.stl` — robustness check
4. `noise_stepped_shaft.stl` — noisy segmentation
5. `Кнопка_2.stl` — real scan (best-effort)
6. `кольцо.stl` — real ring/torus scan
7. `tests/fixtures/plain_shaft.stl` — controlled shaft
8. `tests/fixtures/stepped_shaft.stl` — controlled stepped shaft

---

## 6. Roadmap

### Phase 0 — Diagnostic Baseline (DONE)
- Baseline test: `tests/test_revolution_baseline.py`
- Measures current sensor accuracy before any changes
- Deliverable: `docs/baseline_results.json`

### Phase 1 — Sensor Upgrade
- Boundary-based radius estimation in `slice_trimesh.py`
- CONE zone type in `shaft_profile.py`
- Improved zone boundary detection
- Target: cylinder radius error < 0.5% on ideal models

### Phase 2 — Primitive Fitting
- `backend/sensors/revolution_fitting.py`
- Least-squares fits: `fit_cylinder`, `fit_cone`, `fit_arc`
- Per-zone fitted parameters with residual error
- Target: fitting residual < 0.1mm on ideal models

### Phase 3 — Deterministic CAD Reconstruction
- `backend/pipeline/deterministic_shaft.py` — standalone STL → STEP
- Fixed `coder_agent.py` with working Polyline revolve code
- No LLM required anywhere in this path
- Target: STEP output opens in FreeCAD and visually matches input

### Phase 4 — Judge / Metrics / Benchmark
- `backend/pipeline/profile_metrics.py`
- Automated benchmark on all `benchmark_kit/ideal/` revolution bodies
- Target: RMSE < 0.5mm, IoU proxy > 0.95 on ideal models

### Phase 5 — Sber500 Demo
- CLI: `python -m backend.pipeline.deterministic_shaft mesh.stl -o output/`
- Visual: matplotlib profile comparison plot
- Report: JSON + summary HTML
- Benchmark table: accuracy across 5+ models
- Timing: < 30s end-to-end on typical shaft

---

## 7. Benchmark Kit

Ground-truth STL files for reproducible R&D validation. All files are generated programmatically via `scripts/generate_benchmark_stl.py` (trimesh-only, no build123d dependency).

| File | Type | Radius (mm) | Height (mm) | Notes |
|------|------|-------------|-------------|-------|
| `benchmark_kit/ideal/ideal_cylinder.stl` | ideal | 20.0 | 40.0 | Perfect mesh, 128 sections |
| `benchmark_kit/ideal/ideal_stepped_shaft.stl` | ideal | 15.0/10.0 | 50.0 | 2-zone stepped shaft |
| `benchmark_kit/noise/noise_cylinder.stl` | noise | 20.0±0.3 | 40.0 | Gaussian noise σ=0.3mm |
| `benchmark_kit/noise/noise_stepped_shaft.stl` | noise | 15.0/10.0±0.5 | 50.0 | σ=0.5mm |
| `tests/fixtures/plain_shaft.stl` | fixture | 9.984 | 50.0 | Slightly under 10mm, sections=64 |
| `tests/fixtures/stepped_shaft.stl` | fixture | 15.0/10.0 | 50.0 | 2-zone reference, sections=64 |

### Ground Truth Parameters

| Model | Zone Count | Tolerance (mm) | Min Confidence |
|-------|------------|----------------|----------------|
| ideal_cylinder | 1 | 0.2 | 0.95 |
| ideal_stepped_shaft | 2 | 0.2 | 0.92 |
| noise_cylinder | 1 | 0.5 | 0.80 |
| noise_stepped_shaft | 2 | 0.8 | 0.70 |
| plain_shaft_fixture | 1 | 0.5 | 0.70 |
| stepped_shaft_fixture | 2 | 0.5 | 0.70 |

---

## 8. Technical Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Zone boundary detection instability | Medium | High | Gaussian smoothing + breakpoint suppression already implemented |
| Fillet/arc fitting convergence | Medium | Medium | Fallback to linear interpolation if arc fitting fails |
| build123d Polyline profile topology errors | Medium | High | Validate profile before revolve; fallback to Rectangle approach |
| Real scan mesh quality (holes, noise) | High | Medium | Graceful degradation: return partial result with low confidence flag |
| Axis alignment failure for tilted scans | Low | High | ICP refinement after PCA alignment |

---

## 9. Definition of Done for Sber500 Demo

The demo is ready when:

1. `python -m backend.pipeline.deterministic_shaft benchmark_kit/ideal/ideal_stepped_shaft.stl -o output/`
   completes in < 30 seconds.

2. Output contains: `output.step`, `output_report.json`, `output_profile.png`.

3. The STEP file, opened in FreeCAD, visually matches the input STL.

4. The report shows:
   - Profile RMSE < 0.5mm
   - Zone count: correct (2 zones detected)
   - Both zone radii within 0.5mm of ground truth (15mm and 10mm)
   - Overall confidence > 0.85

5. The same pipeline runs without errors on at least 3 additional benchmark models
   (`ideal_cylinder`, `noise_cylinder`, `Кнопка_2`).
