# Inspection Timebase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Keep invalid acquisition inspectable even with extreme nominal frequency.

**Architecture:** Replace untrusted frequency-derived display fallback with fixed1000Hz; retain blocking and fitted-period behavior.

**Tech Stack:** Existing Python/NumPy/pytest.

**Spec:** docs/superpowers/specs/2026-10-27-inspection-timebase.md

## Global Constraints
- Fixed1000Hz inspection only; invalid status, TIME-DAT block, no clock promotion.
- Valid declared/recovered grids and untrusted finite fitted periods unchanged.
- Preserve historical evidence, Dash and inputs; no field data.
- Full suites serially; one fresh review and one TDD Important-fix pass.

## Review Focus
- Extreme positive nominal frequency must not produce infinite rate or flat time.
- Tiny nominal frequency must not overflow the display grid.
- Nonfinite/negative metadata must remain blocked despite a finite placeholder.
- Fitted invalid DAT timing must retain its existing inspection period.
- Ordinary valid acquisition must not be redirected through the placeholder.

### Task 1: Finite invalid-timing fallback
**Files:** Modify src/dranalyser/comtrade/timestamps.py; create tests/test_inspection_timebase.py.
**Interfaces:** recover_time(cfg,stamps,n) tuple unchanged; only invalid(reason) without fitted display_period uses1000Hz and inspection provenance.
- [x] Write direct and public-parser parameterized tests for1e308,1e-320,1e-308,nan,inf,-50,0,50. Expect old overflow/non-increasing failures.
- [x] Replace nominal-frequency multiplication with fixed1000Hz and update basis label.
- [x] Run pytest tests/test_inspection_timebase.py tests/test_timestamp_recovery.py -q GREEN; architecture/focused Ruff. Commit/task-done.

### Task 2: Review and delivery
**Files:** Create project-docs/INSPECTION_TIMEBASE_FIX_2026-10-27.md; prepend latest handover to project-docs/NEXT_SESSION.md.
**Interfaces:** All existing timestamp/clock and full regression tests must remain green.
- [x] Run full suite serially and one fresh whole-branch read-only review. Fix Important findings once RED/GREEN/full suite; defer Minors.
- [x] Integrate with reviewed DSP milestone without losing its handover/evidence, run primary full suite, push/verify remote, preserve QA/ledger and archive managed worktree. Keep five-hour continuation active for remaining validation policy work.
