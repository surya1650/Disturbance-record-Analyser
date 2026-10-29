# Autonomous analyser: goal and implementation plan v1

Date: 2026-10-30 (Asia/Kolkata). Runtime baseline: `58ce8eb5d73032db4028aef9b8e7510eebffd424`
on `codex/operator-ui-review`. Status: implementation authorized by the user for
a **new chat session**; this session prepares the handoff only.

## 1. Goal and authority

Turn the working DR viewer into a simple, evidence-based incident analyser:
upload records, inspect waveforms immediately, obtain the supported autonomous
observations, provide only genuinely missing method-specific facts, calculate
an eligible fault location, and read one short incident report.

The user grants implementation freedom while explicitly requiring preservation
of present functionality, a simple flow, available features only, and questions
only for required inputs. Proceed phase by phase in the next session without
repeated plan/implementation approval. Missing engineering facts are not
permission questions: ask for the exact fact only when its absence prevents the
requested calculation, and continue independent work meanwhile.

Do not claim that another chat has started automatically. The user opens it and
uses [NEW_CHAT_START.md](NEW_CHAT_START.md). This plan is the main work contract;
NEXT_SESSION.md is the current-state entry point.

## 2. What is proven and what needs work

Existing delivery to preserve: all analog channels; voltage/current pairing;
labelled axes; one-cycle sample RMS and Fourier cursor vectors; locked/shared
cursors; changed-first digital tracks with four initially visible when available;
automatic/manual source intervals; universal CT/VT reviewed-copy workflow; saved
end inputs; one incident report with pre/fault/post values, digital evidence,
existing eligible location and separate relay-reported distance; exports and
source/revision/hash/concurrency protections.

Previous runtime release evidence: 1,957 tests passed, 28 private-corpus skips,
one existing Starlette warning; Stage-A10,000 PASS, clean p95 .4361% of line.
These are **previous-session results**, not a fresh full qualification here.
Read AUTOMATIC_EVENT_ACCEPTANCE_2026-10-29.md and
EVENT_STUDY_ACCEPTANCE_2026-10-29.md for scope and limits.

Fresh 2026-10-30 inspection establishes these concrete priorities:

| Finding | Evidence in baseline | Required improvement |
|---|---|---|
| Operational location already works | `faultloc/ensemble.py:locate`, `workbench/incident.py:analyse_bundle` | Reuse the engine; connect a clear calculation action rather than duplicate estimators. |
| Simple report consumes an existing study | `workbench/event_study.py` reads stored `location_text`; `source_snapshot.py:line_facts` extracts a number from prose | Add a structured, source-bound location summary and a clear path to producing it. Keep legacy display compatibility. |
| Help describes outdated prerequisites | `static/feature-guide.js` RMS/conditions entries still say four-cycle fits and mandatory manual A/B | Make help and capability states agree with the one-cycle viewer and automatic event report. |
| End names alone do not run the study | `application/worker.py:validate_assignments` separately requires a configured line and physical assignments | Carry already supplied declarations forward, showing what is merely a display choice versus accepted study evidence. Do not infer physical ends. |
| Joining is advertised but not established in this audit | References to a joined viewer exist; bounded searches found no join/export route or module | Trace and test any implementation before advertising it. If absent, remove misleading actions/text; use the bounded optional phase below. |
| Rules include fallback settings | `workbench/incident.py` starts with a Z2-time default before reading settings | Audit absent-settings verdicts. Project defaults must not masquerade as the relay's actual settings or prove compliance. |

Fresh executable check: generate the existing synthetic demonstration with
known `m=.42` on a 100 km line, then run `dranalyse locate` with both ends.
E5 returns **41.988 km from S**, E4 refuses because clock quality is absent.
S/R sample rates are 1000/1200 Hz and relay clock offset is 1418 s. The ~.012 km
error is one synthetic example, not field accuracy or calibrated uncertainty.
Other method results and input flags remain visible; no polarity is repaired.
Reproduce with `scripts/create_demo.py` and the CLI. Local artifacts are under
ignored `out/qa/autonomous-handoff-2026-10-30/`.

No authenticated opposite-end private pair or patrol truth was established in
this session. DR1/DR2 are successive recordings from **one relay**, never S/R.

