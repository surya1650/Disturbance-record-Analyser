# Automatic window and line-reference checkpoint

Plan: [AUTO_WINDOW_LINE_REFERENCE_PLAN_v1.md](AUTO_WINDOW_LINE_REFERENCE_PLAN_v1.md).
Branch `codex/operator-ui-review`, baseline `c1b2a88`.
State: **IMPLEMENTING — window selection frozen, reference integration active**.
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

Earlier workers hit a platform usage limit; the user's continuation resumed their
preserved local edits. Work during the limit is not claimed. Required real CT/VT,
line/end/association facts remain pending in the prior real-input checkpoint.
