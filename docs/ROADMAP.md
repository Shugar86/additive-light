# Roadmap — CAD-Recode backend (this repository)

Living directions for **this** codebase: deterministic sensors, multi-agent reverse engineering STL → parametric `build123d`, validation, and benchmarking.

An older, UI/ecosystem-oriented roadmap for related projects lives in [`archive/ROADMAP.md`](archive/ROADMAP.md) (legacy context; not authoritative for backend runtime).

---

## Planned — CAPP / manufacturing intent (experimental)

These items are **proposed research steps**, not commitments and not shipped in the default pipeline:

- **Feature semantic labeling** — map recovered zones/features to machinable interpretations (beyond pure geometry recovery) with explicit uncertainty; human-in-the-loop by default.
- **`manufacturing_intent.yaml` (contract sketch)** — optional sidecar describing intent, tolerances, stock/fixture hypotheses; sketch only ([example](examples/manufacturing_intent.example.yaml)).
- **Engineering Q&A over STL** — retrieval and answering grounded in sensor slices, feature lists, and mesh-derived evidence (no substitution for dimensional metrology tools).
- **Process route hints** — heuristic suggestions only (additive vs subtractive sequencing, orientation notes); not automated CAPP.

Narrative: [EXPERIMENTAL_CAPP_DIRECTION.md](EXPERIMENTAL_CAPP_DIRECTION.md).
