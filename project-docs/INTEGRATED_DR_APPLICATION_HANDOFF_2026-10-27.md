# Integrated DR application: user mandate and execution handoff

Date: 2026-10-27. Baseline: main fc7453b (clean, pushed when inspected).
This document supersedes the research-first ordering in NEXT_SESSION.md and the
old heartbeat. It is a delivery mandate and roadmap, not a claim of implementation.

## User outcome

One scalable application in the main analyser project. Opening a disturbance
record must show every recoverable waveform, digital channel and sample value
without requiring a successful fault-location calculation, line assignment,
remote record, or common clock. The user wants the practical interaction of a
standard DR tool such as Wavewin: moving cursors update values; clearly allocated
analog/digital slots; multiple time cursors; useful single-line diagram; full
analysis snapshot, detailed evidence, and readable final conclusions.

The user explicitly asked to move this long conversation to a fresh chat, set
goals, achieve them, avoid repeated design discussions, and proceed autonomously.
Inline Superpowers execution and commit/push remain authorized. Existing author:
surya1650 / rscvreddy@gmail.com. No AI coauthor. Dash findings remain local unchanged.

Interpret “parse at any cost” as never withholding recoverable inspection because
an estimator refuses. It does not authorize invented samples, missing-to-zero
conversion, guessed timing/scaling, unsafe resource use, or bypassed analysis gates.
For irrecoverable/unsupported inputs retain the file/header inventory and exact
reason, and show everything independently recoverable. Do not promise all possible
formats or physically meaningful values from corrupt bytes.

## Present gap, verified by code inspection

- application/api.py `/navigator` requires result.navigator_path.
- workbench/samples.py `sample_interval` requires relay_evidence status analysed.
- application/static/navigation.js mounts through result.relay_evidence and has
  one cursor and selected-channel views. Reuse good existing behavior, but these
  dependencies prevent an inspection-first workspace on blocked records.
- application/worker.py `validate_assignments` correctly requires usable primary
  records for the operational analysis path. Do not remove this restriction to
  make a viewer work; provide inspection and supported diagnostics independently.
- The reviewed strict loader and actual-time diagnostics exist in main but are
  exposed only by scripts/analyse_source_record.py and a standalone HTML report.
  The user's criticism is valid: that report is not the requested integrated tool.

## Goals and evidence required to finish them

All items below are pending. Mark a goal done only after its acceptance evidence
is recorded. No research-only output may close an application-delivery goal.

| Goal | Deliverable | Acceptance evidence |
| --- | --- | --- |
| G1 | Main application opens recoverable source data before analysis/assignment | A needs_review, blocked Dhone-equivalent revision shows analog and digital observations through app APIs/UI without a result, terminal assignment, DB transition, or weakened gate; readable partial/error states remain |
| G2 | Practical waveform workbench | Separate resizable analog/digital areas; channel slots with original IDs/labels/units; select, reorder, hide/show, grouping/overlay, zoom/pan/reset; at least cursor A/B plus movable hover cursor, pin/add/remove cursors and delta times; live sample values and digital states; keyboard sample stepping; correct gaps and source/sample-index time basis |
| G3 | Integrated supported analysis | Automatic per-record diagnostics independent of common clock/line model; explicit coverage and method eligibility; local event evidence; conditional phasor/R-X/sequence composition only with its prerequisites; lower-density/short-support work delivered if independently validated, otherwise visibly unavailable with reasons |
| G4 | Single-line diagram and location placeholders | Persistent terminal-line-terminal schematic; full length and parameter provenance when supplied; distance/section overlays only when eligible; unknown length/constants/location explicitly Not available; no fabricated scale, terminal identity, breaker state or location |
| G5 | Understandable analysis snapshot and detail | Every opened record has What was observed / What it supports / What cannot be concluded / What is needed next; channel/window/source links and units; separate recorded start/trip from inferred inception/operation; printable/downloadable snapshot and detailed evidence from the same app model |
| G6 | Scalable, verified single-application delivery | Bounded interval loading, cache/provenance invalidation, cancellation/stale-response handling, background diagnostics, deterministic errors; real-file replay plus functional browser checks; serial full verification, one fresh branch review and one Important-fix pass per milestone, pushed commits and preservation/handover |

First milestone must be a usable G1/G2 vertical slice in the MAIN APPLICATION,
not another separate HTML viewer. The later goals are sequenced work, not a
reason to delay the first useful delivery. Keep a short goal board and update
checked acceptance evidence after each milestone. Do not repeat earlier research.

## Product and numerical contracts

1. Separate decode status, inspection availability, method eligibility, and
   operational conclusion. A red location gate cannot blank valid raw traces.
2. Show all source channel identities, including unmapped/ignored channels and
   channels beyond the visible page. Paging must not silently drop channels.
3. Cursor values use actual source observations with sample index and actual
   sample timestamp where available. Envelope extrema are not cursor samples.
   Nearest-sample selection states its timestamp; no unlabelled interpolation.
   At a missing observation/gap show unavailable. Digital unknown is not zero.
4. If reliable timed coordinates are unavailable, sample-index inspection remains
   possible where decoding supports it; do not invent fs, seconds or UTC. Preserve
   per-record local axes. Manual visual offsets are display metadata only.
5. Distinguish raw counts, CFG-declared engineering values, and verified physical
   quantities. Do not infer real CT/VT ratios, wiring, alias protection, clock
   provenance, line constants or fault identity from a good waveform fit.
6. Multiple recordings may be inspected independently and compared with explicit
   reference provenance. They are not automatically the same event, line or ends.
   Single-end diagnostics require no second record. Synchronized analysis remains
   available only when its evidence gates pass. Cursor alignment grants no clock.
