# Three-phase Full-record Acquisition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Validate the frozen noise-aware screen through six-channel acquisition and actual main/reviewed-stage location, retaining unsafe passes and failures.

**Architecture:** Test-only independent phase-network/CT signals pass through explicit secondary ADC encoding and public parsing. An offline record wrapper applies the frozen shape screen with explicit A/V units; a runner retains independent truth and real workflow results. No production gate override.

**Tech Stack:** Existing Python, NumPy, pytest; no new dependencies.

**Spec:** docs/superpowers/specs/2026-10-26-three-phase-acquisition.md

## Global Constraints
- No production code or frozen candidate/oracle/historical evidence is modified.
- No new field data, Dash changes, operational enablement, or clock promotion.
- Fixed residual 2%, harmonic 3%, peak residual 8%, four cycles and 16 samples/cycle.
- Numerical A/V fundamental floor 1e-9; relative prominence 1e-5.
- Complete 552-incident/1104-workflow grid; never tune on validation.
- Full suites run serially; strict finite JSON and exclusive output publication.

## Review Focus
- Primary/secondary and ADC scales must round-trip without double application.
- Shape-only gain/polarity/fundamental-alias counterexamples must stay visible.
- Balanced and weak-current truth must not divide by tiny I2 or imply calibration.
- A failed numerical terminal/incident must retain both workflow denominators.
- Known research windows and metadata clock skew must not imply field pairing or E4.

### Task 1: Independent full-record signal and acquisition chain
**Files:** Create tests/full_record_signals.py, tests/full_record_acquisition.py, tests/test_full_record_acquisition.py.
**Interfaces:** signals(split, profile, fault, scenario) returns end-keyed secondary waveform dictionaries plus ideal/CT-only arrays, true frequency/rate/window and ADC encoding facts. records(directory, *, split, profile, fault, scenario) returns (publicly parsed end-keyed Records, truth). Constants expose supported splits/profiles/scenarios.
- [x] Write tests for ideal secondary/primary ADC round trip, six channels, digital chronology, CT current balance provenance, noise determinism, gap/clock/rate cases, clipping rails, alias identity and configuration rejection.
- [x] Run pytest tests/test_full_record_acquisition.py -q; expect missing-module failure.
- [x] Implement source-phase signals, independent CT-before-noise/ADC, integer ASCII acquisition and normal public parsing; preserve truth separately.
- [x] Run the focused test command; expect all pass, then commit and task-done.

### Task 2: Record-level diagnostics and complete numerical runner
**Files:** Create scripts/full_record_quality.py, scripts/full_record_validation.py, tests/test_full_record_validation.py. Modify scripts/architecture_budgets.json for new scripts only.
**Interfaces:** record_quality(rec, freq, bounds) returns JSON-safe six-channel research diagnostics with authorizes_location=false. run() returns complete incidents with truth errors, candidate quality, real main/stage results, strata, adoption decision and source hashes. main() exclusively publishes output and exits 2 for numerical failures.
- [x] Write tests for six-channel shape and acquisition gates, weak/short/nonfinite input, explicit voltage units, truthful gain/polarity counterexamples, independent error floors, tiny complete grid, injected exceptions/nonfinite output, CLI failure/race and existing output preservation.
- [x] Run pytest tests/test_full_record_validation.py -q; expect missing-module failure.
- [x] Implement the frozen wrapper, independent quadrature metrics and both unchanged actual workflows. Retain every planned outcome; no truth-based quality override.
- [x] Run both new focused suites; expect all pass. Architecture and new-file Ruff must pass. Commit protocol/code before the full validation grid, then run it to a new tracked evidence path.
- [x] Verify finite JSON, denominators, hashes and actual unsafe passes. Commit evidence; task-done with both focused suites.

### Task 3: Evidence, independent review and delivery
**Files:** Create project-docs/THREE_PHASE_ACQUISITION_VALIDATION_2026-10-26.md; update project-docs/NEXT_SESSION.md.
**Interfaces:** Task 2 scientific results determine the documented adoption decision and pending work.
- [ ] Report actual split/scenario/weak/balanced outcomes, harmful passes, location errors and limits; do not reinterpret scientific failure as numerical failure.
- [ ] Run the full worktree suite serially; expect no failures. Obtain one fresh whole-branch review, fix Important findings in one TDD pass, preserve frozen evidence if correction changes source binding.
- [ ] Integrate under existing main/push authorization; run the serial primary full suite, verify remote push, preserve QA/review/ledger, archive the managed worktree and remove the merged branch.
