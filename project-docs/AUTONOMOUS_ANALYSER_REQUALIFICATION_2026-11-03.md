# Autonomous analyser continuation — 2026-11-03

Branch: `codex/operator-ui-review`. Starting remote HEAD: `084ede6`.
Contract: [autonomous analyser plan](AUTONOMOUS_ANALYSER_GOAL_AND_PLAN_v1.md).
The requested branch already contains the P0–P6 implementation and later
source-first/comparison fixes. This continuation verifies that delivery and
corrects demonstrated gaps; it does not repeat the implementation.

## P0 — fresh baseline

Direct architecture guard and self-tests passed. Full pytest: **2,037 passed,
28 skipped**, one inherited Starlette/httpx deprecation warning, 98.88 seconds.
The skips need unavailable private records; no private captures were supplied
or inferred in this environment. Stage-A **10,000 PASS**, clean p95 **0.4361%**
of line length, zero impossible distances without a caveat. Repository-wide
Ruff has **34 inherited findings**; this is an explicit failed baseline gate.

Disposable application data, synthetic fixtures, logs, browser harnesses and
screenshots are under `work/qa-2026-11-03/`; browser port is 8137. Existing
application roots and stored incident history are not used for this check.

| Preserved contract | Fresh verification |
| --- | --- |
| Recoverable source waveforms without physical declarations | Desktop/mobile UI upload; eight analogs and recorded digitals |
| One-cycle RMS, shared cursor and vectors | Browser cursor/RMS plus full cursor/Fourier regression suite |
| Automatic/manual source intervals and source bindings | Full event/region/concurrency regression suite |
| Universal CT/VT reviewed copies | Full instrument-review and input UI regression suite |
| Comparison playback and changed-first digitals | Desktop/mobile comparison; existing lifecycle/known-gap tests |
| Primary calculation and structured location | Desktop/mobile E5 calculation with positive-sequence-only model |
| Simple report and HTML/JSON | Matching method/reference, source provenance and explanations |
| Stored R–X/full-line context | Browser source navigator and declared 100 km line |
| Immutable old revisions and late remote attachment | Full stored-summary/worker/revision regression suite |
| Single-ended methods and named refusals | Full engine, optional-zero-sequence and application suite |

## P1 and P5 — capability and availability audit

The current UI correctly describes one-cycle measurements, optional display
labels, method-specific physical inputs and separate physical-end confirmation.
Raw inspection asks no line questions. Same-relay successive captures remain
ineligible as opposite physical ends. Focused guidance/assignment/ratio tests:
**31 passed**, one inherited warning.

README still advertised a joined viewer and mandatory substation labels. It now
matches the existing inspect/compare flow and optional labels. Same-relay joining
and joined COMTRADE export remain unavailable, using the plan's explicit P5
completion option. No gap is filled or unknown digital state manufactured.
NEW_CHAT_START now directs future sessions to the actual delivered phase status.

## P2 and P3 — location and protection evidence

Fresh desktop/mobile UI calculation for the unchanged known-42-km synthetic
case returns **E5 = 41.98828243177587 km from S**. The registry deliberately
omits Z0/source impedances: E5 remains eligible, while unrelated ground-loop
methods state their missing inputs. Clock evidence is absent, so E4 refuses.
The line/source/input/revision hashes and finite structured result survive
matching report exports. No estimator equation or synthetic oracle is changed.

The audit reproduced FL-02 declaring incorrect operation with an explicit Z2
indication and a 0.42 pu location but **no actual zone settings**. FL-01 similarly
used a generic reach. FL-03 used an unqualified apparent-loop/settings comparison.
These are not established protection compliance checks. New rule assessments
preserve recorded indications and numerical location without claiming
correct/incorrect protection operation from those assumptions. FL-01–03 now
remain explicitly not evaluable with named settings/loop/scheme reasons.
Generic CB/AR timing screens keep their thresholds and are labelled project
policies, not actual breaker specifications or relay settings. AR lockout,
definitive-trip and backup pickup observations no longer prove physical
reclosure, permanence, reset or grading. Twelve focused regressions cover
these boundaries; the first seven failed before the correction. Broader
P2/P3/API/rules/report checks: **112 passed, 8 private skips**, one inherited
warning. The correction is committed as `f970ea6`.

A P3 follow-up (`9cb2314`) also withholds the legacy VA-only expected-zone
projection, which treated missing ground compensation as zero and could display
a computed zone for the wrong fault loop. Existing feature keys remain present
as unknown, with `zone_expected_reason`; CLI output names that reason. Four
AG/BG/phase/missing-compensation cases failed before the fix, then passed.
Focused boundary/settings/rules/backtest checks: **49 passed, 12 private skips**.
Reviewed R–X inspection remains a separate display function; establishing zone
compliance still needs applicable settings, supported loops and scheme evidence.

New stored incident results use `rule_assessment_version=2`, and new technical
HTML carries the matching marker. Version 2 rollups describe adverse findings
requiring review, not protection compliance. Results without that marker are
legacy evidence; this continuation does not rewrite or recompute their HTML,
JSON, revisions or original bytes. `location_summary.version=1` retains its
existing meaning and exact numerical result.

## P4 and P6 — browser scope and delivery

