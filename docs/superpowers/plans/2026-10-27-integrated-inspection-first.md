# Integrated Inspection First Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline, task by task. The user has already authorized autonomous execution and integration; do not ask another design or execution-method question.

**Goal:** Open a blocked or unassigned revision in the main application and inspect its recoverable analog/digital observations with live sample cursors.

**Architecture:** Add a revision-scoped, read-only workbench inspection adapter over the reviewed strict source loader. Expose bounded source inspection APIs independently of the operational result, and mount the workspace from the incident view before assignment. Keep operational analysis, stored revisions and estimator gates intact.

**Tech Stack:** Existing Python/NumPy/FastAPI and vanilla JavaScript; current pytest and Node browser-model tests. No framework migration.

**Spec:** project-docs/INTEGRATED_DR_APPLICATION_HANDOFF_2026-10-27.md. This is the first vertical slice of G1/G2, not a plan claiming to finish G3-G6.

## Global Constraints

- Original files and live DB/revisions/previews remain unchanged; use disposable roots for tests/demo.
- Missing samples/states remain unknown; invalid timing falls back to sample index without invented seconds.
- Inspection never grants end/primary assignment, physical scaling, clock quality, production DSP or location authority.
- Application imports workbench adapters, not DSP or COMTRADE internals.
- Preserve path containment, source hashes, duplicate channel identities, bounded responses and stale-response isolation.
- Full verification runs serially; record baseline counts as historical until freshly run.

## Review Focus

- A blocked needs_review revision with no result must open inspection without changing revision state (Task1/2).
- A malicious filename or changed DAT must not read outside the revision or silently reuse stale values (Task1).
- Missing analog/digital observations and bad timestamps must not turn into zero or fake UTC (Task1/3).
- Cursor movement during a record switch or failed interval request must not display old record values (Task3).
- Many channels/large intervals must page or explicitly refuse the request while retaining the rest of the workspace (Task1/3).

## Task 1: Revision-scoped source inspection adapter

**Files:** Create src/dranalyser/workbench/source_inspection.py and tests/test_source_inspection.py. Read workbench/samples.py and comtrade/source_observations.py first.

**Interfaces:** `inspection_record(root, revision, filename) -> dict` produces source metadata, stable channel IDs, sample count, time-basis status, bounded trace envelopes, issues and source hashes. `inspection_samples(root, revision, filename, channel_id, start_index, stop_index) -> dict` returns a half-open integer interval, at most20000 samples, exact indices, source coordinates if valid, nullable values/states and scaling labels. Channel identity includes source kind plus original ordinal; duplicate labels cannot alias. These are new proposed interfaces, not existing code.

- [ ] Write failing tests for no-result blocked revision inspection, analog/digital values, orphan CFG, missing/invalid observations, missing seconds with retained sample-index access, duplicate labels, bounds, path traversal/symlink containment and source hash mismatch. Use small synthetic CFG/DAT in tmp_path; never depend on private captures.
- [ ] Run tests and confirm the intended failures.
- [ ] Implement adapter using load_source on contained revision files with explicit paired DAT. Inspect current bundle schema and hash convention before binding identity. Preserve content_hash and per-file byte hashes without confusing their algorithms. No parsed primary Record or operational evidence is required.
- [ ] Keep source loader's current supported scope explicit. Where it cannot recover a format, show the reason; any extension gets its own failing test and deliberate contract. Do not silently remove its budgets.
- [ ] Run focused tests and commit the adapter.

## Task 2: Main application read-only inspection entry

**Files:** Modify src/dranalyser/application/api.py, static/app.js and static/index.html as needed; create static/inspection.js; extend tests/test_application.py.

**Interfaces:** GET `/api/incidents/{incident_id}/inspection?revision=N&record=NAME` calls inspection_record. GET `/api/incidents/{incident_id}/inspection/samples?revision=N&record=NAME&channel_id=ID&start_index=A&stop_index=B` calls inspection_samples. Use existing incident404/security conventions. Existing /navigator, /samples and /review contracts remain compatible.

- [ ] Write failing API tests proving needs_review inspection works with no result or assignment, no DB state/history mutation, malformed interval/path refusals, and source issues returned separately from operational eligibility.
- [ ] Run RED, implement routes and incident entry, run GREEN. Mount inspection from the incident's file inventory regardless of result.navigator_path. Keep decoder errors local to the selected record and preserve the channel list/other records.
- [ ] Ensure header-only and unsupported records have a useful screen rather than an empty navigator or raw exception. Add a visible analysis-eligibility summary separate from Load/Inspect.
- [ ] Run focused application/adapter and architecture checks; commit.

## Task 3: Analog/digital slots and native cursor slice

**Files:** Create static/inspection-model.js, tests/inspection_model.cjs and tests/test_inspection_model.py; extend static/inspection.js, static/style.css and static/index.html. Reuse existing navigation-model.js patterns where correct; keep old navigator working.

**Interfaces:** Pure UI model holds per-record channel-slot order/visibility, local viewport, hover position and pinned A/B sample indices. Async interval requests carry record+revision+channel+generation identity. Never use trace-envelope extrema as cursor values.

- [ ] Write failing model tests for A/B delta on actual nonuniform timestamps, sample-index-only delta when timing unavailable, digital unknowns, nearest-sample index/value attribution, channel reorder/visibility, gaps and stale response cancellation. Add numeric cursor index fields and left/right sample stepping for deterministic and accessible control.
- [ ] Run RED, implement separate analog/digital panes and a live value table. At least hover plus pinned A/B cursors must work across visible slots with clear local time/units; architecture supports additional named pins. Support zoom/pan/reset, hide/show/reorder, explicit overflow pagination and no silent channel loss. Keep pointer handling independent of waveform path rendering.
- [ ] Run GREEN and actual browser pointer/keyboard smoke: move hover, pin/move A/B, zoom, change channels and switch records during requests. Verify values against exact returned source samples, including missing state. If browser automation is unavailable, record the limitation and preserve deterministic API/model evidence; do not call visual interaction verified.
- [ ] Replay copies of authorized Dhone/DR2 inputs in an isolated app data root or securely reference immutable originals without changing them. Demonstrate the main application flow on an isolated port, preserving8091/8113/8092. Hash sources before/after. Keep the UI a main-app feature, not a standalone report.
- [ ] Run serial release verification, architecture checks and one fresh whole-branch review under existing Superpowers inline policy; one Important-fix TDD pass, no repeat review. Record exactly which parts of G1/G2 pass and which remain pending (including arbitrary extra pins/group overlays if not yet delivered). Commit/push verified results and update the goal board/handoff.

## Next milestones after this slice

Finish remaining G2 interaction, then G3 diagnostics and independently validated density/support options, G4 diagram, G5 conclusion/report composition and G6 scalability/reliability. Write a separate bounded implementation plan for each from inspected current code. Do not postpone inspection until every numerical question is solved; do not mark the whole vision complete after this first slice.
