# Roadmap — additive-light backend

**Last updated:** 2026-05-12 (Sber500 Sprint 0–4 complete)

---

## Status as of Sprint 4

Sprint 0–4 of the Sber500 R&D roadmap are fully shipped:

| Sprint | Summary | Key artefacts |
|---|---|---|
| 0 | Metrics end-to-end | `profile_metrics.py` fix; `scipy` pinned; `docs/baseline_results.json` |
| 1 | Bench inventory + 6 evil-shafts | `docs/bench_inventory.md`; `scripts/run_benchmark_matrix.py`; 6 new STL |
| 2 | RANSAC alignment + arc-gap closing | `ransac_plane_axes()` in `align_open3d.py`; arc discretisation in `coder_agent.py`; math tests |
| 3 | Spike Generator | `phi_variance_profile()`; `SkillRequest`/`OutOfScopeRegion` in `core/state.py`; `test_out_of_scope_detector.py` |
| 4 | One-command demo + deck | `python -m backend.benchmark`; `README.md` rewrite; `docs/sber500_deck.md` |

**Test baseline:** `pytest tests/test_revolution_baseline.py tests/test_math_enhancements.py tests/test_out_of_scope_detector.py` → **30 passed**.

**Hero numbers:**

| STL | RMSE (mm) | Conf |
|---|---:|---:|
| `ideal_short_disc_shaft.stl` | 0.003 | 0.998 |
| `Кнопка_2.stl` (real scan) | 0.042 | 0.949 |
| `ideal_conical_shaft.stl` | 0.445 | 0.636 |
| `ideal_hourglass_shaft.stl` | 0.460 | 0.600 |

---

## v2 — Swarm activation (next)

Enable the Spike Generator's `SkillRequest` payloads to be fulfilled automatically:

- [ ] Wire `SkillRequest.needs_tool` into `controlled_bootstrapper.py`.
- [ ] Implement `feature_detector_for_keyway` as the first bootstrapped skill.
- [ ] Implement `feature_detector_for_transverse_hole` (second skill).
- [ ] Persist learned skills in `backend/skills/library/`; reuse across runs.
- [ ] Activate LangGraph coordinator once bootstrapper is stable.

**Acceptance for v2:** a new shaft with a keyway and a cross-hole produces a STEP file where both features are explicitly cut, not just averaged over.

---

## v3 — CAPP-lite / manufacturing intent (planned)

The `manufacturing_intent` JSON slot already ships in every v1 report (activated: false). Activation means:

- [ ] Populate `process_family` (turning / milling / hybrid) from zone taxonomy.
- [ ] Populate `stock_assumption` (bar / near_net) from bounding-box analysis.
- [ ] Add `primary_datum_hypothesis` from axis confidence.
- [ ] Optionally surface engineering Q&A over the same mesh evidence.

Schema design: [docs/examples/manufacturing_intent.example.yaml](examples/manufacturing_intent.example.yaml).

---

## Explicit non-roadmap items (will not be done in current focus)

- Browser-based Text-to-CAD UI (frozen; see [docs/DECISION_MEMO_TEXT2CAD.md](DECISION_MEMO_TEXT2CAD.md)).
- Drawing-to-CAD.
- Arbitrary 3D (non-axis-aligned) rotation axis (post-v2).
- Open-source GitHub publication (post-Sber500 demo).
- Provisional patent (post-demo; defensive publication preferred).
