# Contributing to additive-light

Thanks for taking the time to contribute. This project is a personal R&D / deeptech artefact built around a deterministic reverse-engineering pipeline. We value small, focused changes over large refactorings.

## How to contribute

1. **Open an issue first** for anything bigger than a typo or a one-line fix — especially if it touches `backend/pipeline/deterministic_shaft.py`, `backend/sensors/`, or `backend/core/state.py`.

2. **Fork the repository** (or create a feature branch if you have write access):

   ```bash
   git checkout develop
   git pull
   git checkout -b feat/your-change
   ```

3. **Set up the environment:**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Make the smallest change that works.** Follow KISS, YAGNI, and the existing code style.

5. **Add or update tests** for any non-trivial sensor, fitting, or pipeline change.

6. **Run the fast acceptance suite before pushing:**

   ```bash
   pytest tests/test_revolution_baseline.py \
          tests/test_math_enhancements.py \
          tests/test_out_of_scope_detector.py -v
   ```

7. **Commit with a conventional commit message:**

   ```bash
   git commit -m "feat(sensors): add barrel zone fitting"
   ```

8. **Open a Pull Request** against `develop` with:
   - a clear description of the change;
   - the motivation and context;
   - the test results.

## Branch naming

- `feat/<scope>-<what>` — new feature
- `fix/<scope>-<what>` — bug fix
- `docs/<what>` — documentation only
- `test/<what>` — test changes
- `chore/<what>` — maintenance

## Style guide

- Python 3.11+ with type hints everywhere.
- Google-style docstrings for public functions and classes.
- No bare `except:` — catch specific exceptions.
- No LLM in the deterministic math path. Keep geometry code in `backend/sensors/` and `backend/pipeline/` free of model calls.
- Use `pathlib.Path` for file paths.
- Keep functions small and single-purpose.

## Security

- Never commit `.env`, API keys, tokens, or personal SSH keys.
- Generated `build123d` scripts must pass `ASTValidator` checks.
- If you add a new import to generated code, update `config/swarm_policy.yaml` and the allowlist logic in `backend/validators/ast_validator.py`.

## Definition of Done for a PR

- [ ] Acceptance tests pass (or the PR explains why they are intentionally not run).
- [ ] New logic has at least one success test and one edge-case test.
- [ ] No secrets or build artifacts (`__pycache__/`, `.env`) are committed.
- [ ] `README.md`, `AGENTS.md`, or `docs/` are updated if the change affects usage, architecture, or agent rules.
- [ ] Commit messages follow Conventional Commits.

## Questions?

Open an issue or check [`STATE.md`](./STATE.md) and [`docs/ROADMAP.md`](./docs/ROADMAP.md) for current focus and blockers.
