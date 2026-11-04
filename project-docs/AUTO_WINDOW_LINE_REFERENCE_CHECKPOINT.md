# Automatic window and line-reference checkpoint

Plan: [AUTO_WINDOW_LINE_REFERENCE_PLAN_v1.md](AUTO_WINDOW_LINE_REFERENCE_PLAN_v1.md).
Branch `codex/operator-ui-review`, baseline `c1b2a88`.
State: **IMPLEMENTED — FINAL QUALIFICATION ACTIVE**.
Publication: **NOT ATTEMPTED** for this new payload.

Existing completed goals/publication remain preserved. Old writer leases are
completed or waiting for real engineering answers; no independent active writer
was found. This root coordinates disjoint UI/report helpers under the ignored
`work/qa-auto-window-impedance-2026-11-04/active-writer.json` lease.

Automatic projection selection now reuses the existing source fault detector,
selects only an eligible native fit wholly within the bounded detected interval,
retains outside-line caveats and refuses insufficient/gapped/no-event support.
Advanced manual provenance is retained; a declared gap remains refused. No DSP,
operational selection thresholds or minimum support lengths changed.
Focused125 tests passed,2.35s,1 inherited Starlette warning; Node input/report,
changed-file Ruff, diff and direct architecture checks passed. Full qualification
is pending and these focused results do not replace it.

Published catalogue evidence: latest Powergrid4Nov2015 single-Panther SC row in
[ERPC31st minutes, printed36/PDF39](https://erpc.gov.in/wp-content/uploads/2016/08/145216645131ERPCTCCMINUTES.pdf#page=39):
R1=.1622, X1=.3861 ohm/phase/km. Exact tower geometry/temperature/frequency are
not given. Earlier table differs; no universal standard is claimed. Five catalogue
tests and changed-file lint passed. Explicit draft/review UI/backend/report
integration and final checks are next. No private physical facts have been filled.

## Implementation milestone

P1 `47fcced`: automatic source-projection support and secondary manual override.
P2 implementation is frozen locally: explicit source-labelled reference draft UI,
strict matching constants and applicability gate, frozen report provenance and
manual fallback. Legacy independent projection controls now live under collapsed
technical details; the primary physical calculation explains automatic detection.
Existing manual review shapes and frozen historical provenance remain unchanged.

Focused integration96PASS,2.64s,1 inherited warning. Reference applied to mismatched
synthetic220kV captures correctly stays blocked by native conformance despite user
applicability review; no gate is weakened to produce a number. Source/report
focused59PASS; catalogue5PASS. Changed15Python/9JS lint/syntax and direct guard/
self-test/diff PASS. Only changed/new Python growth budgets updated exactly.

Full pytest, Stage-A10000 and actual browser/PDF checks are running. No final
counts, PDF page counts or completed qualification are claimed yet. Final source
commit/checkpoint, sanitized evidence and publication decision follow those checks.

Earlier workers hit a platform usage limit; the user's continuation resumed their
preserved local edits. Work during the limit is not claimed. Required real CT/VT,
line/end/association facts remain pending in the prior real-input checkpoint.
