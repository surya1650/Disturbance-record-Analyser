# Numerical Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Strengthen structural E5 refusal and independently measure scalar and mixed-section numerical behavior.

**Architecture:** Pure estimator corrections retain Estimate diagnostics. Independent numerical consumers live under validation; no production location path imports validation. Tests and generated sweeps use synthetic inputs only.

**Tech Stack:** Python >=3.10, NumPy, existing pytest/Ruff.

**Spec:** docs/superpowers/specs/2026-10-23-numerical-validation-design.md

## Global Constraints

- Python >=3.10; existing NumPy/SciPy only; no new runtime dependency.
- No ML in location, travelling waves, GPS requirement for E5, or field values.
- Preserve source records, active app roots, Dash files and historical reports.
- Main/stage mixed-section, coupling, charging and source-review gates remain.
- No calibrated confidence, field accuracy or TB certification claim.

## Review Focus

- Very large/small coefficients must not overflow or turn absent real roots into usable distances (Task 1).
- Missing root support at only one sample must not be silently discarded (Task 1).
- Undefined phase at zero fault voltage must not produce an ok estimate or fallback distance (Task 1).
- Sweep refusals must remain in planned denominators; seeds and parameter bias must be reproducible (Task 2).
- Junction duplicates, reversed sections and no valid candidate must not be silently selected in a section study (Task 3).

### Task 1: Structural E5 numerical contract

**Files:** Modify src/dranalyser/faultloc/estimators.py and ensemble.py; create tests/test_numerical_robustness.py; modify budgets deliberately.

**Interfaces:** Consumes stable_quadratic(a,b,c), e5_roots and e5_unsynchronised; preserves their signatures. Produces finite real root lists or an empty list plus reason, and failed Estimate diagnostics `inconsistent_window`/`undefined_angle` as applicable. Ensemble consumes those flags alongside existing ambiguity/insufficient-window flags.

- [x] Write coefficient-scale, no-real-root, partial-invalid-window and zero-fault-voltage refusal tests; independently specified roots and counterexamples.
- [x] Run focused tests; observe RED for the intended numerical/structural behavior.
- [x] Normalize coefficient arithmetic and explicitly reject structurally invalid E5 windows; preserve aligned-E4 escape only when usable.
- [x] Run focused and full suite; record failures/refusals and update architecture budget for changed files.
- [x] Commit with message `Fix structural E5 root and window failures` and ledger the result.

### Task 2: Reproducible independent scalar envelope

**Files:** Create src/dranalyser/validation/sequence_envelope.py, scripts/numerical_envelope.py and tests/test_sequence_envelope.py.

**Interfaces:** `sequence_case(m, source_ratio, rotation)` returns terminal quantities and true m from independent branch Ohm laws. `run_envelope(seed=854, repetitions=20)` returns a finite JSON-compatible dict with all-case and per-scenario counts, error tails, refusals, interval containment and explicit limits. Script writes a new output via exclusive creation, never overwrites prior output.

- [x] Write failing oracle-law, deterministic envelope/accounting and exclusive-output tests; hand-derived midpoint and parameter-bias expectations.
- [x] Run focused tests; observe RED because the interfaces do not yet exist.
- [x] Implement independent branches and deterministic zero/noise/weak-infeed/parameter-bias groups, retaining rejected cases and using no estimator to generate expected quantities.
- [x] Run focused tests, full suite and real sweep. Do not require noisy groups to meet a clean-data target; report actual behavior.
- [x] Commit with message `Add independent scalar numerical envelope` and ledger results.

### Task 3: Bounded mixed-section feasibility study and handoff

**Files:** Create src/dranalyser/validation/section_study.py and tests/test_section_study.py; update project-docs/TB854_VALIDATION_MATRIX.md, NEXT_SESSION.md, STATUS_LEDGER.md and a new numerical validation report.

**Interfaces:** `aligned_section_candidates(line, vs, is_, vr, ir)` returns all eligible section-local positions with mismatch diagnostics and a unique/ambiguous/withheld status. Consumes negative-sequence phasors with a supplied common reference; never called by production main/stage paths.

- [x] Write failing tests against independent phase nodal network: junctions, AG/BG/CG, physical reversal, resistance, uniform limit, unsupported/invalid model and ambiguity/no-candidate behavior.
- [x] Run tests; observe RED because the study interface is absent.
- [x] Implement piecewise healthy-section voltage propagation and bounded candidate evaluation; deduplicate only the same physical junction and retain all distinct candidates.
- [x] Verify focused/full tests, architecture/Ruff and Stage-A 10,000. Document exact envelopes, tails, limits and remaining model gaps.
- [x] Commit with message `Validate aligned mixed-section feasibility and document limits`; dispatch one whole-branch review, fix important findings RED→GREEN and rerun full suite.
- [ ] Integrate/publish as authorized, verify Git remote and preserve Dash findings locally.
