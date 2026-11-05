# Parse setup and report clarity acceptance

5November2026, Asia/Calcutta. Branch `codex/operator-ui-review`, baseline1123cb4.
[Plan](PARSE_REPORT_CLARITY_PLAN_v1.md), [checkpoint](PARSE_REPORT_CLARITY_CHECKPOINT.md).
Final runtime `f2aaaf42f7618cdd387813cc867b0d8f0f5b4231`; report/source logic is
unchanged from fully tested `16e83e7`. Final follow-ups change Setup CSS only.

Publication **PUBLISHED**: normal review-branch delivery
`5f2ce1557f06af31c2ec239cc0e96ab3872f8789` pushed and remote HEAD verified exactly.
This documentation closure leaves runtime unchanged. Private data stayed local.

## Result

Upload/parse now opens **Setup** before Analyse. Parsed recording names and known
CFG instrument declarations appear first. Missing phase ratings use one common
CT primary/secondary pair and one VT/PT pair per recording, with optional channel
exceptions. Valid existing declarations and already-primary samples are retained;
no voltage-based CT guess or shared ratio across opposite ends is assumed. Saves
use the same logical recording and immutable input revisions, preserving original
bytes, previous reports and other unsaved recording/line drafts.

Enter line length, impedance/units and physical-end facts in the same Setup.
A separate model file is not required. Analyse shows saved facts and links back
to Setup; duplicate line forms and empty primary model selectors are removed.
Registry/model and independent projection controls remain secondary engineering
interfaces. Existing fault-type/window detection is automatic for usable input;
there is no manual assumed-loop choice in the primary physical calculation.
Line geometry/impedance usually cannot be recovered from a DR. All existing
rating, physical-end/event/polarity, model applicability and method gates remain.

New four-page report generations have clearer screen layouts, matching phase
scales around zero, explicit current/voltage prefixes, and separate instantaneous
versus RMS descriptions. Event detail uses actual native samples around a selected
or detected observation interval, with two cycles of context only when declared
frequency is valid. Dense traces retain a labelled bounded sample envelope; gaps
remain unknown. This display focus never shortens or changes DSP/RMS windows.
Full-record overview remains available; source-local clocks are not synchronized.

Hover/touch/keyboard readouts name actual retained sample indices/times/values;
there is no interpolation or fabricated peak. RMS cells expose precise values,
units and basis. Print always selects event detail and hides interactive controls.
Eligible source-bound stored classification can appear even when distance is
unavailable; stale/partial/unsupported/disagreeing source evidence cannot become
a forced fault type or loop. No new classifier or numerical estimator was added.

Existing generated HTML/JSON stays immutable. The new presentation appears in a
new report generation after updating the application. The user's localhost8098
URL was unreachable from this workspace; screenshots and saved fixtures were used,
without claiming to edit that existing generation.

## Actual qualification

- Full pytest on frozen source/report logic16e83e7: **2438PASS,28private-data skips,
  1inherited warning**,105.16s. Final Setup CSS has focused23PASS,3.25s plus final
  desktop/mobile browser checks below; no later Python/JS/numerical logic change.
- Direct architecture/self-test, changed10Python Ruff/18JS syntax and diff PASS.
  Exact changed/new Python budgets only; guard unchanged. Whole Ruff retains26
  inherited findings in untouched files.
- Fresh Stage-A10000 **PASS**,cleanp95 **.4361%**,zero impossible distances without
  caveat,45.3s. Native DSP/estimator/oracle files unchanged. Known42 E5 remains
  exactly **41.98828243177587km**, with source primary samples preserved.
- **7/7workflow checks**: parse Setup/common ratings, same-record save/draft
  retention, distinct end ratings/primary no-rescale, line setup/automatic native
  calculation/Compare, reference inputs, classification variants and read-only
  private-record inspection. Zero page errors; original files/history preserved.
- Final CSS-onlyf2aaaf4 **2/2desktop/mobile checks**: all confirmation text stays
  in its card,18px checkboxes toggle by label click, units stay inline and evidence
  fields span the form.1440px/390px views visually checked; no clipping/overflow.
- **5interactive HTMLs**:780exact sample readouts(624keyboard/102pointer/54touch),
  162precise RMS cells,16focus/overview pairs,12gap refusals,18touch persistence/
  clear and34mouse-leave cases. Zero external requests/page errors.
- **7fresh Chromium PDFs /28A4pages**, each exactly4pages. All28pages visually
  reviewed; no scroll/text/PDF clipping, footer overlap or overflow; minimum9pt.
  Earlier3renderer smoke PDFs each also passed4A4 including long aliases.
- Wheel rebuilt with exact final report JS/template and Setup JS/CSS assets.
  All18runtime hashes match. Independent code/evidence/privacy review PASS.
  All owned QA servers stopped; old goal automation stays paused; none created.

These are software/synthetic qualifications, not field-accuracy evidence. Private
real inputs retain unresolved facts and unavailable distance; no CT/VT, line,
loop, end, event or clock facts were invented. Original private app/history remain
unchanged. Real physical answers are still pending under the earlier real-input
checkpoint. No real files/settings/source hashes/private reports were committed.

## Evidence and milestones

[Sanitized evidence](PARSE_REPORT_CLARITY_EVIDENCE_2026-11-05.json).
Local ignored root `work/qa-parse-report-clarity-2026-11-04/`: final-pytest.log,
final-setup-tests.log, stage-a.log/csv, runtime-manifest.json, wheel-final.log,
browser/qualification.json, interaction-print-summary.json, setup-visual-results.json
and setup-visual-final.log. Final geometry result names exactf2aaaf4; the earlier
a40e65f visual result and initial scratch failures are superseded. Report checks
remain tied to unchanged16e83e7 source; final qualification combines these parts.

P0 `3061519`; P1 Setup `494de5e`; P2 canonical evidence `3164884`; P3 renderer
`16e83e7`; final visual corrections `a40e65f`/`f2aaaf4`. Platform usage limits
interrupted helpers; explicit user continuations resumed preserved work. No work
during interruptions is claimed. No main merge, deployment or environment publish.
