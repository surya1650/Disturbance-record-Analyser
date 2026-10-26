# Fractional-window DSP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct physical fundamental conjugate leakage and keep conditional noise bounds matched to the operator.

**Architecture:** Pure real-basis sliding fit replaces scalar orthogonality assumptions. Independent matrix oracles and parsed metrology validate the corrected operator; all old evidence stays historical.

**Tech Stack:** Existing Python/NumPy/pytest, no new dependencies.

**Spec:** docs/superpowers/specs/2026-10-27-fractional-dsp.md

**Adoption amendment:** The corrected-default trial produced new harmful outputs
on corrupted inputs. Retain it historically; final code must keep legacy default
and expose method='basis' only explicitly for research. Matching radius uses the
same method. Freeze and run fresh HELD metrology evidence, default full suite and
default Stage-A. Ledger contains the adoption ruling and observed RED regressions.

## Global Constraints
- Absolute-origin RMS, existing rounded full/half supports and mimic FIR contract.
- Relative determinant guard64eps; singular supports NaN, no plausible estimate.
- Bound utility2..100000 samples, explicit verified-uniform-grid and supplied caps.
- No gate relaxation, location authority, field/clock/CT/alias certification.
- Preserve original evidence, Dash, inputs and DB; full suites serially.
- New80-record disjoint grid fixed in spec; .01A ideal physical-bias ceiling.
- Stage-A10000 and full regression required; one fresh review/one TDD fix pass.

## Review Focus
- A mimic startup sample differs from a steady FIR boundary; both must fit exact signals.
- Half supports and absolute origins must not rotate or rescale phasors.
- Singular or extreme grids must refuse finite-looking phasors/bounds.
- L1 raw coefficients must include the prior sample, not just filtered support.
- Physical reference bias and violated cap assumptions must not disappear from denominators.

### Task 1: Exact fundamental fit and matched conditional kernel
**Files:** Create src/dranalyser/dsp/fundamental.py and tests/test_fractional_dsp.py; modify dsp/core.py, dsp/sequence_budget.py, tests/test_sequence_budget.py and architecture budgets.
**Interfaces:** sliding_dft public signature unchanged; new pure sliding_fundamental(x,t,fs,freq,n,decay) returns complex stream; filter_samples(x,decay) preserves initialization; kernel_l1(fs,freq,n,decay) returns finite radius factor or raises ValueError for unsupported rank. Existing i2_budget unchanged.
- [ ] Add analytic physical-phasor and independent matrix-oracle tests covering spec cases. Run pytest tests/test_fractional_dsp.py -q: expect fractional/startup failures on old core.
- [ ] Implement two-basis sliding Gram fit and raw-input kernel factor; replace legacy direct-kernel test oracle with independent pinv/FIR matrix. Add resource/rank bound refusals.
- [ ] Run pytest tests/test_fractional_dsp.py tests/test_sequence_budget.py -q: expect all pass; architecture and changed-file Ruff pass. Commit/task-done with same focused suite.

### Task 2: Disjoint parsed physical and perturbation validation
**Files:** Create scripts/fractional_dsp_validation.py, tests/test_fractional_dsp_validation.py and tracked evidence; reuse tests/sequence_budget_records.py in an isolated module namespace with explicit split configuration without editing its frozen defaults.
**Interfaces:** run() yields original summary fields plus physical-bias adoption gate and new-grid provenance/source hashes; CLI exclusive finite JSON and exit2 on failed gate. Reuse existing evaluate() with matched physical truth and caller caps.
- [ ] Test two-record real-parser smoke, failure accounting, masks/physical gate, finite/existing/racing publication RED; expect missing module.
- [ ] Implement immutable new grid and isolated generator namespace with separate split values; historical source globals remain unchanged even on error. Gate requires80 evaluated/0failed/0within-cap misses and .01A bias maximum, never production location authority.
- [ ] Run focused tests and architecture/Ruff GREEN. Commit protocol before full80 new-grid run and historical80 replay to new files; verify counts, hashes and scope. Commit evidence/task-done.

### Task 3: Adoption evidence, independent review and integration
**Files:** Create project-docs/FRACTIONAL_DSP_VALIDATION_2026-10-27.md; update project-docs/NEXT_SESSION.md and plan/ledger.
**Interfaces:** Task1 operator and Task2 evidence must pass unchanged Stage-A/full regression criteria before shipping.
- [ ] Run serial full pytest and fresh Stage-A10000 (workers2); record results without threshold changes. Report physical correction and all limitations.
- [ ] Generate whole-branch review package; dispatch one fresh reviewer, resolve Important findings once with RED/GREEN and full suite; defer Minors.
- [ ] Integrate/push under standing authorization, primary full-suite check and remote HEAD verification; preserve ignored QA/ledger, archive native worktree. Continue remaining software tasks, including malformed-frequency inspection fallback.
