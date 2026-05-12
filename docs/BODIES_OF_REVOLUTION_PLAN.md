# Bodies of Revolution — Implementation Plan

**Version:** 2.0
**Date:** 2026-05-12 (updated post-Sprint 0–4)
**Status:** Sprint 0–4 complete; see [docs/ROADMAP.md](ROADMAP.md) for v2 plan

---

## 1. Scope

This document specifies the detailed technical plan for implementing deterministic
reverse engineering of **bodies of revolution** (shafts, cylinders, stepped shafts,
flanges, knobs, rings).

Bodies of revolution are the primary use case for the Sber500 accelerator demo and
the most tractable category for the deterministic neuro-symbolic pipeline.

---

## 2. Geometric Definition

A body of revolution is defined by:
- A single **rotation axis** (commonly Z after alignment)
- A **radial profile r(z)** — the radius as a function of position along the axis
- Optionally, **local non-rotational features** (keyways, holes, flats) cut into the surface

The target accuracy requirement:
- Profile RMSE < 0.5mm on ideal STLs
- Profile RMSE < 2.0mm on noisy/real STLs
- IoU proxy > 0.95 on ideal models

**Sprint 0–4 actuals** (see [docs/baseline_results.json](baseline_results.json)):

| Model | RMSE (mm) | IoU | Conf |
|---|---:|---:|---:|
| `ideal_short_disc_shaft` | **0.003** | 1.000 | 0.998 |
| `ideal_cylinder` | 0.356 | 0.986 | 0.677 |
| `ideal_conical_shaft` | 0.445 | 0.975 | 0.636 |
| `ideal_hourglass_shaft` | 0.460 | 0.987 | 0.600 |
| `ideal_fillet_shaft` | 0.979 | 0.954 | 0.397 |
| `Кнопка_2.stl` (real scan) | **0.042** | 0.997 | 0.949 |

---

## 3. Zone Type Taxonomy

| Zone Type | Description | Example | Fitting Method |
|---|---|---|---|
| `CYLINDER` | Constant radius | Main shaft body | `fit_cylinder()` — mean r |
| `CONE` | Linear radius taper | Reduced shaft end | `fit_cone()` — linear regression |
| `FILLET` | Smooth curved transition | Shoulder blend | `fit_arc()` — circle fit |
| `CHAMFER` | Short angled end transition | Lead-in edge | `fit_cone()` — linear |
| `GROOVE` | Circumferential groove | Snap ring groove | Groove profile fit |
| `STEP` | Sharp radius discontinuity | Shaft shoulder | Boundary detection |

---

## 4. Module Map (post-Sprint 4)

```
backend/
├── sensors/
│   ├── align_open3d.py          [UPDATED] PCA + RANSAC refinement (Sprint 2)
│   │                                       ✓ ransac_plane_axes() rescued from P8-P9
│   │                                       ✓ adaptive activation for PCA-degenerate parts
│   ├── shaft_axis.py            [STABLE]  Rotation axis detection
│   ├── shaft_profile.py         [STABLE]  r(z) profiling + zone segmentation
│   ├── slice_trimesh.py         [UPDATED] Low-level slicing (Sprint 0, 3)
│   │                                       ✓ public sample_at_position()
│   │                                       ✓ phi_variance per slice
│   │                                       ✓ phi_variance_profile() batch method
│   └── revolution_fitting.py    [STABLE]  fit_cylinder, fit_cone, fit_arc, fit_all_zones
│
├── pipeline/
│   ├── deterministic_shaft.py   [UPDATED] STL → STEP (Sprint 0–3)
│   │                                       ✓ _zones_to_specs passes FitResult arc params
│   │                                       ✓ Spike Generator (_generate_skill_requests)
│   │                                       ✓ skill_requests + manufacturing_intent in report
│   └── profile_metrics.py       [UPDATED] Sprint 0 API fix
│
├── agents/
│   └── coder_agent.py           [UPDATED] Sprint 2.4
│                                           ✓ _arc_polyline_points() — arc discretisation
│                                           ✓ _build_revolve_polyline() — adaptive samples
│
├── benchmark/                   [NEW]     Sprint 4 one-command demo runner
│   └── __main__.py                         python -m backend.benchmark
│
└── core/
    └── state.py                 [UPDATED] Sprint 2.4 + 3.2
                                            ✓ ShaftZoneSpec: arc_center_z, arc_center_r, arc_radius
                                            ✓ OutOfScopeRegion dataclass
                                            ✓ SkillRequest dataclass
                                            ✓ ShaftConstructionPlan: skill_requests, out_of_scope_regions
```

