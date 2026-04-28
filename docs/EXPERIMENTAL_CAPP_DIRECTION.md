# Experimental direction: CAPP, manufacturing intent, engineering Q&A

**Status:** early research. Nothing described here is required for or enabled in the production reverse-engineering graph unless explicitly stated elsewhere.

## Why this direction

This repository already stresses **deterministic geometry** (sensors, slices, zone-level structure, construction plans) before LLM reasoning. A natural next step in *research* is to surface **manufacturing intent** next to that geometry: what a human might need to plan operations, communicate with a shop, or ask grounded questions about a mesh-derived part—without pretending to replace CAM or full CAPP.

## How this differs from “STL → CAD”

**STL → parametric CAD** here means recovering or generating a **modeling** program (`build123d`) that matches input shape. **Manufacturing intent** is orthogonal: labels, tolerances, stock assumptions, sequence *hints*, and Q&A that reference the same evidence trail (slices, features, zones) but target **process planning and communication**, not mesh congruence alone. We are not claiming automatic feature recognition at production CAPP depth.

## Planned experiments (3–5)

1. **Semantic labeling pilot** — attach provisional labels to `Feature3D`-class outputs (e.g. “likely bearing seat”, “internal groove”) with confidence and provenance to sensor IDs; no automatic toolpath generation.
2. **`manufacturing_intent` sidecar** — evolve the sketch in [examples/manufacturing_intent.example.yaml](examples/manufacturing_intent.example.yaml) alongside benchmark or ad-hoc parts; validate human readability, not pipeline consumption.
3. **Engineering Q&A prototype** — closed-book answers over fixed corpora: slice JSON, feature lists, and docstrings; explicit “unknown” when evidence is missing.
4. **Process route hints** — rule/LLM-assisted suggestions (additive orientation, rough turning vs finishing) marked as **non-authoritative** and review-only.
5. **Evaluation hooks** — lightweight checklists comparing intent files to expert annotations on a small labeled set (planned; not a shipped metric gate).

## Current limitations

- No end-to-end **CAPP** or certified manufacturing output.
- **`manufacturing_intent` YAML** is not loaded by the default orchestration; stub models under `backend/experimental/` (if present) are **not** wired into LangGraph.
- **Engineering Q&A** will hallucinate without strict grounding and scope limits—we treat RAG/over-mesh QA as experimental only.

See [ROADMAP.md](ROADMAP.md) for a short prioritized list of research bullets.
