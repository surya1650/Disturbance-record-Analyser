# Setup reuse and signal report acceptance

5November2026 Asia/Calcutta; branch `codex/operator-ui-review`, baseline57d0aec.
[Plan](UNIFIED_ANALYSIS_SIGNALS_PLAN_v1.md), [checkpoint](UNIFIED_ANALYSIS_SIGNALS_CHECKPOINT.md).
Final runtime `f4811e31953a2590ffc641e0f3288234326ebd95`. Source/JS/Python logic
is unchanged from tested e303e87; final follow-up is two template CSS lines only.

## Result

Analyse reuses incident-local Setup line/end selections and saved confirmations;
no duplicate local-model or end selectors. It checks authoritative source-bound
missing inputs before queueing and links directly to Setup. Current direction is
explained as the recorded sign reference, not AC power-flow direction. A single
explicit standard-wiring action fills existing sign fields for selected records
only: P1bus/P2line, S1relayI+ and uninverted exports must be declared. S2 common
alone is not proof of exported polarity. Unknown stays unknown, a changed source
resets its sign, and reverse export remains an advanced per-end choice. No new
metadata schema, sample mutation, guessed ratings or automatic inversion.

Event views reuse exactly bound Setup recordings/names/same-event review and
automatic timings; existing saved event choices take precedence. A single source
at either end remains at that physical end. R-only reports load/build without
remapping R to S or inheriting a stale pair confirmation.

Optional relay readings now name missing or invalid fields. Incomplete readings
remain editable, with exact draft text retained through build/source switches;
they are visibly excluded while the observation report still builds. A sourced
zero is valid. Backend validation stays strict; no source is invented, and relay
readings remain separate from calculated location.

New reader reports have compact offline cursor tables for phase values, source-
local sample time/index and digital state. Assertions use explicit polarity
review only; unreviewed signals show raw high/low. Gap/transition/omitted support
stays unavailable. Window activity and sampled duration brackets retain unknown
support and boundary censoring; these are not physical relay/breaker times.
At most4 selected digital signals are summarized; omissions remain explicit.

Recorded CFG start/trigger dates/times appear separately from generation time.
Valid local timestamps preserve fractional precision; invalid strings stay visible
without guessed dates. Timezone/common-clock quality and absolute cursor anchor
are not fabricated. Cursor readings use actual source elapsed time. Earlier
models have honest fallbacks; old generated reports/original files are immutable.

## Actual qualification

- Full pytest on frozen e303e87 logic: **2470PASS,28private-data skips,1inherited
  warning**,102.67s. Final template-only layout fix has **54focusedPASS**,1.48s,
  and actual browser/PDF checks. No later Python/JS/numerical changes.
- Direct architecture/self-test, changed13Python Ruff/13JS syntax and diff PASS.
  Exact changed/new budgets only; guard unchanged. Whole Ruff retains26 inherited
  findings in untouched files. Wheel final template/JS/digital/time assets match.
- Fresh Stage-A10000 **PASS**,cleanp95 **.4361%**,zero impossible distances without
  caveat,48.2s. Native engines/oracle unchanged. Known42 E5 remains exactly
  **41.98828243177587km**, with primary source samples and history preserved.
- **7actual workflow checks** passed: standard-sign declaration/reset/override,
  missing/stale readiness, canonical selectors/confirmations, event prefill/timing,
  nonblocking relay drafts and zero, R-only reuse, native result and private
  read-only inspection. All owned servers stopped; original private app unchanged.
- **5offline reports/10device contexts**:792exact analog rows,976digital cursor/
  window rows,56static signal rows;192keyboard,24pointer,24touch,24gap/transition,
  108unknown-state refusals,24touch-hold/clear and24mouse-leave cases. Zero external
  requests and page errors. Actual cursor/Setup desktop/mobile visual review PASS.
- **5fresh Chromium PDFs /20A4pages**, each exactly4pages; minimum9pt. No footer
  overlap, sheet/PDF text clipping, horizontal overflow or errors; visual audit
  PASS. Final long source names wrap; print suppresses cursor tables/controls.
- Independent final engineering review PASS. All12runtime hashes match the final
  manifest. No private physical inputs invented, old report generations unchanged.

The first final print matrix exposed a real5page/overflow issue that the earlier
small smoke missed. The final CSS correction preserves fonts and all evidence;
fresh affected cases and the complete final matrix passed. Initial failed metrics
and harness attempts remain archived, not represented as final evidence. The
mobile touch discrepancy was a QA visual-viewport coordinate issue, corrected
after removing actual long-heading overflow; no cursor logic workaround was used.

## Evidence and scope

[Sanitized evidence](UNIFIED_ANALYSIS_SIGNALS_EVIDENCE_2026-11-05.json).
Ignored root `work/qa-unified-analysis-signals-2026-11-05/`: final-pytest.log,
foundation-tests.log, event-r-only-tests.log, final-layout-tests.log, stage-a.log/csv,
runtime-manifest.json, wheel-final.log, browser/final-qualification.json,
workflow-results.json, offline-results.json and pdf-qualification.json. Use final
PDF counts/metrics; first-print-matrix-summary.json is retained failure history.

P0 4e5e76c / P1 cf73e53 / P2 21025d0 / R-only06f40cb / renderer e303e87 /
layout f4811e3. Platform limits interrupted renderer/QA; user continuation resumed
preserved edits at12:35IST5November. No work during the pause is claimed. No main
merge, production deployment, environment publication or new automation. Prior
owned continuations stay paused. Private sources/settings/hashes/reports remain
local; qualifications are software/synthetic checks, not field accuracy claims.
