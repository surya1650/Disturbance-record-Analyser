# Conditional Sequence Error Budget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Supply and independently validate conditional additive-error bounds for the DSP kernel and I2, with explicit provenance and no location authorization.

**Architecture:** A small pure DSP utility propagates supplied deterministic errors. Independent direct-kernel tests and new parsed metrology records validate the assumptions and show coherent-bias counterexamples. Existing gates and historical studies remain unchanged.

**Tech Stack:** Existing Python/NumPy/pytest; no dependencies added.

**Spec:** docs/superpowers/specs/2026-10-26-sequence-error-budget.md

## Global Constraints
- All returns have authorizes_location=false; missing bounds/provenance refuse.
- No automatic gain, polarity, alias, clock, CT or field-error guarantee.
- Conditional I2 floor1% /1e-6 primary A and relative limit5%; numeric guard64 ulps.
- Fixed80-record matrix:56 within supplied caps,24 underclaimed coherent controls.
- Strict finite JSON/exclusive output; preserve historical sources/artifacts and Dash.
- Full suites run serially; one fresh review and one TDD Important-fix pass.

## Review Focus
- Zero or missing radius must not silently mean that unknown field noise is zero.
- Mimic boundary samples and half-cycle normalization must be included.
- A balanced/weak I2 must not receive a finite optimistic relative bound.
- Violated sample-cap assumptions must stay outside validated-coverage counts.
- Matched-kernel perturbation bounds must not be called physical-fundamental accuracy or confidence.

### Task 1: Pure conditional DSP bounds
**Files:** Create src/dranalyser/dsp/sequence_budget.py and tests/test_sequence_budget.py; add only its line budget in scripts/architecture_budgets.json.
**Interfaces:** dft_noise_radius(fs,freq,sample_bound,*,tau=None,half_cycle=False,uniform_grid=False) returns a structured conditional operator radius. i2_budget(currents,error_radii,*,provenance='') returns structured I2 magnitude interval/error bound and conditional/withheld/unsupported status. Inputs/outputs are primary A, explicit ordering ABC, JSON-safe numbers.
- [ ] Write direct independent kernel-coefficient tests, exact adversarial triangle construction, weak/balanced/unknown tests, malformed/overflow cases and no-authority assertions.
- [ ] Run pytest tests/test_sequence_budget.py -q; expect missing module failures.
- [ ] Implement the two pure functions and finite guards exactly as the spec, preserving the existing operator/callers.
- [ ] Run focused tests, architecture and new-file Ruff; expect pass, then commit/task-done.

### Task 2: Independent parsed metrology matrix
**Files:** Create tests/sequence_budget_records.py, scripts/sequence_budget_validation.py and tests/test_sequence_budget_validation.py; add the new script line budget.
**Interfaces:** records(directory,*,split,i2,scenario) returns(parsed Record, ideal primary current arrays, declared per-phase sample caps, truth/provenance). run() returns80 cases with evaluated observation counts, bound misses, conditional/withheld counts, explicit assumption violations, hashes and no production adoption. main() exclusively publishes and exits2 on numerical failures/valid-assumption misses.
- [ ] Test primary/secondary/ADC roundtrip, bounded/underclaimed sample caps, tiny actual-DSP matrix, complete failure accounting, missing/weak bounds, and CLI finite/existing/racing publication RED.
- [ ] Implement independent source signals, integer public parsing and all actual DSP supports with matched ideal-kernel comparison; never infer a bound from truth residuals.
- [ ] Run both focused suites and architecture/Ruff GREEN. Commit code/protocol before running the full matrix to a new tracked evidence path.
- [ ] Verify all80 cases/observation denominators, finite values, masks and hashes; commit evidence and task-done.

### Task 3: Scientific interpretation, review and integration
**Files:** Create project-docs/SEQUENCE_ERROR_BUDGET_2026-10-26.md; update project-docs/NEXT_SESSION.md.
**Interfaces:** Task2 evidence determines whether the supplied-cap theorem is numerically supported; field/operational adoption is never implied.
- [ ] Publish coverage and counterexamples with explicit conditional scope, numeric tolerances and matched-kernel limitation.
- [ ] Run serial full suite; obtain one fresh whole-branch review and fix Important issues with RED/GREEN evidence, preserving frozen evidence revisions.
- [ ] Integrate, verify primary full suite and remote push, preserve QA/ledger and archive managed worktree. Continue further actionable work under the user's autonomy and five-hour heartbeat.
