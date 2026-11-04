# Automatic windows and published line-reference acceptance

Branch `codex/operator-ui-review`; qualified runtime
`8c3909c0d81b87fd4e00860de056ebc157043e17`.
Plan: [AUTO_WINDOW_LINE_REFERENCE_PLAN_v1.md](AUTO_WINDOW_LINE_REFERENCE_PLAN_v1.md).

## Result

The main physical engine already detects the disturbance and selects its native
analysis window automatically. The separate technical source-projection panel
now also defaults to automatic selection: reuse the detector, then pick an already
eligible fit wholly inside its bounded fault interval, nearest the interval centre
with deterministic ties. No capture-first/max fallback, shortening, gap repair,
loop inference or plausibility-based distance selection. Short/no-event/missing-
model/raw-counts/unsupported-ground cases retain named refusals. Manual override
stays secondary with support provenance and outside-interval warning; declared
gaps remain refused. This display policy is not a new standard or operational
eligibility rule. No DSP/estimator/oracle code changed.

One explicit optional reference is offered for 132 kV Single Panther S/C:
R1=.1622, X1=.3861 ohm/phase/km, from the later Powergrid4Nov2015 table in
[ERPC31st minutes, printed36/PDF39](https://erpc.gov.in/wp-content/uploads/2016/08/145216645131ERPCTCCMINUTES.pdf#page=39).
It is general published reference data, not a universal standard or an actual line
measurement. Geometry, temperature, frequency, transposition and earth conditions
are unstated; an earlier table differs. Only this verified single-circuit reference
is selectable; other configurations use approved manual data.

No voltage-based selection occurs. Explicit Apply fills kV/basis/R1/X1 as a draft;
actual length, physical ends, instrument facts and other inputs stay supplied by
the operator/source. Applying across incompatible units refuses when any R0/X0 is
populated, including zero; nothing is silently converted/deleted. Reference
applicability and line confirmations must be reviewed before use. Unreviewed
references block physical calculation and advanced projections while observation
reports remain usable. Manual electrical edits remove the reference label.
Backend validation rejects altered constants/sections under that label. Frozen
report JSON retains source and applied-positive-sequence scope; four-page reports
state review status and that these are not measurements.

Legacy projection controls live under Supporting measurements and technical
exports. Primary flow stays Upload/parse → Analyse → Compare(optional) → Report.
Manual review shapes, original bytes, names, history and all gates are preserved.

## Actual verification

- Final full pytest: **2403PASS,28private-data skips,1inherited warning**,92.71s.
- Direct architecture/self-test, changed16Python Ruff,9JS syntax and diff PASS.
  Only changed/new Python growth budgets updated exactly; guard unchanged.
  Whole Ruff retains26 inherited findings in untouched files.
- Stage-A10000 **PASS**,cleanp95 **.4361%**,zero impossible distances without a
  caveat,77.7s. Known42 native E5 remains **41.98828243177587km** with unchanged
  primary samples; matching-reference synthetic132E5=41.98108149626168km.
- Browser **10/10PASS**,zero page errors: automatic/manual selection, short/no-
  event refusal, unchanged result, reference preview/Apply, unit guard, save/reopen,
  applicability gates, source-labelled report, manual invalidation and read-only
  private-record inspection. Desktop/mobile390px fit, including reference controls.
- **3fresh Chromium PDFs /12A4pages**, each exactly4pages: native known42,
  unreviewed reference and reviewed reference. No scroll/text/PDF clipping,
  horizontal overflow, footer overlap or blank pages. Minimum print12px/9pt.
  All4 reviewed-reference pages visually checked; citation readable.
- Independent review found the unit issue and verified its fix; final review has
  no outstanding actionable finding. All16 runtime hashes match after
  qualification. All owned servers stopped; no new automation created.

These are software/synthetic qualifications, not field-accuracy evidence. Private
records retain unresolved scaling/physical facts and unavailable distance. No
line reference, CT/VT, loop, end, event or clock facts were invented. Original
private application/history remain hash-unchanged. Actual engineering answers
remain pending under the prior real-input checkpoint.

## Evidence

[Sanitized JSON](AUTO_WINDOW_LINE_REFERENCE_EVIDENCE_2026-11-04.json).
Ignored local root `work/qa-auto-window-impedance-2026-11-04/`: `final-pytest.log`,
`stage-a.log/csv`, `review-fixes-tests.log`, `runtime-manifest.json`, final
`browser/qualification.json`/`qualification-summary.md`, three `*-print-qa/`
metrics/PDFs. Initial browser `results.json` contains a superseded scratch
containment failure; final qualification combines completed synthetic/read-only
runs. Private uploads, settings, hashes, content and timing/measurements are
excluded from public evidence. Old goal continuations stay paused. No main merge,
environment publication or production deployment.
