# Restore recording-first behavior without losing the simple report

2026-10-29. User reported that the earlier viewer was better and requested its
input/corrected-CFG workflow and analog/vector/digital arrangement. Current base
889becd; reference e3a9db35c13a5df7bd274dcd6ffcf95afca204cf was fetched read-only.

## Evidence and scope

Current inspection-workbench shown() slices all signals eight at a time, so digital
channels can be absent from an analog page. Current main-derived branch also lacks
ratio_inputs.py, instrument_review.py and instrument-review.js that the earlier
viewer used to resolve missing declared ratios through reviewed copies. Its generic
assignment refusal hides the actionable RATIO-P/S flags shown in the user's earlier
Chandragiri screenshot (secondary side, primary1/secondary0). The current screenshot
alone does not establish every remaining gate or verified instrument ratings.

Restore every analog channel above, voltage before current, vectors alongside,
and changed digital signals below with optional extra channels in a top disclosure.
Remove shared signal pagination. Keep exact cursors bounded with eight-channel
batches and concurrency/resource limits, readable axes and trigger-relative source
coordinates when supported. Determine changed signals from native states, not
lossy envelopes. Keep the simple report and feature-help task panels.

Restore the earlier explicit CT/VT questions and reviewed-copy path. Original CFG,
DAT and revision bytes stay immutable. A reviewed copy may update missing ratio
fields only from positive supplied ratings with reviewer/evidence/confirmation,
then a new revision reruns conformance. Export a marked copy with evidence manifest.
No bypass for unrelated timing, scaling or missing-channel findings. Raw inspection
remains usable independently.

## Constraints and policy

PROJECT_CONTEXT section2 and CLAUDE rules apply. No estimator or DSP gate changes,
clock inference, invented ratios, sign correction or silent source rewrite. This UI
layout is project policy, not standards certification. COMTRADE source identity and
reviewed-copy provenance remain explicit; no new interpretation of the standard.
No site-specific default or unknown physical parameter is silently supplied.

## Phases and acceptance

1. Restore native digital activity/timeline metadata and all-analog viewer with
   bounded cursor/native transport. Digital-only, all-null, no-change, sample-only
   and 64-channel cases have explicit behavior.
2. Port reviewed instrument-copy API/UI and tests from the reference commit; connect
   Inputs & help and actionable operational-assignment messaging. Prove original
   hashes/DAT unchanged, stale revision refusal, strict input validation, exact
   conformance rerun and download provenance.
3. Browser desktop/mobile/realDR2 and synthetic bad-ratio replay, regression tests,
   architecture guard, Ruff and 10,000-case synthetic acceptance. Commit and push
   to the already-authorized review branch after verification, without merging main.

## Expected change and limits

All decoded analogs and changed digitals are visible without paging; UI-request
batching remains. A ratio blocker becomes a targeted input path and a marked new
recording, not an assumption that all recordings are operationally eligible.
No original data migration. Existing reports remain bound to their revisions.
Actual CT/VT ratings and physical clock/line/terminal evidence remain external.
