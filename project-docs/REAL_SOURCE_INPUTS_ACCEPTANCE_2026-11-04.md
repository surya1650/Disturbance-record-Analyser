# Same-record engineering inputs and real-source workflow — acceptance

Plan: [REAL_SOURCE_INPUTS_PLAN_v1.md](REAL_SOURCE_INPUTS_PLAN_v1.md).
Branch `codex/operator-ui-review`; baseline `e76bd6e`; qualified runtime
`b1376b1184ee80eb8324c8b4384f7cc6ea0bbbb5`.
[Sanitized evidence](REAL_SOURCE_INPUTS_EVIDENCE_2026-11-04.json) contains no
private source names, source hashes, settings, samples, measurements or reports.
Actual uploaded data and real report PDFs remain local in ignored scratch.

## Result and use

Upload the real CFG/DAT or CFF recordings. The incident name uses the capture
names, and useful source names appear after parsing. Explicit name edits win.
Selecting a recording for a physical end fills an editable end name; no upload
order, filename or display label silently establishes S/R or same-event identity.

Under **Review analysis inputs if needed**, enter the actual missing CT/VT
ratings. **Save inputs** keeps the same incident and exact recording filename.
It creates an immutable input revision rather than another visible corrected
capture. Original bytes and earlier reports are unchanged. Reopen and edit the
saved ratings; they are shown prefilled and require fresh explicit confirmation.
Previously declared valid primary-valued inputs are not requested or scaled again.
Only missing main-phase ratings are required; unrelated auxiliary channels remain
unknown unless explicitly reviewed. Partial answers can be saved without falsely
clearing the remaining block.

The physical-calculation panel also accepts **this incident's line inputs**, even
with an empty global registry. Save length, voltage, impedance and explicit units,
physical end selections, automatically filled names and method-relevant facts.
Empty fields remain unknown drafts. Draft length/names can appear in the report
without authorizing a fault marker. Confirmed applicable line facts feed the
existing engine; E5 does not require Z0/source impedances/GPS. A single-end method
may need more sequence-specific facts. Existing sample/window/quality/model gates
still decide eligibility and may refuse after engineering answers are supplied.

Generate the report from the saved input revision. The four-page real paired and
single-source observation reports show the actual waveforms, supported physical
units or counts, recorded signals and named unknowns. Original source files are
not rewritten merely to save answers or create a report.

## Implementation and preservation

Instrument reviews bind the original capture hash, channel IDs, reviewer/evidence,
secondary designation and actual ratings. They apply once before existing P/S
normalization/conformance; gains and source samples/clocks stay unchanged. Original
and effective declarations are both retained. Source cache/model/diagnostic and
RX/zone/stage review identities include the review digest where applicable, so an
edit cannot reuse stale amplitudes or an earlier scaling confirmation. App-native
operational, inspection, report and native-sample rereads use the same inputs.

Default `POST /api/incidents/{id}/instrument-review` saves the same recording;
`reviewed_record` returns that original filename, with `save_mode='same-record'`.
Explicit `mode='copy'` and corrected-file ZIP export remain secondary engineering
capabilities. GET exposes `required_ratios`, editable `reviewable_ratios` and
`applied_review`. Capture-bound reviews survive line/end/exclusion changes; physical
end-specific reviews remain separately gated.

New GET/POST `/api/incidents/{id}/line-inputs` saves source-bound incident facts on
the same files. It checks exact revision/source/end identity, refuses stale/running
requests, preserves ratio inputs and freezes the calculated model per operation.
No global registry entry or synthetic line definition is fabricated for a real
incident. Source labels remain presentation data, distinct from engineering claims.

The parser extension is an optional, validated input overlay; default decoding and
numerical engines remain unchanged. The application calls its workbench validation
service; architecture rules were not weakened. Intentional file-growth budgets
were updated to exact counts only for the touched/new modules.

## Actual qualification

| Check | Result |
| --- | --- |
| Direct architecture self-test and guard | PASS |
| Changed-file Ruff / Node syntax / diff | PASS |
| Whole repository Ruff |26 inherited findings in untouched files; not claimed clean |
| Final full pytest | **2345PASS**,28 private-corpus skips,1 inherited warning,97.97s |
| Ratio/source/RX/zone/stage regression group |245PASS; final120-test subset PASS |
| Incident line helper/API group |40PASS |
| Integrated backend/name/report group |81PASS |
| Stage-A10000 | PASS, cleanp95 .4361%,0 impossible distances without caveat,32.5s |
| Actual private paired/single report PDFs |2/2PASS, each4A4 pages, no clipping/overflow,9pt minimum print text |
| Real desktop/mobile workflow | PASS, original four file hashes/names unchanged, no extra capture or guessed settings |
| Synthetic browser input/edit/line/Calculate workflow |10/10PASS, empty registry, E5 known42km remains41.98828243177587km |

Real validation used the uploaded recordings directly, not synthetic substitutes.
One source remains counts because actual missing ratings are unanswered; the other
already declares primary data and is not scaled twice. Only six missing phase
ratings are presented. No real physical distance or cross-record clock evidence
was invented. Downloads, native printing, display names, same-source selection,
single-record reporting and old generation immutability passed with zero page errors.
The actual two reports were visually inspected and bounded in Chromium PDF output.

Separate generated-source tests exercise rating corrections/edits and complete
line models. Their settings are known synthetic facts and were never applied to
the real recordings. Actual browser saves kept original file hashes/filenames
through revisions1–6, preserved old reports, retained partial drafts and reached
a completed method-labelled calculation with no global registry model.

First full qualification had one stale report-wording assertion; the scaling note
was clarified and all final tests passed. A first print harness invocation used
the old page selector; the corrected `.page` invocation verified the actual bounds.
Earlier worker platform usage limits interrupted handoff; after user continuation,
preserved code was audited and all final checks above ran. No work during the pause
is claimed. All owned real/synthetic QA servers are stopped.

## Delivery and remaining facts

- P0 `c951672`: plan/checkpoint and protected real-source scope.
- P1 `15057bf`: source-bound same-record input persistence and domain/API tests.
- P2 `b1376b1`: automatic names, same-record editor and contextual line form.
- P3 `bca3acf`: final sanitized qualification/handoff; runtime remains unchanged.
- P4 `2acd72a`: publication-block checkpoint, subsequently published with the
 qualified workflow after explicit approval; remote HEAD verified.

Engineering answers for the real physical calculation are still pending. The user
was asked for actual missing instrument ratings, line constants/units, physical
reference/association/current direction and model-relevant VT/applicability facts.
Until answered, the real observation reports remain usable and distance is withheld.
These are required facts, not another implementation approval request.

One adjacent limitation remains: standalone field-manifest acceptance replay does
not consume the new application-only instrument-review metadata. App-native replay
is covered; explicit corrected-file export retains the existing offline contract.
No unsupported field-replay claim is made. No private files or real settings are
published, no main merge/deployment/environment publication occurs, and prior
completed goal continuations remain paused. Publication status is in the checkpoint.


**PUBLISHED:** the user submitted **“Yes, publish code and sanitized documents
only”** to the exact workflow/checkpoint, named public repository and review-branch
question, resolving the prior automatic-review rejection. A normal fast-forward
push published delivery `2acd72af1955db10f3766ef894c2d9f4ce99a08d`; read-only remote HEAD
verification returned the exact SHA. This documentation closure follows with
unchanged runtime. No real DRs, settings, original source hashes, private reports
or measurements were published. No alternate path or force push was used.
Publication permission remains separate from the still-missing actual physical
facts; no ratio, line setting, current polarity or real fault distance was inferred.