---

## 5. Pipeline Steps (Detailed)

### 5.1 Alignment and Centering

**Module:** `backend/sensors/align_open3d.py`

- PCA alignment: principal component analysis to find dominant geometry axes
- RANSAC plane detection: for flat-base parts
- ICP refinement: fine-tune alignment using Iterative Closest Point
- Output: centered mesh with consistent axis orientation

**Acceptance criterion:** Mesh bounding box center within 0.1mm of origin.

### 5.2 Rotation Axis Detection

**Module:** `backend/sensors/shaft_axis.py`

Three complementary methods (auto-selected by confidence):
1. **Symmetry analysis:** compare slices at multiple positions; highest circularity axis wins
2. **Slice circularity:** sample X/Y/Z cross-sections, compute circularity = 4πA/P²
3. **Inertia PCA:** principal axes from mesh inertia tensor

Output: `AxisInfo(direction, origin, confidence, length, method)`

**Acceptance criterion:** Axis confidence > 0.7 for ideal models.

### 5.3 Radial Profile Sampling

**Module:** `backend/sensors/shaft_profile.py → slice_trimesh.py`

- Slice mesh at N evenly-spaced positions along the rotation axis
- For each slice: extract the largest 2D polygon (Shapely)
- Compute **boundary-based radius**: mean distance from centroid to all boundary vertices
  (more accurate than `sqrt(A/π)` for bodies of revolution)
- Compute circularity and confidence per sample

Output: `ShaftProfile(samples, total_length, min_radius, max_radius, sample_count)`

**Acceptance criterion:** Radius error < 0.5% on ideal_cylinder.stl with 100 samples.

### 5.4 Zone Segmentation

**Module:** `backend/sensors/shaft_profile.py`

Algorithm:
1. Smooth radius array with Gaussian filter (σ = 2 samples)
2. Compute first derivative dr/dz (slope)
3. Compute second derivative d²r/dz² (curvature)
4. Detect zone boundaries at high-slope or high-curvature positions
5. Classify each zone using `_classify_zone()`:
   - CYLINDER: low slope + low curvature
   - CONE: significant constant slope, long extent (> 2mm, > 1mm radius change)
   - CHAMFER: significant constant slope, short extent
   - FILLET: high curvature with radius change
   - GROOVE: local minimum in radius
   - STEP: large radius discontinuity at boundary

Output: `[ShaftZone(zone_type, start_pos, end_pos, mean_radius, confidence), ...]`

**Acceptance criterion:** Correct zone count on 90%+ of benchmark models.

### 5.5 Primitive Fitting

**Module:** `backend/sensors/revolution_fitting.py`

For each zone, fits the best geometric primitive:
- `fit_cylinder(positions, radii)` → `{radius: R}`
- `fit_cone(positions, radii)` → `{slope: a, intercept: b, half_angle_deg: θ}`
- `fit_arc(positions, radii)` → `{center_z, center_r, arc_radius, arc_span_deg}`

Selection via `classify_and_fit_zone()`:
- Occam's razor: prefer cylinder unless cone/arc is clearly better
- Threshold: cylinder preferred unless its RMS is > 1.5× the best alternative

Output: `[FitResult(primitive_type, residual_rms, r_squared, confidence, params), ...]`

**Acceptance criterion:** Fitting residual < 0.1mm on ideal models.

### 5.6 CAD Reconstruction

**Module:** `backend/pipeline/deterministic_shaft.py` + `backend/agents/coder_agent.py`

- Build `ShaftConstructionPlan` from zone specs and axis info
- Generate build123d code using fixed revolve profile:
  ```python
  with BuildPart():
      with BuildSketch(Plane.XZ):
          with BuildLine():
              Polyline((r1, z1), ..., (0, z_top), (0, z_bot), close=True)
          make_face()
      revolve(axis=Axis.Z)
  ```
- Execute in subprocess, collect STEP output

**Acceptance criterion:** Valid STEP file produced for ideal_cylinder and ideal_stepped_shaft.

### 5.7 Quality Metrics

**Module:** `backend/pipeline/profile_metrics.py`

| Metric | Formula | Interpretation |
|---|---|---|
| `rmse_mm` | `sqrt(mean((r_orig - r_recon)²))` | Average profile error |
| `max_error_mm` | `max(|r_orig - r_recon|)` | Worst-case deviation |
| `iou_proxy` | `1 - mean(|r_orig - r_recon| / max(r_orig, r_recon))` | Volumetric overlap |
| `confidence` | Weighted combination of above | Overall quality |

