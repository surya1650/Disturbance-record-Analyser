# One-cycle viewing and incident event report

Implemented on the authorized `codex/operator-ui-review` branch. Original
record bytes, operational four-cycle fits and E1–E5 estimators are unchanged.
No environment publication or merge to main is part of this delivery.

## Visible behavior

- All analog channels remain mounted above changed digital channels. Their
  plotting widths/time coordinates align, with labelled vertical scales,
  channel values alongside and voltage/current vectors in the side panel.
- Clicking, typing or stepping a cursor locks the shared source index for
  instantaneous values, digital states, RMS and vectors. Mouse motion cannot
  replace the locked readings. Follow hover explicitly resumes live tracking.
- One-cycle measured RMS is a dense trailing-cycle sample observation,
  including DC/harmonics. Zoom requests exact RMS samples within the existing
  bounded native viewport budget; overview envelopes are never cursor values.
- Cursor fundamental phasors use harmonic-plus-DC actual-time least squares,
  DFT-equivalent on a uniformly sampled integral cycle. All channels use the
  same complete trailing support and cursor phase reference. First-cycle,
  missing-sample, gap, frequency and scaling limitations remain explicit.
- Simple report is incident-level, with explicit sending/receiving record
  selection and substation names, combined phase voltages above combined
  currents, selected pre/fault/optional post RMS and percentage changes,
  recorded digital transition brackets, existing eligible method-labelled
  location and optional evidence-bound relay-reported distance.
- Applied channel mappings and digital assertion choices reach this report;
  saved inputs are revision/source-bound with optimistic concurrency checks.
  HTML and JSON exports use the same report model. Moving cursors or editing
  fields cannot silently change a built report.
- Physical-unit/mapping conflicts are withheld with their provenance. Raw
  counts retain their units and scaling explanation. Successive captures
  from one relay are refused as an opposite-end pair.

## Verification

Direct architecture checks/self-tests, changed-Python Ruff and changed-JS
syntax checks pass. The repository-wide Ruff baseline adds no findings
(39 current versus 40 previously recorded findings).

Stage-A 10,000 cases: PASS, clean two-ended p95 error 0.4361% of line length;
zero impossible distances without a caveat. Final full pytest: 1,921 passed,
28 private-data skips, one existing Starlette deprecation warning, 126.45 s.

Real local DR2 browser replay: 1,800 samples, all eight analogs and 32 digital
channels in the source inventory. All eight analogs returned cursor Fourier
observations at sample 100. Browser checks passed locked readings/no hover
requests while locked, follow-hover resumption, two vector plots, exact native
RMS paths, matching analog/digital plotting bounds and mobile width. No page
errors. These observations do not validate DR2 scaling or authorize location.

Synthetic opposite-end browser checks passed paired quantity/phase plots,
one-cycle RMS, pre/fault/post comparisons, held shared overview cursor,
relay-reported distance, persisted reload, A/B interval transfer, source
mapping/polarity transfer, escaped user text, stale-input notice, matching
HTML/JSON report data and mobile width. Private input and QA artifacts remain
under ignored `out/qa/event-study-2026-10-29`.

## Practical limits

One-cycle viewing does not certify phasor stationarity, frequency, anti-aliasing,
CT/VT wiring or physical scale. Nominal frequency is declared, not tracked.
Source timing preparation is cached per decoded source; each cursor fit is
capped at 4,096 source observations and API batches at 64 analog channels.
The existing decoded-source LRU retains at most two sources.

Selected fault-region starts are display references, not detected inception or
clock synchronization. Report RMS is the median of complete one-cycle supports
wholly inside each selected interval; short regions stay unavailable. A relay
distance is an operator-transcribed estimate, not patrol ground truth. Trip and
AR commands do not establish physical breaker opening or successful reclosure.
Location still requires the reviewed line and existing eligible incident study;
the UI never manufactures a distance from an unsupported fit. This remains a
bounded local application, not a qualified production multiuser service.
