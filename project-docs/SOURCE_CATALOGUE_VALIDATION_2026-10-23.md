# Source catalogue, acceptance readiness and inspection validation

Resume point: `fe99a06`. The user authorized continuing non-field work and
supplied a Google Sheet, then a local line-master workbook and the Dash project.
This milestone implements source integration and acceptance/workflow safeguards;
it does not complete omitted electrical models or field-distance validation.

## Delivered behavior

- Immutable connector snapshot of all 13 transmission-line tabs, with source
  modified/retrieval times, sheet/row/cell locators, original values and hashes.
  Transformer tabs are inventoried but are outside this line analyser's scope.
  Identity-column checks after row 350 found no later transmission-line records.
- Reusable `dranalyse catalogue import`, `review-template`, `candidate` and
  `export` commands. Existing files cannot be overwritten with different content.
  No bus IDs are filled down; no row order establishes terminals/Main-1/Main-2.
  Reach vectors do not establish full zone polygons or impedance bases.
- Searchable local source catalogue with value issues, exact source links,
  reciprocal-end candidates and a downloadable blank registry-review form.
  Draft endpoints do not write active registries or modify incident revisions.
- Explicit source-bound provisional registry export. Missing/stale identity,
  base/topology/instrument declarations and unresolved parameter conflicts refuse
  export. Reviewer declarations bind evidence but do not authenticate a person.
- A separate source-candidate path can use identified source values immediately
  with `model_review_required: true`. Both main and stage location refuse this
  state. No towers are generated. Actual source values remain local under `out/`.
- `dranalyse acceptance`: read-only record replay through conformance, DSP and
  the existing location solver, with exact source/proof hashes. A frozen cohort,
  project-specific criteria, independent patrol truth/uncertainty and declarations
  are required. Empty evidence is `not_ready`, not a pass. Refusals remain in the
  denominator; duplicate/reused events, training-line leakage and excluded cohort
  cases prevent acceptance. Truth uncertainty contributes conservative error
  bounds. Interval coverage is descriptive, never a calibrated confidence claim.
  E4 gains no new authorization from clock metadata; replay keeps it gated.
- Unmapped/ignored analogs are available in the navigator and native-sample
  endpoint by exact source ID. Values are `a*x+b` in declared source units;
  CT/VT and k-unit conversion are not applied. Canonical primary arrays, DSP,
  rules and location do not consume these inspection-only channels.
- Settings lookup refuses event-time gaps and overlapping versions. Invalid,
  orphan, out-of-line and contradictory not-found confirmations are refused.
  Unscorable confirmations cannot open the dashboard's Tier-2 count gate.
  Incident reassignment cannot silently rebind existing truth to another line.

## Source findings and user ruling

The setting catalogue contains 1,961 line rows: 1,940 parse without electrical
value errors; 21 need value review; 1,166 have no bus ID. The user explicitly
confirmed **DHN-NNR = Dhone–Nansuralla**. Historical references calling it Nandyal
are superseded. The tracked placeholder registry's identity is corrected,
generated patrol towers are removed and its unreviewed model is now withheld.

The Excel line master adds circuit/conductor evidence, but exposes conflicting
lengths and incomplete circuit joins. Exact operational values and hashes are
in local source/selection/candidate files and the Dash report, not public test
fixtures. No source length is silently averaged or declared field approved.

Dash project updated locally: `E:/dash/aptransco-grid-dashboard`; its findings
are in `docs/LINE_MASTER_FINDINGS_2026-10-23.md` and the workspace index
`E:/dash/LINE_DATA_FINDINGS_2026-10-23.md`. That project directory has no Git
metadata or remote. No GitHub publication or live DB migration was performed.

## Independent review and verification

Superpowers was requested after the initial implementation. Its verification,
independent code-review and RED→GREEN fix workflows were applied from that point;
earlier code was not retroactively claimed to have been developed test first.

The independent reviewer found one important race in patrol confirmation versus
incident reassignment. Real same-object and separate-SQLite-connection tests
reproduced it before the fix. `BEGIN IMMEDIATE` now spans validation and mutation
under the Store lock, protecting both concurrency forms. The focused 26-test
truth/readiness run passed after the fix. The final full suite passed after it.
No other concrete functional/provenance blocker was reported. Physical field
truth and final prose/visual polish were outside that review's judgment and are
not treated as verified by its verdict.

Final full suite: **744 passed**, one upstream Starlette/httpx deprecation
warning, 128.32 seconds. Architecture direct/self-tests and focused Ruff pass.
JavaScript syntax checks pass; navigation-model and native-sample checks pass
16 and 10 assertions respectively. Dash's eight offline audit tests pass, and
the final real-source audit reproduces the documented counts. A first JS test
command used a nonexistent `tests/js` directory; rerunning the actual
`tests/navigation_model.cjs` and `tests/native_samples.cjs` files passed.

Stage-A 10,000 PASS: 9,707 located, 293 refused;
4,258 clean located, clean located p95 0.4361%, all-located p95 8.0513%,
CT-saturated located p95 35.2249%. Numerical behavior matches the last checkpoint.
These difficult tails remain unsuitable as general field-accuracy claims.
The catalogue was inspected in the local browser, including filtered source
rows, their detailed raw values and reciprocal-end candidates. The isolated
preview is http://127.0.0.1:8113/#catalogue, root
`out/application-catalogue-preview`, with the private source-candidate registry
`out/source-data/registry`, one worker and launcher PID 40072 at handoff.
Only that newly created preview was restarted. Older servers were not stopped.

Fresh read-only field inventory: 16 recordings, 11 analysed, five blocked;
zero stored patrol confirmations. All 16 recording hashes match the prior audit.
Neither source workbook was edited, and existing application roots/reports were
not reset or migrated. Only the newly created catalogue preview is to be restarted.

## Use

```powershell
dranalyse catalogue import out/source-data/grid-settings-2026-10-23.json --out NEW-ROOT/source-catalogue.json
dranalyse catalogue review-template NEW-ROOT/source-catalogue.json --out review.json
dranalyse catalogue candidate NEW-ROOT/source-catalogue.json --selection selection.json --prior data/registry/dhn-nnr.yaml --out PRIVATE-REGISTRY/dhn-nnr.yaml
dranalyse catalogue export NEW-ROOT/source-catalogue.json --review review.json --out REVIEWED-REGISTRY/line.yaml
dranalyse acceptance --template --out acceptance-protocol.json
dranalyse acceptance --manifest acceptance-protocol.json --out acceptance-result.json
```

The empty local protocol/report correctly retain `not_ready`. An actual case
needs a line proof `{path, sha256}`, explicit S/R records `{path, record_hash}`,
a review proof with reviewer and the declared identity/stage/scaling/topology
confirmations, and a separate independent truth proof with chainage and
uncertainty. Freeze planned event IDs, timestamp, minimum case count, maximum
p95 error and minimum located fraction before running it. These are project
acceptance criteria, not thresholds mandated by CIGRE.

Remaining: reviewed circuit/length/topology choices, event-effective settings,
verified wiring/scaling, surveyed towers and independent patrol cases. General
section/coupled/distributed solving, CT/CVT reconstruction, calibrated uncertainty,
autonomous cross-delivery pairing and direct relay collectors remain outside this
completed software milestone. No unsupported method was enabled by importing data.

## Publication

The user subsequently requested committing and pushing the analyser changes to
the existing GitHub remote. Git history and `origin/main` record the outcome.
Dash findings and the workbook/settings snapshots, operational candidate registry,
databases and QA outputs remain local; no Dash files are part of this commit.
