# Dhone Source-Time Investigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline task-by-task.

**Goal:** Validate useful DAT-time inspection without bypassing uniform-DSP gates.
**Architecture:** New isolated pure diagnostic API; no production consumers; private source replay.
**Tech Stack:** Existing Python/NumPy/pytest.
**Spec:** docs/superpowers/specs/2026-10-27-dhone-source-time.md

## Global Constraints
- Source-time inspection only, nrates=0; no DSP/location/clock authority.
-3..200000 samples; explicit positive multiplier; exact finite consecutive numbers.
- No input edits, app DB/revision/process changes, gate/default/registry changes.
- Freeze108 independent synthetic cases; retain every failure and denominator.
- One fresh whole-branch review and one TDD Important-fix pass; defer Minors.

## Review Focus
- Declared timestamps are not calibrated time or proof of recorder identity.
- Gaps/initial/final digital states must retain unknown boundaries.
- Huge/underflow/coercive inputs withhold finite JSON.
- Constant sampling cannot be inferred from quantized interval runs alone.
- Existing blocked slow nonuniformity and invalid acquisition must stay blocked.

### Task 1: Pure source-time inspection
**Files:** src/dranalyser/comtrade/source_time.py; tests/test_source_time.py; exact architecture budget.
**Interfaces:** source_time_axis()/digital_source_intervals() per spec.
- [ ] Write analytic irregular digital edges, state boundaries, gaps, type/shape/extreme refusals RED; expected missing module.
- [ ] Implement minimal pure API; focused GREEN, architecture/Ruff; commit. Expected passes.
- [ ] task-done reruns pytest tests/test_source_time.py tests/test_timestamp_recovery.py -q; expected pass.

### Task 2: Independent validation and investigation report
**Files:** scripts/source_time_validation.py; tests/test_source_time_validation.py; project-docs/DHONE_TIMESTAMP_INVESTIGATION_2026-10-27.md; tracked synthetic evidence; private QA real replay.
**Interfaces:** frozen108-case run returns finite row-retaining evidence, exclusive publication, nonzero on failure.
- [ ] Tests RED for tiny real runner, failure denominator and publication; implement GREEN. Commit freeze before108 outcomes; preserve source/Git bindings.
- [ ] Run108 cases and private unchanged Dhone replay; expected exact source-time intervals and unchanged block. No field/model/calibration claims.
- [ ] Full serial suite, fresh whole-branch review/single Important pass; integrate/push under standing authorization; primary suite. Preserve QA/ledger, native archive, handover/automation. Expected no unresolved Important and unchanged protected state.
