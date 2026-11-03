# Reviewed zone-boundary comparison — plan v1

2026-11-03. Starting branch `codex/operator-ui-review`, HEAD `b91e65a`.
The user's continuing implementation authorization applies; this is the next
bounded task following the completed autonomous analyser continuation.

## Problem and scope

The previous audit reproduced a Z2 indication being judged against an invented
Zone1 reach, plus a VA-only expected-zone projection for other fault loops.
Those assessments are now explicitly unavailable. Reviewed R–X plots work, but
do not yet provide a structured comparison of supported model points against
the associated exported boundaries.

Add a per-record, versioned geometric comparison using the existing R–X review
form. Compare the classified fault loop over the existing complete operational
phasor supports, then display inside/outside/mixed or not-evaluable results with
counts, source/settings/mapping provenance and a fixed local window.
The navigation cursor, zoom and thinned display points do not change this model.

## Constraints and evidence

Reuse `loop_quantities`, native k0 conversion, reviewed VT/CT impedance conversion
and exact `Characteristic.contains`. Never use phase/earth fallback or polygon
approximations to determine mho containment. Keep the existing E5/estimator/DSP
algorithms, source bytes, parser, line schema, jobs and historical results.
No line model, remote record, source impedance, GPS, tower or relay-distance
input is needed solely for this local geometric comparison.

Require an associated actual settings hash, current source/mapping-bound review,
reviewed settings identity/event-time/scaling/polarity and settings-base CT/VT
ratios. Ground loops also require native compensation, reviewed zero-sequence
transfer and no contradictory detected VT evidence. Use supported full-cycle
operational windows; refuse gaps/multi-rate, invalid/nonfinite support, saturation,
clipping and detected mixed-state transitions. Preserve inconclusive transition
screening as a limitation, without inventing a new settling criterion.

The bounds of 4,096 evaluated phasor supports and 32 exported zones are software
work limits; the existing 1e-6 A display-current floor is numerical policy.
Oversized support is explicitly unavailable, never silently thinned. Counts are
overlapping phasor supports, not independent measurements or confidence coverage.

IEEE C37.114-2014 remains the source for the existing fault-loop definitions;
COMTRADE interpretation remains under IEEE C37.111-2013 / IEC 60255-24. This
feature makes no new standards-conformity claim or invented clause citation.
Exported boundary containment does not establish enablement, pickup, timer
expiry, scheme behavior or correct protection operation. FL-01–03 and overall
compliance remain unassessed; no generic reach/time substitutes are introduced.

## Phases and done checks

1. **P1 backend model:** add `report/zone_comparison.py` and independent numerical/
   refusal tests. Exact polygon/mho containment and phase/earth identity agree
   with simple geometry and synthetic known circuits. Supported zero k0 stays
   valid; missing k0 stays unknown. Outputs serialize as finite JSON.
2. **P2 integration and simple presentation:** add the same object to navigator
   R–X evidence and matching relay evidence; render it below existing R–X views
   and in the technical report/annex, with a short source-matched report note.
   Reuse existing inputs; add no menu or duplicate form. Refusal states do not
   hide raw/phase views or block E5. Old stored results load unchanged.
3. **P3 qualification and delivery:** prove UI review→comparison, missing/stale/
   ambiguous-settings refusal and immutable revision history on desktop/mobile.
   Run direct architecture/self-tests, changed Python lint/JS syntax, full pytest
   and Stage-A10,000; document inherited lint/private-data limits, commit phases
   and push only the authorized review branch, verifying remote HEAD.

## Data and validation

Persist an additive `zone_comparison.version=1` under existing per-record
evidence. It describes a conditional model projection, not the previously
removed `zone_expected` or protection compliance. No migration, implicit
recomputation or rewrite of old reports is performed. New revisions use their
own frozen source/settings/review inputs.

Tests cover known AG/BG/CG and phase fault loops, differing ratios and rotations,
inside/outside/mixed, exact mho versus display outline, wrong/missing kind,
invalid geometry/compensation, missing/stale sources/settings/mappings/review,
empty/short/half-cycle/gapped/nonfinite/zero-current/saturated/clipped/oversized
windows, transition evidence and finite serialization. Integration covers
corroborating-record isolation, late/ambiguous settings, source selection and
unchanged E5=41.98828243177587 km for the existing known42km demonstration.

The established baseline is 2,094 passed, 28 private-data skips; architecture,
Stage-A10,000 and desktop/mobile verification passed on the preceding unchanged
runtime. All26 inherited whole-repository lint findings are in untouched files.
Expected numerical step: new geometric comparison only; location estimates do
not move. Field accuracy and true settings applicability require external facts;
synthetic declarations never become authenticated site evidence.
