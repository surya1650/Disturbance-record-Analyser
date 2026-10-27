# Conditional E5 Error Sets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Independently validate offline necessary distance sets under explicit error caps.
**Architecture:** Pure guarded section subdivision; separate direct circuit and phase nodal oracles; immutable experiment publication.
**Tech Stack:** Existing Python, NumPy, pytest; no new dependencies.
**Spec:** docs/superpowers/specs/2026-10-27-e5-error-sets.md

## Global Constraints
- Offline only; authorizes_location=false; no production integration/default/gate change.
- Exact passive series Z2=Z1 assumption; both currents into line; caller caps/provenance explicit.
- At most256 supports,64 sections,200000 boxes; resolution in[1e-6,1].
- Guard256*machine_epsilon*(number_sections+1); retain unresolved resource boxes.
- Pre-frozen556 cases; no tuning, unknown evidence promotion or discarded failures.
- Dash/captures/workbook/DB/previews untouched; serial full suites.
- One fresh whole-branch review and one TDD Important-fix pass; defer Minors.

## Review Focus
- Lost pending regions on resource exhaustion must never exclude physical truth.
- Section-angle changes require conservative current-circle propagation.
- Joint support intersection is only a necessary set, not a shared-phase solution.
- Tiny/huge or bool/nonfinite inputs must never masquerade as empty physical sets.
- Deliberately invalid caps must stay in denominators and outside coverage claims.

### Task 1: Pure necessary-set research utility
**Files:** Create src/dranalyser/faultloc/error_sets.py, tests/test_error_sets.py; exact new architecture budget.
**Interfaces:** Dataclasses and e5_error_feasible() as spec; finite JSON, no location.
- [ ] Write analytic/refusal/resource/extreme/scale/section-angle tests; run focused RED (missing module).
- [ ] Implement normalized conservative drops and Lipschitz subdivision; run focused GREEN, architecture and changed-file Ruff. Expected all pass.
- [ ] Commit; task-done reruns pytest tests/test_error_sets.py -q. Expected all pass.

### Task 2: Frozen disjoint independent experiment
**Files:** Create tests/error_set_oracle.py, scripts/e5_error_validation.py, tests/test_e5_error_validation.py, tracked validation JSON.
**Interfaces:** oracle case_grid()/make_case() contain all556 rows; runner run() retains exceptions as failed rows, source hashes and frozen Git revision. main() exclusive finite JSON publication, exit2 on failure.
- [ ] Write oracle/sign/bounded perturbation, real tiny runner, failed-row denominator and publication tests; focused RED missing module/runner.
- [ ] Implement independent oracle and runner, GREEN tests, architecture/Ruff; commit protocol before full experiment. No full_record_signals dependency is used; if reused include it in manifest.
- [ ] Run all556 once, preserve every row; assert zero within-cap omissions, record wide/ambiguous/resource/violated-cap outcomes honestly. Expected numerical coverage, not field adoption.
- [ ] Commit evidence; task-done reruns focused suites. Expected all pass.

### Task 3: Review and deliver
**Files:** project-docs/E5_ERROR_SETS_2026-10-27.md and project-docs/NEXT_SESSION.md.
**Interfaces:** Published conditional results/limitations and next supported work, no location authority.
- [ ] Run full serial suite and production/Dash/historical-manifest checks; expected unchanged production and full pass (28 missing-corpus skips in worktree).
- [ ] Fresh whole-branch review; single Important TDD pass if needed; retain historical evidence and new corrected binding separately. Expected no unresolved Important issues.
- [ ] Integrate, primary serial suite, commit/push and verify remote HEAD; preserve QA/ledger hash-verified before native archive. Expected clean primary and recoverable archived worktree.