---

## 6. Benchmark Models

Priority for testing and demo:

| Model | Category | Ground Truth | Priority |
|---|---|---|---|
| `ideal_cylinder.stl` | ideal | r=20mm, h=40mm | ★★★★★ |
| `ideal_stepped_shaft.stl` | ideal | r=[15, 10]mm, h=50mm | ★★★★★ |
| `noise_cylinder.stl` | noise | r=20mm ±noise | ★★★★☆ |
| `noise_stepped_shaft.stl` | noise | r=[15, 10]mm ±noise | ★★★★☆ |
| `Кнопка_2.stl` | real | unknown | ★★★☆☆ |
| `кольцо.stl` | real | ring/torus | ★★★☆☆ |
| `plain_shaft.stl` (fixture) | fixture | single cylinder | ★★★★☆ |
| `stepped_shaft.stl` (fixture) | fixture | 3 zones | ★★★★☆ |

---

## 7. Acceptance Criteria for Sber500 Demo

### Minimum Viable Demo (achieved Sprint 4)

```bash
# One-command, ~30 seconds, 8 parts:
python -m backend.benchmark
# → temp/sber500/<timestamp>/{report.json, summary.md, previews/*.png}
```

Achieved criteria:

1. **CLI works end-to-end** — `python -m backend.benchmark` completes 8 STL in ≈33s.
2. **Output artefacts present** — STEP + parametric script + report.json per part.
3. **Report metrics** (actual Sprint 4 numbers):
   - `ideal_short_disc_shaft`: RMSE **0.003 mm**, conf **0.998** ← sub-tessellation.
   - `Кнопка_2.stl` (real scan): RMSE **0.042 mm**, conf **0.949** ← sub-tessellation on real photogrammetry.
   - `ideal_conical_shaft`: RMSE **0.445 mm** after Sprint 2.4 arc fix (was 3.365 mm, 7.7× improvement).
4. **STEP file** — opens in FreeCAD / SolidWorks / Fusion / Inventor.
5. **30/30 tests green** — `pytest tests/test_revolution_baseline.py tests/test_math_enhancements.py tests/test_out_of_scope_detector.py`.
6. **Spike Generator** — `shaft_with_keyway.stl` produces 4 `SkillRequest` payloads; `plain_shaft.stl` produces 0.

### r(z) overlay previews

`backend/benchmark/__main__.py` generates `previews/<stem>_overlay.png` for every part (source r(z) vs reconstructed r(z), matplotlib). These power the visual diff in the deck.

---

## 8. Known Limitations (First Version)

1. **Axis detection limited to X/Y/Z candidates** — tilted parts may fail unless
   manually pre-aligned.

2. **Fillet arc fitting is approximate** — algebraic circle fit may not converge
   for short, noisy fillets. Fallback: classify as chamfer.

3. **Non-revolution features are ignored** for CAD generation — keyways, flats,
   holes require a secondary cut operation (already scaffolded in `coder_agent.py`
   but not integrated into `deterministic_shaft.py`).

4. **build123d revolve may fail for degenerate profiles** — zero-radius zones or
   zones with z_start >= z_end cause topology errors. The pipeline returns the
   generated code but marks `success=False` in this case.

---

## 9. Future Work

### v2 (swarm activation)

1. **Spike Generator → bootstrapper** — wire `SkillRequest.needs_tool` into `controlled_bootstrapper.py`; first skills: `feature_detector_for_keyway`, `feature_detector_for_transverse_hole`.
2. **Local feature CAD integration** — keyways and cross-holes were always scaffolded in `coder_agent.py` (`_generate_feature_cut`); v2 makes them real.
3. **Spline fitting for barrel/freeform zones** — `ideal_barrel_shaft.stl` RMSE 11.7 mm is the current canary.
4. **LangGraph coordinator activation** — once bootstrapper is stable.

### v3 (CAPP-lite)

5. **Populate `manufacturing_intent`** — process family, stock assumption, primary datum, tolerance notes.
6. **Engineering Q&A** over the same mesh + zone evidence.

### Infrastructure

7. **Arbitrary 3D axis** — RANSAC currently refines PCA but still picks from {X,Y,Z}; post-v2 can extend to arbitrary in-plane axis using symmetry fit.
8. **Scan noise robustness** — calibrate `phi_variance` threshold and zone segmentation hyperparameters on a larger real-scan dataset.
9. **Open-source publication** — post-Sber500 demo; defensive publication on zone-fitting + Spike Generator method.
