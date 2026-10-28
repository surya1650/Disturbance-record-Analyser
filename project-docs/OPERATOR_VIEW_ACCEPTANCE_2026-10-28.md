# Operator view: delivery and acceptance

Code milestone: `bc6d83a` → `6a974c4` → `9ed98d6` → `e1f3fdf`.
This extends the integrated application; it is not another standalone report.

## Delivered behavior

- Instantaneous source readings sit beside their waveform; supported fitted RMS and relative angles share that panel, with separately labelled units.
- Voltage/current vectors have separate magnitude scales, a visible reference selection and common model-centre phases. They follow hover/moved pins. Off-screen pin movement pans the view.
- Digital channels show known/unknown states, without meaningless RMS/angle fields.
- The main report leads with voltage/current overview, explicit operator-selected pre-fault/fault/post-fault regions, fitted-RMS comparisons, trip/AR indications and the schematic. Point/model bookkeeping is expandable.
- Only supported windows wholly within each selected region contribute. Applied `[A,B)` bounds remain visible after cursors move; exact matching cursor source times are included when available. JSON/printable output carries the same selection.
- Four-sample/partial inputs keep exact observations and specific model refusal reasons. No phase, timestamp, scaling or physical fault boundary is invented.
- `TAKEOVER.md` covers fresh installation, public demo, operator workflow, development entry points, constraints and next-owner priorities; README links it.

## Verification

Final isolated suite: **1787 passed,29 skipped,one existing warning,98.16s** after the single review-fix pass. Skips:28 absent private-corpus cases plus1 Windows symlink privilege case.

Primary suite: **1815 passed,1 Windows skip,one existing Starlette/httpx warning,170.66s**. Architecture, changed Python Ruff and JS syntax checks passed.

Real copied DR2 replay:105/288 conditional channel-window fits;4 supported cursor rows and3 selected-region comparisons in the qualification example. These are export-coordinate observations, not authenticated fault states.

Public `create_demo.py` and ZIP intake were exercised locally: S370/R492samples,14channels each, needs_review with no operational result. The public onboarding incident is `9b16cdf4400a43429f9016feca78dfa5` in the final disposable root.

## One fresh review and one fix pass

One fresh review covered `bc6d83a..9ed98d6`; no Critical finding. Two Important findings were reproduced RED2 → GREEN26 focused → green full suite:

1. Live/printable region reports omitted applied bounds. Fixed with a persistent half-open index caption and exact source times when available.
2. Removing a followed extra cursor left an undefined followed cursor and blank readings. The owner regraded this from Minor to Important; removal now falls back to a surviving active cursor.

No second review. The guide's final-preview-root note was a pending delivery task, now fulfilled by actual routing proof below. The earlier zero-safe-row recovery metadata minor remains explicitly deferred.

## Actual browser scope

Fresh CUA at1265×712 verified real DR2 inline supported/refused values; numeric/waveform cursor moves; reference refusal and automatic recovery of vectors; zoom and off-screen cursor following; manual regions; collapsed technical details; preserved main schematic; choice invalidation and record switching; four-sample exact analog/digital values,2.6ms delta, honest four-cycle refusal and AR blocking summary. Five screenshots and short-record DOM are preserved under the operator QA directory.

Those checks were against the review candidate before the two fixes. The fixes are verified by reproducing transport/report tests and the full suites. No post-fix browser interaction or rereview is claimed.

Browser download delivery, OS printing, forced network/cancellation failures, additional devices, broader accessibility/load testing and independent fresh-machine installation were not performed. Export/transport logic and shared markup were checked in code/tests; local onboarding commands were exercised.

## Stable preview and protected state

Actual8094 process37016/session57576 runs from `E:/dr analyser` with:

`--root out/qa/integrated-final-preview --workers 1`

The eight existing preview incident URLs, frozen copied source hashes and served current static-file bytes were verified over HTTP. The current URL therefore remains valid after temporary-worktree cleanup. Worker1 supports new uploads in this disposable root.

All26 original capture hashes and the real pending revision matched preserved baselines after primary verification. Originals/Downloads, workbook, Dash, realDB/revisions and protected8091/8113/8092 were not changed.

The continuation heartbeat was paused through the native app tool and its `PAUSED` state verified, so it will not compete with the next owner.

## Decisions, limits and next-owner work

Operator A/B regions are explicit selections; automatic physical boundary detection is future work. Vectors use a common supported model centre and do not interpolate/rotate an instantaneous phasor. Existing four-cycle/stationarity/frequency/recovery/scalar/operational policies and the152study remain frozen. Transient/sub-four-cycle RMS/phasors require independent validation before changing those policies; a short fault can still lack fitted RMS/angles.

Physical meanings, CT/VT, wiring, clocks, event/ends, line facts and protection settings require asset evidence. No new operational adoption, field accuracy, standards conformity or protection decision fitness is claimed. Broader device/load/accessibility and external print/download paths remain qualification limits.

Deferred minor: zero-safe-row binary failures omit structured opaque/declared/decoded counts, while original hashes, explicit failure and zero samples remain correct.

Ignored QA and all scoped ledgers are preserved with SHA256 verification before native archival. The final preservation manifest and archival result are recorded in NEXT_SESSION and the goalboard.
