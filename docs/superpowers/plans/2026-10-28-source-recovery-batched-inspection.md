# Bounded Source Recovery and Batched Inspection

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline. Autonomous implementation/verification/integration/push remains authorized; no further design questions.

**Goal:** Recover digital-only/short/container/complete-prefix observations under explicit contracts and keep cursor interaction efficient on large records without inventing missing data or timing.

**Architecture:** Separate bounded container/file acquisition from the existing strict observation decoder, retaining its numerical/scaling/time rules. Add one bounded multi-channel/multi-index source-point adapter/API and use already-loaded native intervals for local cursor lookup. Keep all provenance, identities and operational analysis gates intact.

**Tech Stack:** Existing Python/NumPy/FastAPI/vanillaJS/pytest/Node; no new production dependency.

**Spec:** project-docs/INTEGRATED_DR_APPLICATION_HANDOFF_2026-10-27.md and INTEGRATED_DR_GOAL_BOARD.md; later user requests for usable analysis/errors/defaultCT/phase choices remain in force.

## Global Constraints

- No writes to original captures/Downloads/workbook/Dash/realDB/revisions or protected8091/8113/8092. Disposable roots/8094 only.
- Strict source fitter/operational/scalar policy and152study artifacts remain unchanged. New decode support grants no physical/clock/alias/location authority.
- Preserve native source sample indices and nullable observations. Incomplete bytes never become zeros. Unsupported framing/unknown formats stay explicit local errors with retained header/file inventory.
- Existing budgets retained: CFG1MiB, DAT64MiB, source200000samples/4000000cells, analog64/digital256; explicit channel/file overflow reasons. Native interval20000sample cap retained.
- One fresh whole-branch review/single Important-fix TDD pass, serial release/primary verification, commit/push; hash-preserve ignored QA/ledgers before native archival.

## Review Focus

- Container marker-like bytes inside a binary payload must not be mistaken for framing; explicit CFG format governs, conflicting DAT markers refuse.
- A binary complete-prefix recovery must stop at broken row-counter continuity and retain exact omitted-byte/remainder status without guessing alignment.
- Digital-only/one- or two-sample sources retain observations even when source-time/model prerequisites fail; no invented fs/seconds/UTC.
- Native local cursor reuse must remain bound to record/revision/generation/source hashes; stale batch responses/errors cannot restore previous-record values.
- Many selected channels/pins/large views require bounded batches and explicit limits; verify no per-channel/per-pin source reread fanout.

## Task 1: Strict decode bytes boundary and deliberate recovery contracts

**Files:** comtrade/source_observations.py, new focused source_container/source_decode/header helper as justified; tests/test_source_recovery.py.
**Interfaces:** load_source(path,dat_path=None) stays compatible; a bounded byte-decoder helper preserves original byte hashes/format basis and returns existing nullable source schema plus explicit recovery metadata. Source-time and fit eligibility remain separate.
- [ ] RED tests for digital-only ASCII/BINARY/BINARY32/FLOAT32,1/2sample inputs, empty input, all-missing analog/digital states, exact byte hashes, nonconsecutive counters, truncated tail and truncated first row. Expectations literal independent values.
- [ ] Refactor file acquisition away from decode with unchanged supported full-CFG/DAT outputs. Allow zero analog only when digital count positive; allow1/2samples for inspection with withheld time/model where existing coordinate contract requires3.
- [ ] Deliberately recover only complete binary rows, stopping at first broken counter continuity when payload is partial/corrupt. Record declared/decoded counts, omitted bytes and issues; withhold structural timing/model authority. No partial-row padding or offset search.
- [ ] Run focused source/time/analysis/application controls and byte/hash assertions; no152study rerun/tuning. Commit.

## Task 2: Explicit CFF framing and recoverable header metadata

**Files:** focused comtrade/source_container.py/header helper, workbench/source_inspection.py; tests/test_source_containers.py and API cases.
**Interfaces:** Supported CFF uses bounded explicit file-type CFG and DAT section markers; CFG declares one supported DAT format, an explicit DAT format must agree. Byte payload cannot be searched heuristically for binary metadata markers. Original container SHA256 remains the revision identity.
- [ ] RED fixtures for supported ASCII/BINARY/BINARY32/FLOAT32 containers, digital-only, missing DAT, malformed/unknown/conflicting markers, marker-like binary bytes, recognized trailing text metadata, and truncation. Test main app needs_review/no-result/no mutation.
- [ ] Decode supported framing through the same strict byte decoder. Use explicit declared row width/count to distinguish complete binary payload from recognized subsequent text sections; unsupported ambiguous framing reports a precise reason and keeps independently readable header facts.
- [ ] Preserve original container hash and declared header/scaling/time metadata; do not expose virtual CFG/DAT hashes as if separate uploaded files. Keep unsupported remaining variants visible with reason.
- [ ] Focused GREEN/architecture/Ruff, commit.

## Task 3: Efficient exact cursor batches and large-record qualification

**Files:** workbench/source_inspection.py or focused point adapter; application/inspection.py; inspection-model/workbench JS; tests/test_inspection_points.py, inspection_model.cjs.
**Interfaces:** read-only inspection_points(root,revision,filename,channel_ids,indices) returns exact nullable observations for at most8channels×17indices in one validated source read. New scoped API; old native interval remains compatible. UI uses hash/generation-bound native interval observations locally when present, otherwise one cancellable bounded point batch.
- [ ] RED tests for mixed analog/digital/unknowns, nonuniform/index-only times, duplicates/bounds/type/path/hash errors, stale batches, pin limits, local exact lookup and no extrema-as-cursor substitution.
- [ ] Implement one-read batch adapter and generation-isolated client requests. Reuse loaded exact native intervals; cap additional pins explicitly with a readable reason. No silent channel loss.
- [ ] Replay supported real-file copies with hashes before/after; generate public large/many-channel/gap/partial fixtures and record bounded response sizes/cold-warm latency as qualification observations, not field/standards certification.
- [ ] Actual browser pointer/keyboard/cursor/record-switch/error/large-view checks if available; record exact limitations otherwise. Serial full suite, one review/single fix pass, primary verification, commit/push and update G1-G6 acceptance. Preserve all scoped QA/ledgers before final native cleanup.