## 3. Scope and constraints

Read CLAUDE.md, PROJECT_CONTEXT.md (especially sections 2, 7, 13 and 17), README's
"What is different from the brief" and the applicable repository skills first.

Preserve original bytes and existing jobs/history/exports. No UI rewrite, parser
replacement, destructive migration, estimator reimplementation or gate weakening
is planned. Correct a demonstrated defect with regression evidence if necessary.
Do not retune the frozen studies or synthetic generator to make a result pass.

Binding constraints: E5 is the primary unsynchronized two-ended path; GPS is not
a dependency. E4 requires established synchronization/reference evidence. No
per-relay ML, traveling-wave location on ordinary relay DRs, guessed ratios,
automatic CT reversal, invented line constants, silent missing-sample filling,
or one report per input file. `m` measures series reactance, so km conversion
uses the existing section-aware `Line.m_to_km`. Current polarity is bus into
line at both ends. Reuse the existing k0/loop definitions and corrected equations.

Standards basis: IEEE C37.114-2014 for AC fault-location methods; IEEE
C37.111-2013 / IEC 60255-24 for COMTRADE; existing versioned settings/rules for
protection interpretation. Verify exact clauses before making new conformity
claims; this plan supplies no invented standard clause numbers. UI timing
screen thresholds and readiness states are project policies, not relay settings
or standards-derived operating limits. Existing illustrative intervals are not
automatically calibrated confidence bounds.

Section17 defaults retained for development: mixed-vendor fleet; either end may
be missing; clocks may be unreliable; no verified deployment scale or labelled
archive is assumed. Those unknowns do not block local workflow work and do not
justify production/fleet/field-accuracy claims. Ask site questions only when a
particular feature actually depends on the answer.

## 4. Simple product flow and minimum inputs

Keep Waveforms and Simple report primary. Inputs & help is contextual; Compare
and Technical evidence remain secondary. Reuse current tasks rather than adding
many menus. Preserve working advanced features under their existing secondary
entry points. Remove dead promises/actions, not functioning features.

Use explicit capability states: available, available with stated limitations,
needs named input, unsupported/not recorded. A conformance issue affecting
physical analysis must not hide recoverable waveforms. An unavailable optional
method must not block an available method. Suggestions never silently become
confirmed engineering facts.

| Feature | Inputs actually needed | Do not ask by default |
|---|---|---|
| Waveforms and digital states | Supported recoverable samples | Line constants, physical ends, CT/VT verification |
| Sample RMS and cursor vectors | Actual times, declared frequency, complete support; appropriate meanings/units and nonzero reference for physical vector grouping | A line model or the operational four-cycle fit merely to display one-cycle measurements |
| Automatic pre/fault/post observations | Supported changes/indication and sufficient coverage; manual refinement only if needed | Mandatory sample indices or invented healthy pre-fault data |
| Single-ended E1 | Eligible V/I, known scaling/polarity, line impedance and supported loop/window | Remote DR, GPS, source impedances required only by another method |
| E2 | E1 prerequisites plus usable pre-fault/superimposed current | Arbitrary pre-fault values when absent |
| E3 | Eligible ground loop, zero-sequence transfer and actual source/line zero-sequence inputs | E3-only source data when E5 or another supported method is the chosen path |
| E5 two-ended | Compatible same-event opposite ends, eligible phase data/scaling/polarity, line positive-sequence/section model and usable windows | GPS, relay-reported distance, tower table or protection settings merely to locate |
| E4 optional | Its physical prerequisites plus verified clocks and common phasor reference | Clock upgrades as a prerequisite for E5 |
| Ground-loop quantities | Relevant Z0/derived compensation and verified zero-sequence transfer | Typed unexplained k0 or fabricated neutral channels |
| Trip/CB/AR interpretation | Recorded meanings/polarity, local timing support and appropriate contact/analog evidence | Missing physical outcomes inferred from command channels |
| Protection pass/fail against settings | Actual applicable settings and scheme evidence | Generic settings treated as actual relay settings |
| Relay-distance comparison | Optional relay-reported km, reference end and evidence | Relay distance as the calculation input or patrol truth |
| Tower/line visual | Declared line length/topology; actual tower chainage if a tower is shown | Fabricated towers or an exact tower from missing chainage |

