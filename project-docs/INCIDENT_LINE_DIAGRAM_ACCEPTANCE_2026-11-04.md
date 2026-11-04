# Incident-report line diagram — acceptance

Plan: [INCIDENT_LINE_DIAGRAM_PLAN_v1.md](INCIDENT_LINE_DIAGRAM_PLAN_v1.md).
Branch: `codex/operator-ui-review`. Baseline `dcf6def`; qualified runtime
`119d3dc96523139c61455293946accfc8466c65a`. All45runtime hashes match
[the committed evidence](INCIDENT_LINE_DIAGRAM_EVIDENCE_2026-11-04.json).
The user requests terminal CBs, the connected circuit, full length and calculated
fault distances in the existing clear four-page report.

## Result and use

Select **Report → Generate report** (or **Generate updated report** for an existing
incident). The new page1 diagram shows named S/R terminal buses, neutral circuit
breaker symbols, the connecting circuit, declared line length/voltage and an
eligible, method-labelled fault point with kilometres from each end. The rest
of the four-page report keeps current/voltage waveforms, measurements, digital
observations and plain analysis/actions. New main UI options are not introduced.

Old saved reports stay immutable. Generate a new report to include the diagram;
opening an older HTML/JSON generation does not rewrite it. The portal still
supports one-recording observation reports without requiring a physical line model.

The synthetic100km example retains **E5 =41.98828243177587km from Synthetic S**
and **58.01171756822413km from Synthetic R**. Its marker is at the corresponding
physical fraction of line length. Zero/terminal estimates remain valid. Mixed
conductor sections use the already-calculated physical kilometres, never the
estimator's reactance fraction as a geometric length fraction.

## Evidence boundaries

New canonical models add `line_diagram.version=1`. Frozen revision line facts,
existing eligible location, source cohort and hash/end bindings supply the view.
Physical S/R assignment does not follow display order. Missing/refused/stale or
inconsistent distances produce a named reason and no marker. A missing line model
produces a generic unscaled schematic, with unknown names/lengths explicit.
Declared/provisional model status is shown; surveyed accuracy is not invented.

CB means circuit breaker. A neutral question-mark symbol represents a terminal
switching point with unknown open/closed state; actual bay arrangement is unverified.
Source-bound trip/pole indications are observations with stated local time,
polarity and gap limitations. Reviewed assertion/clearing is distinguished from
unreviewed high/low states. Commands, current loss, and pole indications alone
do not prove mechanical operation. No common cross-record clock is assumed.

The diagram connects only the modelled two-terminal circuit. Other connected
feeders, switching topology, outage extent and healthy/unaffected branches have
not been supplied and are not fabricated. The fault distance is an estimated
position along the circuit, not a measured length of damaged conductor.

The SVG and HTML escape labels, retain accessible title/description and bound
display length. Full values/labels remain in JSON. Older model rendering remains
compatible. Original files, numerical engines, operational results, old technical
report and report/revision histories are preserved. No standard-derived switching
or protection-compliance claim is introduced; this is a project presentation view.

## Verification

| Check | Result |
| --- | --- |
| Direct architecture self-test/guard | PASS |
| Changed Python Ruff, Node syntax, diff | PASS |
| Full repository Ruff |26 inherited issues in untouched files remain |
| Focused line/model/renderer/API/UI integration |88PASS,1 inherited warning,8.93s |
| Full pytest | **2279PASS**,28 private-data skips,1 inherited warning,98.29s |
| Stage-A10000 | PASS, cleanp95 .4361%,0 impossible distances without caveat,34.6s |
| Actual Chromium PDFs | **24/24PASS**, each4A4 pages, no clipping/footer/scroll/text overflow |
| Geometry | **6/6PASS**, zero/remote endpoints, physical km rather than reactance, missing/refused, long labels |
| Desktop/mobile portal and preserved artifacts | **PASS**,0 page errors; old and new generations/legacy reports remain immutable |

Scratch evidence is in `work/qa-incident-line-diagram-2026-11-04/` and does not
replace the prior report goal's evidence. Only synthetic sources are used; the
private corpus/patrol truth is unavailable. No new field-accuracy claim is made.

## Delivery

- P0 `72f260f`: bounded plan/checkpoint and ownership.
- P1 `7ce9ce9`: frozen line/terminal/observation/location model and tests.
- P2 `119d3dc`: diagram SVG, compact page1, API/UI integration and renderer tests.
- P3 `e4af0fb`: complete qualification/evidence and synthetic sample export.
- P4: local publication-block checkpoint; no push occurred.

All runtime gates above and source hashes are satisfied. Full repository lint
still has26 inherited findings; it is not claimed clean.
The prior completed goal's continuation stays paused. No main merge, deployment
or environment publication. Public publication is blocked as recorded below.


The24actual PDFs comprise13source fixtures,6provided-model geometry stress cases
and5actual API generations (96pages total). Print text is at least12px (9pt);
diagram effectiveSVG text is13.75px desktop and12.92px at390pxmobile width.
No text or plots were hidden to satisfy four-page output. Independent source/
geometry/mobile review found no correctness/wording blocker; root then inspected
the final printed known42page1 after reading the completed qualification logs.

Actual portal checks cover upload/parse→analysis→optionalcomparison→generation,
HTML/JSON exports/nativeprinting/newtab/mobile, reversed displayed source order,
late revision2, manual-input stale warning, wrong-revision response and held
response after route departure. An isolated copy of a pre-feature store served
its earlier generation byte-identically with no added diagram; the original
qualification store was unchanged. These are synthetic software checks, not
field switching/protection or patrol-confirmed accuracy validation.

Scratch logs: `pytest.log`, `focused.log`, `stage-a.log`, `combined-print.log`,
`geometry-results.json`, `portal/results.json`, `portal/extras-results.json`,
`historical-generation-results.json`, `runtime-manifest.json`. The sample PDF,
HTML and first-page image are in the scratch `deliverables/` directory.

A browser worker hit a platform usage limit at handoff. Its previously launched
checks completed; after the user's explicit continuation, root verified the
actual logs/artifacts and45runtime hashes. No continued agent reasoning during
the pause is claimed. All owned QA servers are stopped, and the earlier goal's
continuation remains paused. Review-branch publication is the only remaining step.

**PUSH_PENDING_AUTH**: automatic approval review twice rejected publishing this
new payload despite the earlier approval/published delivery record. It requires
an explicit current answer permitting this line-diagram code/tests/synthetic docs
to the named public repository and review branch. That question is pending; no
push ran and no alternate path was used. All implementation/qualification commits
remain local; last verified remote HEAD is dcf6defe767cfa6a8164f4a6d2cc3025a735d03f.
