# Conditional Source Quantities and Supplied Line Inputs

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline. Continue the user's approved autonomous execution without design/integration questions.

**Goal:** Show conditional sequence/R-X quantities and an approximate line-model projection when the user supplies the requisite channel and line assumptions; keep every other supported observation/report available.

**Architecture:** Add small pure composition helpers over the already reviewed source-window phasors, consumed only through workbench adapters. Preserve the numerical fitting profile and operational gates. Bind all user choices, supplied line bytes and derived quantities to the same job/snapshot identity. No new framework or production dependency.

**Tech Stack:** Existing Python/NumPy, FastAPI, vanillaJS, pytest/Node/browser QA.

**Spec:** project-docs/INTEGRATED_DR_APPLICATION_HANDOFF_2026-10-27.md, INTEGRATED_DR_GOAL_BOARD.md, and latest user request for simple analysis after channel assignment, two-side comparison, possibleARfailure/trip, approximate location, CTdefaults and selectable phase colours.

## Global Constraints

- Protected captures, Downloads sources, workbook, Dash, realDB/revisions and8091/8113/8092 remain untouched. Disposable8094 only.
- No source-model/CTdefault/line-assumption success grants physical, common-clock, field, alias or operational location authority.
- User-selected phase meanings and asserted digital0/1state are assumptions with provenance. Missing/nonfinite data or incompatible units stay unknown; do not substitute zeros.
- Reuse existing reviewed source fits; do not rerun/tune152study or relax lower-density/short-support policy.
- Approximate projection requires explicit supplied line length/positive-sequence reactance and chosen phase-phase loop. Ground-loop compensation stays unavailable without its own supplied convention. Never infer line/ends/faultloop from a waveform.
- Serial release/primary verification; one fresh whole-branch review/single Important-fix TDD pass for this milestone.

## Review Focus

- Duplicate/ignored phase meanings, mismatched fit centres/supports and near-cancelled loop currents cannot form invented R-X/sequence quantities.
- Assumed current scaling must preserve underflow/missing values and never overwrite valid source ratios.
- Asserted-state choices and CFG normal-state observations are distinct; automatic suggestions cannot become verified trip/AR causes.
- Line selection/custom inputs changing during queued work must invalidate derived quantities, snapshots and overlays together.
- Negative/outside-line or ill-conditioned projections remain explicit; no clipping into a plausible kilometre or fake certainty.

## Task 1: Pure conditional quantities and line-model projection

**Files:** create workbench/source_quantities.py (or focused pure helper), tests/test_source_quantities.py; extend source_diagnostics.py options/composition.
**Interfaces:** compose_source_quantities(channels,windows,line_model=None,fault_loop='') returns per-window sequence/phase-loop results, prerequisite reasons, and an explicit approximate projection object with method/residual/assumptions/status; all authority flags false.
- [ ] Write RED tests with hand-derived balanced/unbalanced complex RMS phasors, known phase-phase impedance and line projection; missing phases, duplicate/ignored meanings, raw-count/mismatched units, withheld fits, centre mismatch, cancellation, zero/nonfinite/reactance/length invalid, and out-of-line values. No fitter-generated expectations.
- [ ] Implement Fortescue components on corresponding declared/assumedV/A phasors; phase-phaseZ=(Vx−Vy)/(Ix−Iy) with a scale-aware nonzero-current prerequisite; preserve fit provenance and units. Per-window failure does not erase other quantities.
- [ ] Return an explicit model projection from Imag(Zloop)/X1_per_km only for the selected phase-phase loop and supplied valid line; include fraction, distance, assumptions, basis and numerical consistency diagnostics. Do not call it a verified fault or unlock operational gates.
- [ ] Add regression for assumed CT intermediate underflow; retain raw source observations if conversion cannot be represented. Run focusedGREEN and commit.

## Task 2: Explicit supplied line facts and digital assertion choices

**Files:** extend source_snapshot.py (split line facts helper if needed), source_diagnostics.py, source_events.py, application/inspection.py and source_jobs.py; tests/test_source_inputs.py.
**Interfaces:** normalised options include optional line_id/custom declared model, explicit fault_loop and per-digital asserted_state0/1. Configured registry selection uses only server-known contained files; hash and parameter status retained. Missing source ratio fallback policy remains132600/1,220800/1 with no default length/constants.
- [ ] Write RED tests for registry containment/duplicateIDs/changed bytes, explicit custom model values and absent constants, pending/completed option invalidation, inherited Ignore precedence, active-low observations with unknown gaps and normal-state metadata not granting assertion authority.
- [ ] Implement bounded supplied-line lookup/custom inputs and job/snapshot binding. Keep frozen operational result separate from an assumption-dependent independent projection.
- [ ] Stream bounded digital evidence using explicit asserted-state choices; default high-state interpretation is labelled as an assumption. AR/trip explanations carry channel/polarity provenance and observed sample brackets.
- [ ] Run focusedGREEN/architecture/Ruff and commit.

## Task 3: Main-app prerequisite controls and useful derived report

**Files:** inspection-analysis.js, inspection-report.js, inspection-model.js/index/style as needed; Node tests and actual browser QA.
**Interfaces:** existing source-analysis panel adds accept-suggested-meanings, supplied-line/fault-loop and asserted-state controls; snapshots/windows show conditional sequence/R-X/projection with explicit assumptions. Diagram overlays only the eligible labelled projection, retaining Not available for missing fields.
- [ ] Write RED model/template tests for options, unavailable reasons, phase colours and conditional projection labels; no raw-count impedance or implicit line/clock/faultloop.
- [ ] Implement controls and single-source identity/generation flow; changing any choice clears the old result. Add window/source links, observed trip/AR evidence and conditional quantities to the existing export/print model.
- [ ] Actual browser checks: assigned supported synthetic phase signals yield expected conditional R-X/sequence; supplied custom line/chosenloop yields known model distance; missingline leaveskmNotavailable; changing line/state/meanings replaces report. Replay real source copies without source-byte changes.
- [ ] Serial full release, one fresh review/single TDD Important-fix pass, primary verification, commit/push and update G1-G6 board. Wider decoder recovery/large-record qualification is the following bounded milestone.
