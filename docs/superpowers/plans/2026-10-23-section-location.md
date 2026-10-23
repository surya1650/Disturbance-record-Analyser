# Section-aware location implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Deliver an opt-in section-aware solver and independent numerical evidence without new field data.

**Architecture:** A pure candidate/window solver owns section equations and ambiguity refusal. Main and reviewed-stage adapters preserve existing intake, review and electrical gates. A separate offline numerical runner uses a phase nodal oracle.

**Tech Stack:** Python >=3.10, NumPy, pytest, existing registry/DSP; no new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-23-section-location-design.md`

## Global Constraints

- Strict boolean opt-in, default false; do not enable an operational registry.
- No coupling, shunts, compensation, unreviewed models, scalar fallback or automatic towers.
- No changes to field data, source workbook, Dash findings, app database or preview processes.
- Engineering screens are not confidence or field accuracy guarantees.
- Preserve historical numerical artifacts and source hashes.

## Review Focus

- Adjacent junction descriptions collapse, physically distinct roots never collapse.
- One invalid sample must not disappear in median aggregation.
- Disabled/unreviewed models and missing/weak/saturated terminal evidence refuse.
- Reversal and remote rotation preserve physical chainage independently of section fraction.
- Biased measurements/parameters may fit perfectly; report the resulting error and refusals.

### Task 1: Pure candidate and window solver

**Files:** Create `src/dranalyser/faultloc/sections.py`, `tests/test_section_solver.py`.

**Interfaces:** `section_model_reasons(line) -> list[str]`; `section_candidates(line, vs, is_, vr, ir, *, aligned=False) -> dict`; `section_window(line, vs, is_, vr, ir, *, aligned=False) -> dict`. Located window returns status, m, km_from_S, interval_pu, diagnostics; refusals contain no distance. Candidates expose chainage, reactance fraction, section identifiers and recovered angle.

- [x] Write nodal-oracle tests for mixed/junction/reversed/rotated cases and invalid models/windows, asserting physical chainage within 1e-7 km for ideal located cases and explicit ambiguity refusal.
- [x] Run `python -m pytest tests/test_section_solver.py -q`; observe missing solver RED.
- [x] Implement section propagation, normalized E5 roots, aligned continuity, junction-only deduplication and conservative window screens from spec.
- [x] Run focused tests and `python -m pytest -q`; inspect all output.
- [x] Commit pure solver/tests, record RED/GREEN and complete task ledger.

### Task 2: Guarded registry and main/stage integration

**Files:** Modify registry `model.py`, `loader.py`, faultloc `ensemble.py`, `stage_location.py`; create `section_location.py`, `tests/test_section_integration.py`.

**Interfaces:** `Line.section_solver_enabled: bool = False`, loader rejects non-booleans. Adapter consumes Task 1 and TerminalInput with existing LocationResult. Stage dispatch consumes existing reviewed, eligible local windows; main dispatch requires both ends and explicit good clocks for aligned mode, otherwise uses unsynchronised mode.

- [x] Write real-DSP/nodal-phasor tests for opt-in chainage, default refusal, no single-ended fallback/towers, review/coupling/shunt/compensation gates, balanced/weak/saturated/missing evidence and reviewed-stage results.
- [x] Run `python -m pytest tests/test_section_integration.py -q`; observe missing enabled behavior RED.
- [x] Implement strict opt-in loading, dedicated adapter and dispatch without touching scalar method selection.
- [x] Run focused tests and full suite; commit and record task evidence.

### Task 3: Reproducible independent numerical evidence and delivery

**Files:** Create `scripts/section_numerical_validation.py`, `tests/test_section_validation.py`, `project-docs/SECTION_VALIDATION_2026-10-23.md` and JSON aggregate under `project-docs/validation`; update README, standards matrix, NEXT_SESSION and STATUS_LEDGER.

**Interfaces:** offline `run(seed=854) -> dict` reports scenario counts/errors/refusal reasons; exclusive-output CLI refuses overwrites. Consumes tests' phase oracle, not production synthetic generator.

- [x] Write runner tests proving all planned cases accounted for, ideal aligned error <1e-7 km, rotational/reversal invariance, nonzero perturbed errors, strict JSON and exclusive output; run RED.
- [x] Implement seeded sweep over geometry/phase/resistance/rotation plus noise, gain and impedance bias. Run fresh aggregate and document all denominators and model limits.
- [x] Run full suite, architecture direct/self-test, focused Ruff and Stage-A 10,000; preserve logs.
- [x] Obtain one fresh whole-branch reviewer per executing-plans. Reproduce material findings RED, fix once, repeat affected checks and final full suite.
- [x] Commit final evidence, fast-forward main, run primary full suite, push and verify remote HEAD. Archive managed worktree after preserving QA; verify Dash hashes unchanged.
