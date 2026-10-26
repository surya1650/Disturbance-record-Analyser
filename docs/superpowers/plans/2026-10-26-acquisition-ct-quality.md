# Acquisition and CT Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Independently test a noise-aware quality candidate without weakening existing refusals on unproven evidence.

**Architecture:** A test-only secondary CT oracle is independent of production synthesis. An offline candidate and runner publish disjoint development/holdout evidence. Production gates remain authoritative unless the stated adoption criterion passes and a separate integration is justified.

**Tech Stack:** Existing Python, NumPy, pytest; no new dependencies.

**Spec:** docs/superpowers/specs/2026-10-26-acquisition-ct-quality.md

## Global Constraints
- No new field data or Dash changes; no operational model enablement.
- Fixed candidate budgets: residual 2%, harmonics 3%, peak residual 8% of fundamental RMS.
- At least four cycles and 16 samples per cycle.
- Do not tune on holdout; harmful CT error threshold >5%.
- Full suites run serially; historical source manifests remain frozen.

## Review Focus
- Initial flux bias must not be described as a hysteretic remanence model.
- A candidate pass must never authorize production location.
- Harmful CT misses and per-case exceptions must remain visible in denominators.
- Weak or absent fundamental must not produce an optimistic pass.
- Output publication must not overwrite prior evidence or serialize nonfinite values.

### Task 1: Independent CT oracle
**Files:** Create tests/ct_quality_oracle.py and tests/test_ct_quality_oracle.py.
**Interfaces:** simulate(primary, fs, *, burden, initial_flux=0, substeps=16) returns secondary current, flux and excitation arrays. Parameters use secondary-referred A, ohm, V s, H. No production DSP or generator imports.
- [ ] Write analytic linear-response, balance, trapezoidal volt-second, symmetry, convergence, knee crossing and invalid-input tests.
- [ ] Run pytest tests/test_ct_quality_oracle.py -q; expect missing-module failure.
- [ ] Implement continuous excitation and exact piecewise implicit trapezoidal inversion.
- [ ] Run the tests; expect all pass. Commit the independently testable oracle.

### Task 2: Frozen candidate and complete experiment
**Files:** Create scripts/acquisition_quality_candidate.py, scripts/acquisition_ct_validation.py, tests/test_acquisition_ct_validation.py. Modify scripts/architecture_budgets.json for new scripts only.
**Interfaces:** assess(samples, fs, freq) returns JSON-safe candidate diagnostics; run() returns complete per-case experiment with disjoint strata, fixed policy, truth metrics and source hashes; main() returns exit 2 on numerical failure, exclusive output publication.
- [ ] Write tests for clean/noisy controls, unsupported/weak/nonfinite data, harmonic/clip/dropout rejection, complete failure accounting and exclusive publication; run them RED.
- [ ] Implement the frozen candidate and independent grid from the spec. Score current legacy detector alongside candidate; never clear its output.
- [ ] Run focused tests GREEN and actual experiment. Freeze full evidence including misses and failure counts.
- [ ] Run architecture and Ruff. Commit code and evidence.

### Task 3: Review and delivery
**Files:** Create project-docs/ACQUISITION_CT_VALIDATION_2026-10-26.md; update project-docs/NEXT_SESSION.md.
**Interfaces:** Task 2 evidence determines adoption decision and remaining work.
- [ ] Report actual strata, unsafe passes and production limitations; record adoption decision against fixed criterion.
- [ ] Run full suite serially; expect no failures. Obtain one independent whole-branch review and fix Important issues with RED/GREEN evidence.
- [ ] Integrate authorized changes into main, run primary full suite, verify remote push and preserve local QA before native worktree archival.