7. Quantities dependent on missing prerequisites stay visible as Not available,
   with the specific missing prerequisite. Preserve useful observed conclusions:
   an unavailable fault location is not an unavailable record.
8. Extend supported inspection deliberately: ASCII/BINARY/BINARY32/FLOAT32 first
   through the strict path; CFF, multirate, digital-only, large/truncated captures
   need explicit recovery contracts and tests, not the old parser's silent zeros.
   Do not coerce unsupported container bytes into a supported layout.
9. Reuse the existing FastAPI/vanilla JS stack, workbench boundary and registry.
   Avoid a rewrite/new framework or production dependency unless justified by a
   measured gap. Keep display decimation separate from native values and DSP.
10. “According to our standards” means trace every analytical assertion to the
    project's actual standards/rules/evidence. Do not claim IEC/IEEE conformity or
    field readiness based on UI resemblance or synthetic test success.

## First implementation entry points

Read docs/superpowers/plans/2026-10-27-integrated-inspection-first.md first.
Existing modules to reuse:

- comtrade/source_observations.py: load_source(cfg_path, dat_path=None).
- comtrade/source_time.py: independent source coordinates, no clock authority.
- dsp/source_analysis.py: analyse_source(observations, *, max_windows=512).
- dsp/source_compare.py: compare_sources(analyses, reference=None), display only.
- application/api.py, workbench/samples.py, application/static/app.js,
  application/static/navigation.js and navigation-model.js.
- tests/test_application.py, test_native_samples.py, native_samples.cjs,
  test_navigation.py, navigation_model.cjs, test_unmapped_inspection.py,
  test_source_analysis_review.py, and scripts/check_architecture.py.

Application must call workbench APIs rather than import numerical internals.
Keep new adapters/UI modules small. No live server replacement is necessary to
implement and verify: use disposable app roots and an isolated test preview.
Treat filenames as revision-scoped identifiers, never arbitrary client paths.

Wavewin is the user's interaction reference, not a numerical certification
authority. Official-manual discovery links include wavewin.net/wwfull/ and
softstuf.com; direct PDF fetches failed in this handoff, so no manual-derived
behavior or parity has been verified. Research primary vendor documentation if
needed; the concrete user requirements above already authorize implementation.

## Delivered evidence to preserve, not repeat

Read project-docs/NONUNIFORM_SOURCE_ANALYSIS_2026-10-27.md and NEXT_SESSION.md.
Baseline release evidence (historical, not rerun in this documentation handoff):
primary 1637 passed/no skips/one existing upstream warning, 159.90 seconds.
Original/reviewed 152 study rows identical; freezes a02945e / 7bdb578; 15/16
UTF8-LF bindings including tests/full_record_signals.py. All 36 step cases refuse.
Eight coherent gain/alias controls pass fits while physical conclusions are wrong:
model consistency never grants physical/production/location/alignment authority.
One fresh review and single Important-fix pass DONE; no repeat review of that work.

Private replay: 14 CFG = 12 complete pairs + 2 VINUKONDA CFG-only missing DAT.
11 pairs are in Downloads; 26 source byte hashes unchanged. 718 windows /
6362 channel-windows: 2007 model-consistent / 4355 withheld. Preserve failures.
Dhone: 212/592 channel-windows; AnyStart span 33.280 ms, bracket
[32.448,34.112] ms in source coordinates, not operating time/confidence.
DR2: 105/288; no recorded AnyStart reference. Do not invent one.
600 Hz records parse but current profile conservatively refuses upper frequency
candidate coverage. Validate alternatives on newly frozen disjoint grids before
changing policy; never tune the published 152 outcomes.
Scalar/fractional-DSP operational adoption remains HELD/FAILED. Optional joint-E5
research is lower priority than this application delivery.

## Protected state and verification

- E:\dr analyser is primary; Git remote is surya1650/Disturbance-record-Analyser.
- Python: E:\dr analyser\.venv\Scripts\python.exe; PYTHONPATH=src;.;
  OPENBLAS_NUM_THREADS=1. PowerShell login:false. Full pytest serial because
  shared test ports 8241-8243. Read native-worktree skills before isolation.
- Keep captures, C:\Users\rscvr\Downloads, lines list.xlsx, both Dash findings,
  application DB and existing revisions unchanged. New tests/demo data use a
  separate root. Never auto-assign or update the real pending revision.
- Existing app http://127.0.0.1:8091/, PID36936/session23573; catalogue8113,
  PID40504/session30570; source viewer8092, PID24720/session49245. Preserve all.
  PID values are historical: verify command ownership before any future action.
- Pending incident4fb72844a355427c85d79ad4adb6b249 revision1 Needs review.
- Reviewed source report: http://127.0.0.1:8092/#r1 Dhone; #r9 downloaded DR2.
  It is reference evidence, not the final product. Do not replace the app with it.
- out/qa/nonuniform-source-analysis-2026-10-27 has 43 hash-preserved ignored QA/
  ledger files, manifest preserved-worktree-sha256.json. Native worktree archived.
- Prior CUA initialization failed; HTTP/HTML/JSON passed but visual QA was NOT
  performed. New interactive UI requires actual pointer/keyboard verification;
  report an unavailable browser capability honestly, do not claim visual success.
- Natural usage resets only. Never buy credits or use manual resets. Handover
  precisely on interruption, then continue the next scheduled run.

## Execution ownership

A fresh project chat will own this mandate. Transfer the existing five-hour
heartbeat to that chat and this document so the old research prompt cannot start
a competing writer. Do not create duplicate automations or new recurring jobs.
Use Superpowers inline; no repeated design/approval questions. Track one milestone
at a time, verify product behavior, commit/push and preserve QA before native
worktree archival. Stop only at verified completion or genuinely external evidence
requirements; explicitly list remaining unsupported analysis without hiding traces.
