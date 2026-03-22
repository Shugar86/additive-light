# Decision Memo: Text-to-CAD Module Status

**Date:** 2026-03-22
**Status:** Archived — no action required
**Author:** Architecture Review

---

## Context

The original product vision documented in `docs/archive/` included a browser-based
Text-to-CAD UI with Pyodide, SolidPython2, OpenSCAD WASM, Web Workers, and Three.js.
The current code audit was conducted to determine whether this component exists in the
codebase and what action to take.

## Finding

**Code audit confirmed (2026-03-22):** There is NO browser-side Text-to-CAD
implementation in this repository. Pyodide, SolidPython2, OpenSCAD WASM, Three.js
references exist **only** in `docs/archive/` documentation — they were never
implemented.

The only non-backend legacy code is `OpenSCAD_AI/` which contains two Python desktop
scripts (`gui_app.py`, `scad_ai.py`) — a pre-agent-era prototype, not a browser app.

## Decision Table

| Component | Status | Rationale |
|---|---|---|
| Browser Text-to-CAD UI | **Archived** | Design exists in `docs/archive/`; never implemented |
| `OpenSCAD_AI/gui_app.py` | **Frozen** | Legacy desktop prototype; no active development |
| `OpenSCAD_AI/scad_ai.py` | **Frozen** | Legacy; keep for historical reference |
| `docs/archive/` | **Preserved** | Historical design record; do not delete |
| Reverse Engineering (`backend/`) | **ACTIVE** | Sole R&D focus |

## Consequences

1. **No code deletion, no split, no freeze ceremony needed.** Text-to-CAD never
   existed as running code, so there is nothing to isolate or migrate.

2. **`OpenSCAD_AI/` stays in the repo as-is.** It does not interfere with the
   `backend/` pipeline in any way.

3. **All development effort goes to `backend/`**, specifically the deterministic
   reverse engineering pipeline for bodies of revolution.

4. **Reassessment trigger:** If the project advances past the Sber500 demo and
   a second product track is required, Text-to-CAD can be initiated as a new
   module — not resurrected from archive, but built fresh on top of the
   existing sensor + build123d foundation.

## Next Review

Text-to-CAD relevance will be reassessed post-Sber500 accelerator demo (target: Q2 2026).