P4 correction is committed as `eb6ae38`. The older technical report could draw
120 ground-loop points without native compensation/review, substitute a phase
characteristic for an absent earth characteristic, and crash on a vendor-neutral
mho characteristic. It now reuses `phase_loops`, `display_context` and
`zone_outlines` from the existing navigator. The adapter matches the primary
source hash/end/role and actual settings hash, then revalidates current mappings
and reviewer declarations. Serialized derived k0/scaling cannot unlock a plot.
Valid phase views remain available without unrelated settings questions.

New technical plots use explicit primary-ohm axes and
`data-rx-display-version=2`. Ground compensation and exact phase/earth boundaries
stay conditional on the existing review contract. Missing points break paths
and clear the last marker; missing angles do not get an invented direction.
Unsupported loops/settings have named reasons. Malformed oversized CT/VT values
are rejected as input errors rather than causing exceptions. Legacy report
files retain their original units and bytes. Focused report/navigation/input
checks: **99 passed, 1 private skip**, one inherited warning.

Baseline Chromium at 1440×1000 and 390×844 passed primary upload, raw inspection,
one-cycle cursor/RMS, comparison, calculation, report/export and stored R–X flow.
Rapid source changes and leaving the route caused no page errors; mobile had
no document overflow. The full declared line is shown with an eligible location.

Bounded capacity fixture: **64 analogs, 12 digitals, 20,000 samples**, 1,520,000
source cells; ASCII DAT 6,451,781 bytes. All 64 analogs and 12 initial digital
tracks rendered. First visibility was 6.40 seconds; sampled JavaScript heap was
9,664,695 bytes. Desktop/mobile and route exit during an RMS request passed.
These observations exclude total server/native/browser memory and do not
establish unbounded or production multiuser capacity.

Final runtime code is frozen at `eb6ae38`. Commit `9520795` updates the existing
relay-difference warning-ordering test to expect the new findings heading. The
first complete final run caught that stale assertion (2,093 passed, one failed,
28 skipped); the six focused application tests then passed. No runtime change
followed browser/Stage-A qualification, and the complete suite was rerun.

Frozen-code Chromium verification passed with a freshly restarted disposable app.
Desktop calculation again returns **E5 = 41.98828243177587 km from S**. Simple
report HTML/JSON agree; full-line and source-local navigation work. Technical
HTML has both version2 markers, neutral findings, named FL-01–03 abstentions,
project-screen timing wording and unavailable AG trajectory reasons when the
associated settings/review/zero-sequence evidence is missing.

Mobile calculation creates revision2 while retaining revision1 unchanged.
Automatic→manual interval→save/reopen→automatic→save/reopen, comparison
playback/pause/reset/hidden-pane stop, vector reference changes, rapid source
changes and route cancellation passed. The frozen-code ratio-copy test rejects
missing/zero ratios, then previews/downloads/saves explicitly known synthetic
universal CT/VT ratings. Original/DAT hashes and revision history remain intact;
the reviewed copy opens on mobile. No page errors or mobile document overflow
were observed. Browser capacity measurements above are from `084ede6`; the
source viewer modules were unchanged by these report/rule corrections.

Browser-owned port8137 was stopped after qualification; disposable data and
harnesses remain in `work/qa-2026-11-03/browser/frozen/`. No private application
root or prior preview process was replaced.

Direct final architecture guard/self-tests pass. Changed-file Python Ruff and
JavaScript Node syntax pass. Repository-wide Ruff remains **26 inherited
findings in untouched files**, down from the fresh baseline's 34; it is still
a failed whole-repository lint gate. `git diff --check` passes. A mistaken
Python-lint invocation on JavaScript was replaced by the appropriate Node check;
its output is not a source defect or a passing lint result.

Final Stage-A **10,000 PASS**: clean p95 **0.4361%**, zero impossible distances
without a caveat, 58.4 seconds. The unchanged synthetic oracle and numerical
estimators were used. Complete final pytest: **2,094 passed, 28 skipped**, one
inherited Starlette/httpx warning, **77.55 seconds**, on `9520795` (runtime
`eb6ae38`). Private-corpus skips remain unqualified. No further runtime or test
changes followed these checks.

Phase ownership: root ran baseline/final gates, reviewed/integrated commits and
owns documentation/delivery; readiness_audit handled P1/P5 audit and P4 adapter;
engine_report_audit handled P2/P3 evidence review and corrections;
browser_qualification handled isolated synthetic desktop/mobile/capacity checks.
All agents finished before delivery. Local `work/` QA is ignored;
no generated records, application databases or browser outputs enter Git.

P0–P6 review is complete within the documented software/synthetic scope.
P1 guidance (`867211a`), P3 evidence (`f970ea6`, `9cb2314`, test follow-up
`9520795`) and P4 R–X (`eb6ae38`) are independently committed. The P6 documentation
commit records final evidence and updates the next-session/lesson/goal ledger.
Review-branch push and exact remote HEAD verification are performed after that
commit and reported in the delivery response. Whole-repository lint, actual
zone compliance, same-relay joining/export and private field qualification retain
the explicit limits above; no hidden implementation or approval step is pending.

No authenticated opposite-end field pair, patrol truth, calibrated uncertainty
or deployment scale is established. Site facts are needed only when a specific
physical analysis depends on them. Old reports and original bytes remain
immutable. No main merge, environment publication or production deployment is
part of this continuation.
