# Clear incident report and simple portal — goal v1

2026-11-03, Asia/Calcutta. Branch `codex/operator-ui-review`, starting `52256d1`.
The user explicitly asks for implementation and overnight continuation, including
after a five-hour reset. This goal supersedes the earlier two-page primary report
and the five-tab/power-user portal layout. Preserve existing working backend
capabilities, source bytes, results and numerical gates.

## Outcome

A non-specialist can upload a recording, understand the recorded disturbance,
optionally compare another recording, and generate one readable incident report
in three or four A4 pages. The primary flow is:

**Upload & parse → Analyse → Compare (optional) → Generate report.**

No line model, opposite-end identity or instrument constants are demanded just
to inspect samples. Ask only the actual missing facts required for a requested
physical calculation. Technical catalogue, collectors, audits, raw rule IDs,
model-fit controls and developer options stay in backend/secondary engineering
interfaces, outside the primary flow. Necessary CT/VT/channel/line/end review is
contextual and retains existing validation; it is not removed to make a number.

## Report contract

Target four physically verified A4 pages, with readable text and self-contained
waveforms. Proposed page order:

1. **What happened and where:** brief plain-language summary, recorded sources,
   available classification, eligible method-labelled location/reference or the
   exact reason it cannot be calculated, and useful next actions.
2. **Currents:** per-record/per-phase before/during/after effective (RMS) values,
   explicit A/kA or raw units, selected support and labelled waveforms. Show each
   source independently; a missing first source cannot hide the other's values.
3. **Voltages:** per-phase values and waveform plots with units, source-local
   time and recorded-change regions. Do not fabricate healthy pre-fault support.
4. **Signals and explanation:** selected recorded digital changes/timeline,
   plain interpretation, what remains unknown, and a short glossary.

RMS is not peak divided by sqrt(2). Distinguish native fault-window sample RMS
from the median of complete one-cycle RMS observations. A whole-record maximum
does not become fault current when the event window is unavailable. Preserve
real zero values and give named reasons for unknown values; no bare dash-kA.
Primary kA/kV requires supported scaling/meanings; raw counts remain counts.

Report records are display selections, not automatically opposite ends.
Prefer explicitly accepted primaries for physical summaries; otherwise name
independent recordings without inventing S/R identity. At most two representative
sources are plotted in the four-page report; attached/corroborating sources and
any omissions remain explicit and accessible in backend evidence/JSON. Reviewed
copies must not be double-counted as separate physical captures.

No inferred mechanical pole counts, unproved opening/reclosure, guessed fault
diagnosis, generic accuracy percentage, silently synchronized clocks or hardcoded
confirmation endpoint. Keep observation, interpretation and uncertainty clear.
The old technical report and full evidence remain accessible through their
backend contracts, but do not form the default user-facing report.

## Phases and acceptance

- **P0, protect and design:** persist this goal/checkpoint, inspect the actual
  screenshot/current flow, capture synthetic baseline and define the canonical
  report model. Existing qualified baseline:2,192 passed/28 private-data skips;
  architecture/self-tests/Stage-A10,000 pass, clean p95 .4361%;26 inherited lint
  findings remain. Do not pretend those are new feature results.
- **P1, report measurements and narrative:** versioned canonical JSON model
  reusing source decoding, automatic/manual region evidence, one-cycle RMS,
  operational measures and source-bound location. Independent synthetic cases
  prove each reported current/voltage, unknown reason and narrative boundary.
- **P2, printable report:** render the same model to a clear four-page HTML/PDF
  presentation, with waveform gaps, legible axes/tables and escaped source text.
  Use native browser Print/Save as PDF unless a supported portable PDF backend
  is established. An actual Chromium PDF must have the promised page count and
  no clipped/overflowed content on all representative fixtures.
- **P3, simple workflow and generation:** reduce the portal's main navigation
  to the four tasks. Add a primary Generate report action with immutable
  generation history, preview/open/print and HTML/JSON export. Preserve waveform
  cursors/RMS/vectors, comparison, reviewed ratio copies, source/revision guards
  and old history. Required engineering inputs remain available in context.
- **P4, qualify and deliver:** browser-test desktop/mobile and full upload to
  report flow, readable PDFs, stale/cancelled requests, source/record/revision
  changes, missing inputs and old report immutability. Run direct architecture
  guard/self-tests, changed Python lint/JS syntax, full pytest and Stage-A10,000.
  Publish evidence and independently reviewable phase commits to the authorized
  review branch, verifying remote HEAD. No main merge or deployment.

## Data/API and preservation

New canonical model/report kind is versioned and additive. Generate report from
one frozen incident revision with zero or explicit source selections; save each
generation as immutable model JSON and HTML. Existing operational result/report
paths are not overwritten or silently recomputed.

New routes: POST/GET `/api/incidents/{id}/incident-report` (revision required for
generation; optional up-to-two source records), then generation-scoped `/html`
and `/data` endpoints. Use existing local authentication and source access
checks. Generated content remains under that incident/revision application root.
No current data, hashes, ratios, polarity, metadata or history is mutated merely
to build a report.

## Constraints and qualification

PROJECT_CONTEXT §2 constraints remain binding: E5 needs no GPS; no per-relay ML,
traveling-wave method, silent input repair or one report per file. Existing
section-aware location conversion and native k0/loop definitions are reused.
The user's explicit current request changes primary report length to3–4 pages.
No new standards clause or calibrated-confidence/field-accuracy claim is made.

Use synthetic known42km, single-end, incompatible ends, missing ratios/raw counts,
short/ongoing/gapped intervals, no/unknown signals, saturation and many-channel/
long-label cases. Original private records and screenshots are not committed.
New measurements may become visible where the old global summary was blank;
their exact source/window/RMS basis must accompany them. Numerical E5 outputs
and existing data/quality gates must not move.

## Overnight continuation

`INCIDENT_REPORT_PORTAL_CHECKPOINT.md` is the cold-start entry point: exact HEAD,
completed/active phases, checks, blockers and next action. Update it at each
milestone and push review-branch checkpoints. Use an exclusive local lease under
`work/qa-incident-report-night-2026-11-03/` while actively editing. Continuations
must check for a fresh active writer and uncommitted work, preserve all changes,
and avoid starting a competing writer. Resume unfinished phases from the latest
checkpoint; if complete, verify status and stop. Platform limits are not bypassed.
Only the explicitly requested overnight continuation is scheduled, not an
indefinite unattended feature backlog. Pause its owned follow-up when done.
