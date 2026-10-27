# Scalar Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Independently evaluate a conservative scalar saturation/weakI2 screen without changing production behavior.

**Architecture:** Pure candidate assesses actual TerminalInput streams; a separately frozen uniform-network parsed-record matrix measures suppression and observability counterexamples alongside unchanged scalar location.

**Tech Stack:** Existing Python/NumPy/pytest.

**Spec:** docs/superpowers/specs/2026-10-27-scalar-observability.md

## Global Constraints
- Candidate offline, no production consumer or location authority; legacy DSP/defaults unchanged.
- ExactlyS/R, known unbalanced faults; usable complete finite full-window support.
- Reject saturation/clipping/blocked acquisition and invalid polarity/grid/streams.
- Existing section I2 floor1% medianI1 /1e-6 primary A; every support checked.
- Fixed616 disjoint incidents from spec; numerical failures and bad passes count.
- No holdout tuning, new field data, clock promotion, input/Dash/DB changes.
- Serial full suites; one fresh whole-branch review, one TDD Important-fix pass.

## Review Focus
- A weak/nonfinite observation between downsampled picks must not disappear.
- Recovered local timing must not imply cross-terminal alignment.
- Missing or malformed acquisition/polarity/stream metadata must withhold.
- Coherent gain/polarity/alias passes must remain visible as counterexamples.
- No scalar fallback/location can be manufactured by the candidate overlay.

### Task 1: Pure conservative candidate
**Files:** Create src/dranalyser/faultloc/scalar_quality.py and tests/test_scalar_quality.py; add its exact architecture budget.
**Interfaces:** scalar_observability(terminals,*,fault) returns finite JSON status/reasons/terminals/policy/authorizes_location=false. Uses actual TerminalInput analyses and complete selected local windows, no source truth.
- [ ] Write actual-DSP clean tests and manipulated boundary cases for every spec refusal; isolated weak/nonfinite support, exact floor and malformed inputs. Run focused RED, expect missing module.
- [ ] Implement pure necessary-condition screen with all finite/length/grid/polarity/rank guards, diagnostics and unchanged section floor.
- [ ] Run pytest tests/test_scalar_quality.py -q GREEN; architecture/focused Ruff; commit/task-done.

### Task 2: Independent disjoint full-record matrix
**Files:** Create tests/scalar_observability_records.py, scripts/scalar_observability_validation.py, tests/test_scalar_observability_validation.py and tracked evidence; add new script budget.
**Interfaces:** records(directory,*,split,profile,fault,scenario) returns parsed pair and independent truth. run() retains616 planned cases, measured candidate, baseline/overlay scalar outcomes and source-bound finite report; main() exclusive publication/exit2 numerical failures.
- [ ] Test public integer ADC roundtrip, source isolation, CT/coherent truth separation, tiny real pipeline, failed-row accounting, monotonic overlay, scientific gate and finite/existing/racing publication RED.
- [ ] Implement the frozen source waveforms using independent nodal/CT oracles and isolated existing writer; actual analyse/locate with measured consensus; separate truth metrics and all gate reasons.
- [ ] Run both focused suites GREEN plus architecture/Ruff; commit code/protocol before full616 run. Verify all denominators/hash bindings and commit evidence/task-done.

### Task 3: Review, interpretation and delivery
**Files:** Create project-docs/SCALAR_OBSERVABILITY_VALIDATION_2026-10-27.md; prepend current state to project-docs/NEXT_SESSION.md.
**Interfaces:** Report all harmful passes/failures and held adoption honestly; cannot promote candidate or research DSP from these observations alone.
- [ ] Run serial full regression, confirm existing production consumer sources unchanged, verify historical manifests and Dash; record actual outcomes and exclusions.
- [ ] One fresh whole-branch review; handle Important issues once with RED/GREEN/full suite, defer Minors; preserve old evidence and regenerate corrected bindings if needed.
- [ ] Integrate/push under standing authorization; primary full suite, remote HEAD and clean tree verification. Preserve QA/ledger before native archival; precise next-work handover and heartbeat update.