This is an input-demand contract, not permission to bypass existing validation.
If a shared schema forces unrelated fields, improve the schema/adapter with
compatibility tests; never populate fake zeros/defaults to evade it.

## 5. Phases and done checks

### P0 — Establish and protect the baseline

Read current code and release notes; capture workflow screenshots, capability
inventory and reproducible cases. Run the direct architecture guard, full suite
and Stage-A before substantive changes. Record inherited failures separately.
Use an isolated app root and preview port; keep private records out of Git.

Done when current source view, ratio-copy, auto/manual timing, cursor/vector,
four-digital-row, paired plots, report/export and history flows have a written
regression matrix and reliable checks. Do not reapply earlier delivered work.

### P1 — Honest features and method-specific input readiness

Inspect `feature-guide.js`, `operator-workspace.js`, `inspection-analysis.js`,
`event-study.js`, `input-guidance.js`, backend source/readiness functions and
existing tests. Add a small shared capability/readiness model only if needed
(a new `workbench/analysis_readiness.py` is a proposal, not existing code).
Update stale help; show only the missing facts relevant to the selected task.
Retain universal ratios with optional channel exceptions. Audit joined-viewer
links and all visible CT/VT/settings assumptions.

Done when a raw-only record can be inspected without line questions; one-cycle
RMS/help agree; empty unsupported actions are absent or correctly explained;
single-ended/E5 users do not answer unrelated-method questions. Existing valid
features and all source/choice bindings still work.

### P2 — One clear calculation flow and structured location result

Reuse `application/worker.py`, `workbench/incident.py:analyse_bundle`,
`faultloc/ensemble.py:locate` and the existing revision/queue APIs. Let the user
review the necessary physical facts once and trigger Calculate fault location.
Automatic reruns are allowed for already accepted inputs under a new revision;
ambiguous suggestions require factual review, not repetitive permission prompts.

Persist an explicit serializable location summary: method/mode/fault type,
accepted/refused state, S/R km and reference, public diagnostics/caveats,
available method estimates, supported windows, line/input/source hashes and
parameter status. Exclude callable/private `_km_fn` diagnostics and nonfinite
JSON. Update `source_snapshot.py`, event report and exports to consume that
model, preserving legacy text/report compatibility and old revision history.

Done when the synthetic known-42-km case runs through the UI and gives the same
eligible E5 result as the engine; a one-end case uses only eligible fallbacks;
bad ratios, wrong/missing line, incompatible ends and ambiguous E5 constraints
give specific reasons instead of a false distance. No healthy two-ended result
is degraded by inappropriate single-ended averaging or fallback gate bypass.

### P3 — Autonomous observations and a short incident explanation

Reuse `source_regions.py`, `event_study.py`, `source_events.py`, operational DSP,
`rules/features.py`, relay/terminal evidence and operation comparison. Summarize
voltage fall/current rise, probable fault type only when supported, pre/fault/post
values, trip indications, pole feedback and AR sequence. Keep the observation,
interpretation and uncertainty distinct, with source/sample/time provenance.
Handle short/ongoing/evolving/later events without merging stages or inventing
healthy baselines. Review settings-dependent verdicts before displaying them.

Done when the report explains what happened and what cannot be concluded, names
the distance method/reference, separates relay-reported distance, and screen/
HTML/JSON agree. Missing CB/AR contacts or settings cannot produce a pass/fail or
physical opening/reclosure time. Source-local timing is not cross-end clock sync.

### P4 — Connect the existing R–X and line visualization simply

Inspect `report/navigation.py`, `report/rx_context.py`, `workbench/rx_review.py`,
`navigation*.js`, `rx-review.js`, stage review/location and current line model
helpers. Connect the selected source sample/eligible model window to available
R–X trajectories and the line sketch. Show full declared line length and an
eligible probable location; animate only supported source observations.
Keep source projection, operational location, trip command and pole feedback
distinct. Ask ground compensation/zone settings only for the relevant view.

Done when playback, manual cursors, gaps and reference changes stay coherent;
zone overlays require actual applicable settings; missing topology/towers stay
absent; no extra diagram-specific duplicate input form is needed.

