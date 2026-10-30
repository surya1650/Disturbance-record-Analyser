# Source-first workflow verification — 2026-10-30

The user supplied two private recording pairs and requested end-to-end verification,
clear blockers and simple steps without breaking existing features. Private files,
record-specific findings, screenshots and user guide remain under ignored
`out/qa/real-record-followup`; no field capture or identifying metadata is added here.
Original uploads and QA copies were hash-checked, with all four unchanged.

## Changes driven by actual reproduction

A secondary-record profile has unresolved instrument ratios, so inspection correctly
uses raw counts. Auxiliary current labels with a suffix also contaminated the
comparison-wide phase-convention detector, splitting main phase counterparts.
Anonymous regression reproduced that defect before the fix. The detector now keeps
unambiguous primary phases separate from unsupported auxiliary suffixes. Counts can
pair for **display only** when source label, declared electrical quantity and header
phase agree. Values remain counts with independent axes and explicit scale caveats;
unknown/conflicting declarations still refuse pairing. No ratio is fabricated and
no operational gate is relaxed. Auxiliary traces retain their own identities.

A compact three-step source-aware guide uses existing tabs: Inspect, Compare,
Read report (physical distance optional). Operational findings are collapsed under
optional physical input review; direct CT/VT review is preserved. Physical calculation
is collapsed unless previous physical inputs/results exist. Observation-report
labels are optional, falling back to a bounded filename only, never a guessed
substation/end. Generated labels survive save/reopen even for long filenames.
Manual/automatic regions, same-event confirmation and source/version guards remain.

The signal audit reproduced carrier-failure abbreviations being interpreted as
AR failure through a substring match. AR boundaries now prevent that confusion;
explicit distance-carrier receive and reverse-order AR initiation aliases are
recognized. Reviewed overrides/polarity remain authoritative. Digital indications
still cannot certify a physical opening/reclosure; current-collapse timing is not
recorded CB-contact feedback.

## End-to-end and limits

Both private sources were uploaded, decoded and exercised in Chromium desktop/mobile.
Seven main phase/neutral counterpart rows now pair, with original units retained.
Waveforms/digitals, playback, source changes/cancellation, independent automatic
observation reports without line/display-name facts, HTML/JSON exports and mobile
layout passed. No browser errors or mobile document overflow were observed.

No pair identity, opposite physical ends, clock synchronization, actual missing
CT/VT values or line impedance was invented. Filename/header clocks do not prove
pairing. No matching line model is supplied for this verification. Distance remains
withheld until actual facts and method-specific eligibility are established;
independent inspection/comparison are available meanwhile. Derived supported source
sampling can be used without rewriting its header; source observation regions and
operational phasor windows are different evidence and not interchangeable.

## Verification

Full suite: **2036 passed, 28 private-fixture skips, one inherited Starlette warning**,
111.63s. After a bounded long-filename display-label correction, **66 affected
report/label/signal tests passed**, including its new save/reopen regression.
Direct architecture guard/self-tests, changed Python Ruff, changed JS syntax and
`git diff --check` passed. Signal mapping budget intentionally grew by two lines;
other budgets were not reseeded. Stage-A10,000PASS, cleanp95 **0.4361%**, zero
impossible m without caveat. No estimator, parser or waveform-sample change.

Review branch delivery only; no main merge, environment publication or production
deployment. Private real-data QA is distinct from field accuracy qualification.
