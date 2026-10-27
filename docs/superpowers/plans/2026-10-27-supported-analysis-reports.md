# Supported Analysis and Clear Reports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline. User approved autonomous design, implementation, integration and push; no approval loop.

**Goal:** Keep usable observations and a readable report available; apply explicit channel meanings, user-requested CT assumptions, phase colours, and source-supported trip/AR diagnostics.

**Architecture:** Preserve strict observation decoding and operational solver gates, expose source diagnostics through workbench adapters independently of those gates, and render method-specific reasons instead of an overall Blocked wall. Use a bounded per-app background job service; snapshots and detailed evidence share the same source/options-bound result. Extend the existing waveform workspace rather than introducing another report application.

**Tech Stack:** Existing FastAPI, Python/NumPy, vanilla JS, pytest and Node. No new dependencies.

**Spec:** project-docs/INTEGRATED_DR_APPLICATION_HANDOFF_2026-10-27.md plus latest user instruction recorded in project-docs/INTEGRATED_INSPECTION_FIRST_2026-10-27.md.

## Global Constraints

- Original files, DB/revisions and protected previews remain untouched. Disposable root/port8094 only.
- Missing observations stay unknown. Source clock coordinates and default ratios never become verified physical/clock/location authority.
- User-authorized missing CT ratios:132kV600/1,220kV800/1; never override a supplied valid ratio. Show when assumptions were applied, and retain raw source inspection.
- Simple analysis/report remains available when some methods lack prerequisites. Unsupported quantities say Not available with specific reasons.
- All numerical calls go through workbench adapters. No changes to the published152case outcomes or numerical policy.
- Serial full verification, one fresh whole-branch review and one Important-fix TDD pass for this milestone.

## Review Focus

- Missing CT ratio vs missing a/b/unit/side must not silently fabricate a physical current scale.
- Explicitly ignored/ambiguous digital channels and missing states must not establish a trip/AR failure.
- Switching sources/options while background jobs complete must never show another result or old assumptions.
- Two independent recordings may be compared but waveform resemblance cannot establish common clock/event/ends.
- Snapshot/diagram must preserve missing line length/constants/location; assumed CT values must not unlock an authoritative location.

## Task 1: Selectable phase display and plain input messages

**Files:** static/inspection-model.js, inspection-workbench.js, inspection.js, app.js, style.css; tests/inspection_model.cjs.
**Interfaces:** per-record model holds editable phase colours and channel display groups. Overlay only channels with matching declared units; explicit phase/colour choice is display metadata only.
- [ ] Add failing model tests for phase defaults/custom colour, safe grouping, unit separation and persisted record preferences. Run Node RED.
- [ ] Implement coloured phase traces and editable palette/channel phase choices; analogous units may overlay; preserve native cursor source identity.
- [ ] Replace overall Blocked display/raw flag dumps with plain availability messages and expandable exact input notes. Keep operational checks in backend. Source status and errors use human labels.
- [ ] Run Node GREEN plus actual browser controls, commit.

## Task 2: Independent diagnostics, explicit mapping and CT assumptions

**Files:** workbench/source_diagnostics.py, source_inspection.py metadata; application/source_jobs.py, inspection.py; tests/test_source_diagnostics.py, test_inspection_diagnostics_api.py.
**Interfaces:** diagnose_source(root, revision, filename, options) returns source/options-bound summary, per-window evidence, digital intervals and a four-part conclusion. options contain voltage_kv (unknown/132/220) and explicit per-channel meanings. Missing-ratio fallback applies only to known secondary currents with known finite source a/b and units; invalid prerequisites retain counts and explain why.
- [ ] Write failing tests for valid supplied ratios retained,132/220fallback provenance, unspecified side/unit/gain staying unknown, invalid mappings, ignored digitals, observed trip/AR indications with exact source brackets, unknown states not becoming zero. Run RED.
- [ ] Compose reviewed analyse_source/compare_sources without numerical policy changes. Map source IDs explicitly; label conditional signal fits. Derive possible trip/AR explanations only from supported observations with channel/window references. Sequence/R-X/location remain Not available unless their own prerequisites exist.
- [ ] Add bounded background service (one running/two retained results, deduplicated source+options identity, deterministic pending/ready/error states). Source checksum verification remains before accepting cached results; no DB mutation. Native inspection remains independent. Test pending/final/stale identity and limits.
- [ ] Run focused GREEN, architecture/Ruff, commit.

## Task 3: Integrated snapshot, schematic and comparison

**Files:** static/inspection-analysis.js, index.html, style.css; workbench/source_snapshot.py, tests/test_source_snapshot.py.
**Interfaces:** analysis UI consumes the same job result for What observed / What supported / Cannot conclude / Next evidence, detailed windows, source-linked digital intervals and JSON/print exports. Schematic uses only supplied frozen line facts with provenance; otherwise Not available. Comparison uses explicitly selected independent source snapshots, with local axes and no inferred clock/physical-end relationship.
- [ ] Add failing snapshot tests for missing line placeholders, recorded vs inferred times, default ratio assumptions, unavailable method reasons, source/options/hash binding, and JSON serializability. Run RED.
- [ ] Mount analysis controls/results inside main inspection workspace. Channel meaning choices apply to independent diagnostics even when operational assignments need review. Poll/cancel by source/options generation; no stale report. Add evidence paging, conditional method panels, persistent schematic and download/print from the same result.
- [ ] Show existing eligible operational estimates as conditional sourced results; never manufacture approximate km without line data. Clearly separate source-supported patterns from possible causes requiring evidence.
- [ ] Run GREEN and actual browser pointer/keyboard/report/default-ratio checks; replay protected-source copies/hashes; serial full suite, one fresh review/single TDD fix pass, commit/push primary. Update G1-G6 board with exact achieved and pending acceptance.
