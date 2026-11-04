# Incident report line diagram — implementation plan

2026-11-04 Asia/Calcutta. Review branch `codex/operator-ui-review`, baseline
`dcf6defe767cfa6a8164f4a6d2cc3025a735d03f`. The user asks for a line diagram,
circuit breakers at both ends, connecting line, full length and calculated fault
distances so the incident's affected circuit is easy to understand.
Implementation and review-branch publication remain authorized.

## Scope

Add an evidence-bound, accessible single-line SVG to page1 of the existing
four-page reader report. Show named S/R terminal buses, neutral CB symbols,
the connecting circuit, declared full length and voltage when available, and
the existing eligible fault point with method and distances from both ends.
Use physical km/full length for drawing; never treat estimator reactance fraction
as length. Real zero and endpoint estimates remain valid. Fault distance is
distance along the circuit, not the physical length of damaged conductor.

Use frozen revision line facts and accepted primary end assignments. Report
display order does not change physical ends. A missing/refused/stale location
gets a named reason and no placed marker. A missing length gets an unscaled
schematic. Generic CB symbols explicitly have unknown physical position;
source-bound trip/pole indications may be labelled as observations, with local
time and polarity limitations. Commands/zero current do not prove opening.
Only the modelled circuit is known. Do not invent adjoining feeders, network
topology, outage extent, switching positions or unaffected/healthy branches.

Add a version1 `line_diagram` object to new canonical report models. Older saved
JSON/HTML generations and old model rendering remain compatible and immutable.
No new main UI option or required input is introduced. Numerical engines,
original files, source/revision gates and the four-page contract are preserved.

## Phases

1. Reuse/audit frozen line, source/cohort and digital evidence; implement bounded
   canonical line/terminal/fault data with meaningful eligibility tests.
2. Draw the report diagram and integrate a compact readable page1. Escape names,
   label unknowns, preserve the summary/refusal/actions and9pt minimum print text.
3. Qualify actual browser/PDF output on the prior13 synthetic fixtures plus
   endpoint/mixed-section/long-label/missing-line/reversed-source cases. Verify
   new API generations and old artifact immutability. Run direct architecture
   self-test/guard, changed Ruff/JS syntax, full pytest and Stage-A10000.
4. Save source-hashed evidence/checkpoint, commit and push only the review branch;
   verify remote HEAD. Keep the completed earlier goal's continuation paused.

## Baseline and ownership

Earlier reader-report delivery:2239PASS/28private-data skips,18 actual PDFs each
four A4 pages, Stage-A10000PASS cleanp95 .4361%, E5 known42km output exactly
41.98828243177587km. This is a protected baseline, not a new diagram test result.
The new scratch root is `work/qa-incident-line-diagram-2026-11-04/`.

Model, SVG/template and browser/PDF qualification have separate agent ownership.
Root owns integration checks, budgets, documentation and publication. No real
substation data or native automation/connection identifiers enter the public repo.
The prior publishing permission was explicitly granted and successfully used;
do not request it again for this authorized follow-up on the same review branch.


Publication review update2026-11-04: the earlier permission remains part of the
user's task context, but automatic approval review has rejected this new public
payload twice. The checkpoint's PUSH_PENDING_AUTH block now governs publication;
a fresh explicit answer for the completed line-diagram payload is required before
any push. Implementation/verification are complete and preserved locally.
