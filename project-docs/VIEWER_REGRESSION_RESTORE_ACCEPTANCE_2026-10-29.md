# Recording-first restoration acceptance

Base 889becd on codex/operator-ui-review. The earlier e3a9db3 viewer was inspected
read-only; the missing behaviors were ported without discarding the simple report.
Plan: VIEWER_REGRESSION_RESTORE_PLAN_v1.md.

## Delivered behavior

- Every decoded analog channel is mounted with no channel pagination. Voltage is
  above current by the existing conservative quantity layout. Analog channels are
  mandatory; optional grouping/colour choices remain in the top disclosure.
- Voltage/current vectors sit alongside analog plots at desktop widths >=1000px.
  Digital plots are below that grid, spanning its width. Mobile stacks the views.
- Changed digital channels are selected from native-state activity, not the display
  envelope; unknown-state channels remain inspectable. The top selector adds other
  digital channels without changing analog visibility. State1 observed spans and
  exact changes retain uncertainty; state1 is not silently treated as trip polarity.
- Shared source coordinates, recorded-trigger-relative millisecond labels, relay
  local time, cursors, pan/zoom and fundamental fitted-RMS trends are restored.
  Missing fits remain gaps. Trigger zero is not detected fault inception.
- Axes remain readable and inline values are compact, with full unit/scaling and fit
  explanations expandable. Cursor movement updates cursor layers, preserving the
  waveform paths rather than rebuilding every path on each pointer event.
- Inputs & help restores required CT/VT primary/secondary rating questions, reviewer,
  evidence and secondary/gain confirmation. Only missing known-secondary ratios are
  asked for. Shared ratings are explicit and per-channel review remains possible.
- Check, create reviewed copy and download reviewed COMTRADE ZIP rerun conformance.
  The copy is marked, DAT bytes remain identical, provenance accompanies it, and
  saving creates a new incident revision with the original explicitly excluded.
  Original CFG/DAT/CFF and old revisions remain unchanged. Reopening the incident
  prefers the reviewed copy when its original is explicitly excluded.
- Operational assignment now identifies actual BLOCK findings and points to the
  required inputs. Missing ratios route directly to the selected recording's form.
  Other timing/scaling/channel problems are not bypassed by a ratio declaration.

## Why Chandragiri was blocked

The earlier supplied input-details screenshot showed RATIO-PS (also described as
RATIO-P/S): known-secondary current/voltage channels with primary1, secondary0.
Those fields cannot establish a primary scale. The current branch lacked the
older guided-copy workflow, leaving the generic assignment refusal. Both the
workflow and specific guidance are restored. No actual Chandragiri capture is
available in this workspace; a synthetic six-channel missing-ratio reproduction
was used. Actual ratings must still come from the operator's relay/asset evidence.
A screenshot alone cannot establish every remaining gate.

## Verification

| Gate | Result |
| --- | --- |
| Architecture self-test / direct guard | PASS |
| Changed Python Ruff and JavaScript syntax | PASS |
| Full Ruff | Same40 pre-existing findings, no new findings |
| Focused restoration checks | 90PASS,2private-data skips,one existing warning |
| Full regression suite | 1843PASS,28absent-private-corpus skips,one existing Starlette warning;129.40s |
| Stage-A 10,000,seed0 | PASS; clean p95 0.4361% |
| Browser restored layout | All8 analogs, vectors alongside,6 changed digitals below, no pagination, add another digital without losing analogs; desktop/mobile |
| Browser missing-ratio reproduction | Exactly6 rows, actual ratings/reviewer/evidence, passing recheck, real ZIP download with identical DAT, save revision2, reviewed selection retained after reload, vectors/RMS rendered |
| Browser private local DR2 | All8 analogs and changed digitals inspectable despite operational findings, no page errors |
| Browser supported analog limit | All64 analogs +12 changed digitals,76 exact cursor rows, batches<=8/concurrency<=3, envelope/native budget enforced, paths retained on hover |

The final reviewed-selection default was also verified with its pure guidance test
and the full browser scenario after the full-suite run. No physical site accuracy,
clock, wiring or universal relay compatibility claim is made.

## Resource and safety contracts

Cursor requests are <=8 channels each and <=3 concurrent; all batches are validated
against source/revision/channel/index identity and merged atomically. Native paths
require <=20000 samples and <=200000 displayed sample cells; otherwise bounded
source envelopes remain visible with exact cursor batches. Envelope budget uses a
conservative five points per bucket, keeping total response points<=16000.
Digital activity is cached in the owning two-source cache, with<=512 detailed
state1 intervals across a source,<=32 per channel; omissions remain explicit.
Display ticks<=513 and break indices<=512; excess breaks never become a continuous
fitted trend. Source gaps/unknowns do not imply state edges or physical operating time.

No estimator/DSP/conformance thresholds were changed. Copy ratios are explicit
supplied instrument ratings, not silent defaults. Other independent BLOCK findings
remain after a ratio review; API tests prove this. CFF/CFG, A/V and kilo-unit copy
rechecks, stale revisions/hashes, invalid rating types/ranges, unexpected fields,
foreign paths, no-source mutations and bounded UI transport are covered.

Evidence is local and ignored under out/qa/viewer-regression-2026-10-29. It includes
synthetic fixtures, logs, downloaded synthetic ZIP and screenshots. Private DR2
screenshots/captures remain local; none are included in the commit. Existing local
application data, user uploads and site files were not modified.


## Universal-input follow-up

After user feedback, universal CT/VT fields are the default visible inputs. Enter
CT primary/secondary once for listed current channels and VT once for voltage
channels; no fill button or per-channel typing is required. Existing valid CFG
ratios remain unchanged. Optional individual exceptions use explicit checkboxes;
changing a universal value preserves checked exceptions. Empty/invalid selected
inputs refuse checking/saving, and disabled inherited fields stay disabled after
an asynchronous check/download.

The pure UI model and 28 focused review/API checks pass. Chromium exercised entering
only the four universal values, captured the full six-channel review payload,
verified override isolation and disabled-field restoration, downloaded the marked
CFG/DAT ZIP and saved/reopened revision2 with unchanged original hashes and DAT.
Evidence: out/qa/universal-ratios-2026-10-29. Backend/conformance math unchanged.

Final follow-up gates:1843PASS/28private-corpus skips/one existing warning,116.22s;
Stage-A10000PASS,clean p95 0.4361%; architecture self-test/guard and JS syntax PASS.