### P5 — Resolve the same-relay joining claim without fabricating evidence

If joining/export already exists, exercise and preserve it. If absent, first
remove misleading availability claims, then implement a separate bounded
advanced workflow only after P1–P4 are stable. It must keep source order/offset
provenance, compatible channel/scaling identities, overlaps/gaps and clock
limitations explicit. A missing interval is not a continuous waveform.
Export a single COMTRADE only when the representation is valid and a round trip
retains supported samples/timestamps/states; otherwise explain why it is not
exportable. Never fill unknown digital states with zero or promote a joined
display into two-ended location evidence. Retain original files.

Done when a joined-view/export claim has actual route, UI and round-trip tests,
or is honestly unavailable with no dead action. DR1/DR2 cannot become S/R.

### P6 — Qualification and delivery

Run meaningful tests for each changed contract, then the complete required gates.
Browser-test the primary flow on desktop/mobile, unsupported inputs and rapid
record/revision/choice changes. Confirm bounded work and correct cancellation
with 64 analogs, many digitals and long recordings. Record memory/time limits;
do not claim unbounded or production multiuser scalability.

Done when release evidence, exact commit, operational risks and remaining data
needs are recorded. Push the authorized review branch and verify remote HEAD.
No main merge, environment publication or production deployment is authorized
by this handoff. Commit independently reviewable phases (`P1:`, `P2:`, ...).

## 6. Test and data contract

Required gates: `OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/check_architecture.py`
directly (never through a pipe), its self-tests, `.venv/bin/python -m pytest -q`,
and `OPENBLAS_NUM_THREADS=1 .venv/bin/dranalyse stage-a --cases 10000`.
Use changed-file Ruff/JS syntax checks; report the inherited repository-wide
Ruff baseline separately. Existing fixed-port HTTP tests may require serial
execution and approved loopback-capable tool execution.

Synthetic tests must cover known distance, one/two ends, differing sample rates,
large clock offsets, weak infeed, supported fault types, missing pre-fault,
gaps, saturation, phase/units conflicts, mixed sections, out-of-line/ambiguous
solutions, provisional model, settings absent and late remote attachment. Test
abstentions as well as successful results. At least one end-to-end UI calculation
must reproduce the core result without duplicating mathematics in JavaScript.

Preserve the Stage-A clean p95 < .5% criterion and its refusal accounting. This
is synthetic qualification; field accuracy and calibrated uncertainty need
authenticated data and independent truth. Do not pair the private DR1/DR2.
If the prior attachments/ignored artifacts are absent in the new environment,
use synthetic fixtures until a particular field validation needs those files.

Changes to stored result meaning require explicit versioning and history policy.
Never rewrite old reports or originals silently. Persist new line declarations
with provenance; retain source/model hashes. No guessed source impedances,
ratios, compensation, tower chainage or timeout values. Schema changes must
preserve loading existing incidents and reviewed copies.

## 7. Expected changes, risks and working rules

Expected visible improvements: fewer questions, an actual calculation path from
the primary report, correct feature descriptions, structured distance evidence
and concise interpretation. Existing valid engine estimates should not change.
If a real maths defect is found, derive the correction, name the affected method,
test it independently, document the expected numeric step and preserve history.

Remaining factual uncertainties: actual site line/CT/VT/polarity data, authenticated
opposite-end events, settings versions, field truth and fleet/load requirements.
They are not fabricated or demanded at initial upload. Ask only when needed;
name the method/feature, the missing fact and why it matters. Continue other
available work. Never describe a configured fallback as a verified fact.

Use relay-engineering, DSP and UI review skills as appropriate. Agents are
authorized if available: separate engine/readiness, UI/report, and verification
ownership; avoid parallel edits to the same files. Agent/tool quota does not
justify leaving a partially wired feature; the main agent can integrate work.
Keep concise progress updates and update the goal ledger after each phase.
Review findings must have code/reproduction evidence. Do not replace this plan
with speculative new platforms, advanced empty menus or unrelated refactors.

Handoff ownership: previous cursor/Fourier, event backend/UI and channel work
is integrated in the baseline history. No other agent is editing this handoff.
This session changes documentation only; phase implementation is outstanding.
