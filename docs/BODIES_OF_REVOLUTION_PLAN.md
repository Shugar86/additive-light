# Bodies of Revolution — Implementation Plan

**Version:** 1.0
**Date:** 2026-03-22
**Status:** Active R&D

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

## 4. Module Map

```
backend/
├── sensors/
│   ├── align_open3d.py          [STABLE]  PCA/ICP alignment
│   ├── shaft_axis.py            [STABLE]  Rotation axis detection
│   ├── shaft_profile.py         [UPDATED] r(z) profiling + zone segmentation
│   │                                       ✓ CONE zone type added
│   │                                       ✓ Boundary-based radius estimation
│   ├── slice_trimesh.py         [UPDATED] Low-level slicing
│   │                                       ✓ boundary_radius added
│   ├── shaft_features.py        [STABLE]  Keyways, flats, holes (secondary)
│   └── revolution_fitting.py    [NEW]     Per-zone primitive fitting
│                                           ✓ fit_cylinder, fit_cone, fit_arc
│                                           ✓ classify_and_fit_zone
│
├── pipeline/
│   ├── __init__.py              [NEW]
│   ├── deterministic_shaft.py   [NEW]     STL → STEP without LLM
│   └── profile_metrics.py       [NEW]     r(z) comparison metrics
│
└── agents/
    └── coder_agent.py           [UPDATED] Fixed revolve code generator
                                            ✓ Polyline-based profile
                                            ✓ CONE zone support
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

### Minimum Viable Demo

1. **CLI works end-to-end:**
   ```
   python -m backend.pipeline.deterministic_shaft \
       benchmark_kit/ideal/ideal_stepped_shaft.stl \
       -o output/demo/
   ```
   Completes in < 30 seconds.

2. **Output artifacts present:**
   - `output/demo/shaft.step` — valid STEP file
   - `output/demo/ideal_stepped_shaft_report.json` — quality report
   - `output/demo/ideal_stepped_shaft_parametric.py` — build123d source

3. **Report metrics:**
   - Zone count: 2 (both cylinder zones detected)
   - Radius 1: 15.0mm ± 0.5mm
   - Radius 2: 10.0mm ± 0.5mm
   - Profile RMSE < 0.5mm

4. **STEP file:** opens in FreeCAD/CAD viewer and looks like the input STL.

### Stretch Goals

- Same pipeline succeeds on `noise_cylinder.stl` and `Кнопка_2.stl`
- Visual profile comparison plot (matplotlib)
- HTML report with embedded charts
- Benchmark table showing accuracy across 5+ models

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

## 9. Future Work (Post-Sber500)

1. **Spline fitting for freeform zones** — B-spline fit for complex profiles
2. **Non-revolution bodies** — prismatic parts, extrusions, swept solids
3. **Local feature integration** — keyways and cross-holes in deterministic_shaft.py
4. **Visual output** — matplotlib profile comparison in pipeline
5. **Confidence thresholding** — auto-escalate to LLM coordinator when confidence < 0.5
