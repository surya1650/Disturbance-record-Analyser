# Operator UI and simple report review

Continuation on published base `f52911e`, preserving the earlier channel-comparison
draft. Plan: OPERATOR_UI_REPORT_PLAN_v1.md. No environment configuration changes,
commit, push or publication were performed.

Subsequently the user authorized a GitHub push for review. Branch
`codex/operator-ui-review` adds the checked Codespaces launcher on port 8098.
Six launcher checks plus the focused UI/model suite pass (15 tests total), including
exact-host handling, invalid-configuration refusal, isolated data and restart
idempotence. No merge to main or cloud-environment publication is performed.

## Review findings and delivery

| Finding | Result |
| --- | --- |
| One long page mixed inspection, inputs and diagnostic evidence | Five task panels: Waveforms, Simple report, Inputs & help, Compare recordings, Technical evidence |
| Left channel rail reduced waveform space | Collapsed channel controls above plots; larger analog viewport and 140 px traces |
| Optional study/history competed with source inspection | More tools disclosure retains operational assignments, saved report, inventory and revisions |
| Required inputs were unclear | Six feature cards explain purpose, required inputs, limitations, availability and next action |
| Line inputs looked necessary for any inspection | Optional line-model disclosure; raw-inspection independence and missing-CT assumptions explained |
| Basic report information competed with technical detail | Region table, distance, analog changes and digital indications lead the report; technical provenance expandable |
| Separate representations could drift | One serialized `simple_report` model used in live report, JSON and printable HTML |
| Narrow-screen report cells became too dense | Readable table widths with contained horizontal scrolling, keyboard focus and unavailable-reason disclosures |
| Navigation could accept a delayed prior-page response | Route generations and cancellation prevent stale detail responses from reclaiming the active page |

Spacing, borders, typography, focus states and status labels are consistent. Tabs use
WAI-ARIA roles, roving focus, Arrow/Home/End operation, and one visible panel. Decorative
transitions respect reduced-motion preferences. These are design/accessibility
practices, not an assertion of certified WCAG compliance.

## What the operator does

1. Upload matching source files and choose a recording. Waveforms are available
   before operational assignment or a successful calculation.
2. Use Inputs & help for the intended feature. Each card says what it does, what it
   needs, why it is limited and where to go next. Line inputs are optional for raw
   inspection. Additional method prerequisites remain explicit.
3. For regional comparisons, put A at fault start and B at post-fault start on
   Waveforms. In Simple report, apply Compare A–B conditions. Pre-fault is `[0,A)`,
   fault `[A,B)`, post-fault `[B,end)`. These are operator selections.
4. Read supported median fundamental RMS values by region, with original analysis
   units and assumptions. A missing fit remains unavailable with its reason. Moving
   cursors does not silently change an already applied selection.
5. Read the distance method and reference. A stored incident estimate identifies
   its selected records; it is separate from a conditional source line projection.
   Missing facts, methodless projections and outside-line results remain explicit.
6. Read literal analog changes and recorded trip/AR indications. Asserted-state
   polarity and missing digital meanings remain visible. Trip commands do not prove
   physical CB opening or actual clearing time.
7. Download HTML/JSON, or open Technical evidence for the detailed windows and
   provenance. The report belongs to the incident's selected recording; this does
   not turn independent captures into authenticated opposite ends.

## Verification

| Check | Result |
| --- | --- |
| Architecture self-test / direct guard | PASS |
| Changed JavaScript syntax | PASS |
| New Python test wrappers / Ruff | PASS |
| Full Ruff | 40 pre-existing findings in 22 files, all unchanged from HEAD |
| Full pytest | 1792 passed, 28 absent-private-corpus skips, one existing Starlette warning |
| Stage-A 10,000, seed 0 | PASS; clean p95 0.4361% |
| Known-m synthetic CLI | Actual 42 km; E5 41.988 km; method table and E4 clock gate retained |
| Chromium desktop / mobile | PASS at 1520/1280 and 390 CSS px; no page errors or page-width overflow |
| Keyboard / reduced motion | PASS; one active panel, arrow activation, visible focus, no decorative animation under reduced motion |
| Download execution | Actual JSON and HTML downloads inspected; shared selection/model and leading simple report verified |
| Supported regional values | Six phase channels have supported pre/fault/post values in the 2400-sample synthetic case; neutral fits retain specific unavailability |
| Partial/failure paths | Four-sample and missing-DAT sources retain clear reports; diagnostics 503 clears stale results/downloads while raw waveforms remain usable; delayed navigation cannot replace Overview |
| Cross-panel actions | Distance help opens its input disclosure; technical-window inspection returns to Waveforms before focusing samples |

The final full-suite rerun passed in 143.64 s. The two final cross-panel action
adjustments were then checked with JavaScript syntax, the architecture guard and
the full Chromium operator/download scenario (`browser-final.log`).

Evidence and repro scripts are local and ignored under
`out/qa/operator-ui-2026-10-29/`: browser logs, screenshots, downloaded reports,
synthetic sources, failure checks, Ruff JSON, pytest logs, CLI and Stage-A output.
No private field captures were added. Pure tests cover units, null versus zero,
active-low indications, ambiguity, method/reference handling, outside-line values,
bounded digital detail, escaping, source immutability and report/export consistency.

## Reliability and scalability boundary

No parser, estimator, source-time policy, physical scaling policy, database or line
calculation changed. Existing four-cycle/stationary fitting requirements remain.
Short/transient intervals can therefore legitimately lack region values.

This change reuses bounded API results and adds no per-frame requests. The simple
report retains every analog and limits its digital detail to 12 relevant rows, with
remaining evidence explicitly counted and accessible. Existing channel/sample/job
limits and source-cache/transport guards remain in force. Previous 128-channel
comparison qualification remains documented separately.

This is still the local application with SQLite/files and its existing worker model.
Authenticated multiuser hosting, tenant isolation, horizontal workers/object storage,
fleet ingestion/load testing and recovery/backup operations have not been built or
qualified by a UI change. Broad browser/device/accessibility testing and actual OS
printing remain outstanding. Physical ratios, wiring, clock/event/terminal identity
and relay/line settings require asset evidence. No universal relay compatibility,
field accuracy or 'foolproof production' certification is claimed.

Applied source-region selections and feature choices remain browser-session state;
downloads carry the selected snapshot. Reloading is not a server-side saved review.
Stored incident revisions and operational reports retain their existing persistence.
