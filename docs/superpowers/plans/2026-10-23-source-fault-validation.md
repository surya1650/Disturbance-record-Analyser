# Source and fault validation implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans task-by-task, with one fresh whole-branch reviewer.

**Goal:** Extend independent section-solver evidence to weak/unequal/asymmetric sources and additional physical fault connections.

**Architecture:** A new test-only phase nodal oracle builds explicit source/fault circuits. A separate offline runner evaluates the existing solver without truth-based root selection; actual-DSP tests assess guarded dispatch. Historical benchmarks remain frozen.

**Tech Stack:** Python >=3.10, NumPy, pytest; no new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-23-source-fault-validation-design.md`

## Global Constraints

- No new field data or operational registry enablement.
- Do not relax production/model/clock/sequence/review gates to improve coverage.
- Preserve prior oracles, benchmarks/hashes, Dash, workbook, app database and preview processes.
- Report refusals, balanced controls and measurement eligibility separately; no field/confidence claim.

## Review Focus

- Physical source reversal must reverse source facts as well as sections and chainage.
- Every fault connection must satisfy independent contact and earth KCL laws.
- Balanced/source-unbalanced controls must not silently enter an operational accuracy denominator.
- Weak-terminal noise must use disclosed scales and never vanish because negative sequence vanishes.
- Failed oracle cases, refused windows and all source/fault/mode strata must remain in their denominators.

### Task 1: General phase nodal source/fault oracle

**Files:** Create `tests/source_fault_oracle.py`, `tests/test_source_fault_oracle.py`.
**Interfaces:** `source_pair(profile='baseline') -> list[dict]` with `z` 3x3 complex and `emf` 3-vector; `solve(sections, fault_km, fault='AG', resistance=4, *, sources=None, reverse_sources=False) -> dict` with terminal/node voltages/currents, physical fault currents, common fault-node voltage and KCL residual. `sequence(phases, order) -> complex` for order 0/1/2.

- [ ] Write oracle tests checking all 11 contact circuits, source laws, internal-node KCL, reversal, balanced controls, old SLG limit and invalid input rejection.
- [ ] Run `python -m pytest tests/test_source_fault_oracle.py -q -x`; expected missing oracle RED.
- [ ] Implement explicit nodal branch/source/fault stamps with no locator imports and passive source profiles.
- [ ] Run focused tests and `python -m pytest -q`; expected all pass, only corpus skips/upstream warning.
- [ ] Commit and record observed RED/GREEN in the plan ledger.

### Task 2: Reproducible envelope and guarded actual-DSP cases

**Files:** Create `scripts/source_fault_validation.py`, `tests/source_fault_records.py`, `tests/test_source_fault_validation.py`, `tests/test_source_fault_integration.py`; add only new script architecture budget if needed. Minimal production fix only after a reproduced failure.
**Interfaces:** offline `run(seed=854) -> dict`, exclusive-output CLI `--output PATH`; consumes Task 1 oracle and existing `section_window`, never uses truth for candidate selection. Records helper `records(sections, km, fault, resistance, profile, rotation) -> dict[S/R,Record]` emits steady sinusoidal states for real DSP. Runner reports all planned/refused/location counts and complete stratum breakdowns, measured strength screens, balanced controls and witnesses.

- [ ] Write accounting tests for exactly 19,008 windows/6,336 per noise scenario, all ideal located unbalanced errors <1e-6 km, balanced-control separation, weak/source-asymmetry coverage, nonzero noisy errors, strict JSON and exclusive output.
- [ ] Write actual-DSP tests for LL/DLG/SLG with unequal/asymmetric sources and balanced refusal without phasor substitution; run focused RED before implementation.
- [ ] Implement runner/record helper, investigate any numerical failure systematically, preserve all failures/refusals rather than filtering by error/truth.
- [ ] Run focused tests/full suite; generate aggregate JSON, source hashes and scenario/stratum summaries; commit.

### Task 3: Review, evidence and delivery

**Files:** Create `project-docs/SOURCE_FAULT_VALIDATION_2026-10-23.md`, JSON under `project-docs/validation/`; update README, matrix, NEXT_SESSION and STATUS_LEDGER.
**Interfaces:** consumes Task 2 reproducible results; records strengths/limits, detailed denominators, source/fault resistance conventions and pending work.

- [ ] Document observed results, guarded versus raw outcomes and all limitations without expanding operational support claims.
- [ ] Run architecture direct/self-test, focused Ruff, Stage-A10,000 and validate all new hashes plus unchanged historical artifacts.
- [ ] Commit reviewable branch, create review package and obtain one fresh reviewer; reproduce/fix Important/Critical findings in one RED/GREEN pass, final full suite after fixes.
- [ ] Fast-forward main, verify primary full tests, commit/push results and remote HEAD; preserve QA/ledger, verify unchanged Dash hashes, archive managed worktree.
