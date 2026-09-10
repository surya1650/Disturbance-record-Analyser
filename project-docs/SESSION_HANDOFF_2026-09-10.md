# Session handoff — 10 September 2026

Workspace: `E:\dr analyser`. The user requested completion of the running task
and a session handoff. **The reviewed ground-loop/zone-boundary task is complete.**
No implementation or verification job is left running. Application servers remain
running intentionally. Nothing was committed, pushed, reset or stashed.

## Read first and preserve

1. `PROJECT_CONTEXT.md` section 2 and `CLAUDE.md` are binding.
2. `project-docs/TB854_VALIDATION_HANDOFF.md` contains the original scope and
   repository constraints. Its initial test count and requested refusal repair
   are historical: the matrix and repair have already been delivered.
3. `project-docs/NEXT_SESSION.md` and the newest `STATUS_LEDGER.md` entry describe
   the current state. Older entries are milestone history, not current limitations.
4. `project-docs/DR_OPERATIONAL_WORKFLOW_PLAN.md` records the user's operational
   priority. Settings API/document access, SAP bay IDs and GIS/GeoJSON follow later.
5. Inspect `git status` before editing. There is extensive existing uncommitted
   work, including the application and earlier validation milestones. Preserve it.

Keep one incident with all records/revisions; Main-1/Main-2 identity is separate
from terminal S/R and primary/corroborating role. The user's “OMS” means **0 ms at
each recording's fault trigger**; detected inception remains separate. Matching
trigger zeros do not synchronize recordings. E5 remains the unsynchronized
primary estimator. Never silently repair phases, ratios, polarity or VT topology.
Currents are positive bus into line at both ends. `m` is a series-reactance
fraction. Native compensation is derived, never entered as an arbitrary complex
k0. Vendor-specific importers stay inside `registry/settings_io/`.

## Current application

**Complete synthetic preview:**
http://127.0.0.1:8100/#incident/b81c038543ca4aefa3ddc1fd9f707fe6

- Incident revision **4**, four relay records, clearly labelled synthetic.
- Root: `out/application-rx-preview`; registry: `out/evidence-qa-registry`.
- S/Main-1 has explicit synthetic input review and an associated synthetic RIO;
  other records intentionally demonstrate missing prerequisites.
- Open **Event and channel navigator**, select **AG/BG/CG** and inspect
  **Ground-loop and zone input evidence**. Dashed earth/phase boundaries remain
  distinct. Use **Review & rerun** to create further revisions.
- Logs: `out/rx-preview.log` and `out/rx-preview.err`.
- Launch used `.venv/Scripts/python.exe -m dranalyser.application --port 8100
  --root out/application-rx-preview --registry out/evidence-qa-registry`.
  The hidden launcher PID was 32592 and the server child PID was 19300; recheck
  runtime state rather than relying on saved PIDs.

Earlier servers at **8091, 8093, 8094, 8095, 8096, 8097, 8098 and 8099** remain
running. All nine `/api/health` endpoints returned HTTP 200, `status: ok`, and
`queued: 0` at session close. **8091 is the original application** with original
data; 8099 is the prior complete mapping/native milestone. 8096 was an intermediate
navigation build; use 8100 for the current feature set.

Both original 8091 revision rows and both saved HTML reports match the SHA-256
snapshot in `out/qa/application-before-evidence-restart.json`. Earlier automatic
approval review rejected process-stop/restart actions; they were not bypassed.
No server was stopped in this milestone. Avoid launching more preview servers
without checking this inventory and choosing an intentional update strategy.
Static assets are shared; backend capabilities differ between older processes.

## Completed implementation

See `RX_INPUT_VALIDATION.md` for the full contract and bounded validation.

| Component | Location and behavior |
|---|---|
| Review schema | `workbench/rx_review.py`: strict optional `rx_review`, exact recording/settings SHA-256, current mapping snapshot, reviewer/rationale, explicit confirmations, optional positive finite settings CT/VT ratios |
| Review intake | `application/intake.py`, `worker.py`, `workbench/bundle.py`: declarations persist with assignments; association provenance is available before analysis |
| Display prerequisites | `report/rx_context.py`: missing/stale/ambiguous inputs are withheld; native compensation and conversion retain provenance; no phase/earth fallback |
| Ground trajectories | `report/navigation.py`: AG/BG/CG reuse existing filtered phasors and compensated loop definition; phase residual uses IA+IB+IC, not recorded IN |
| Zone boundaries | `report/rx_context.py`: existing characteristic outline interface, primary scaling through VT/CT, exact characteristic kind; finite/nondegenerate/bounded geometry |
| Incident evidence | `workbench/incident.py`: per-record settings and review feed only display context; context reaches relay evidence and frozen navigator JSON |
| Browser and export | `static/rx-review.js`, `navigation.js`, `app.js`, `evidence.js`, `index.html`, `style.css`; explicit input review, six loop choices, dashed boundaries, source evidence, script-free current-view export |
| Saved report | `report/evidence.html`: review declarations, sources, native k0 inputs, conversion and refusal reasons |

Paths above are relative to `src/dranalyser/`. Exact deliberate Python growth
budgets were updated in `scripts/architecture_budgets.json`; there was no global reseed.

No estimator equations, DSP algorithms, waveform samples, registry constants,
analysis windows or rule inputs changed in this milestone. The new review gates
the navigator display; it does not retrofit the legacy report's analytical plots.
The philosophy audit's settings validity/coordination checks remain not evaluable.
Declared reviewer identity is not an authenticated signature. Source hashes do
not establish field correctness or settings event-time validity.

Earlier completed work includes the TB matrix/refusal-test repair, all-relay
evidence and measurements, advisory onset correlation, recording/philosophy
checklists, local SLD/channel/phase-R-X navigation, reviewed channel mappings and
native-sample interval inspection. Their dedicated validation documents are linked
from `NEXT_SESSION.md`; do not restart those workstreams from the original handoff.

## Verification completed

- **509 pytest tests passed**, one upstream Starlette TestClient deprecation
  warning, 374.72 seconds. New files `tests/test_rx_review.py` and
  `tests/test_rx_application.py` add **29 tests**.
- Independent unbalanced phase-domain waveform network: self impedance
  `10+j18`, mutual impedance `5+j6`; all AG/BG/CG recover `5+j12` ohm within
  1e-7 at two phase rotations, despite an unrelated neutral channel.
- Refusal/geometry/metadata tests cover each confirmation, stale source/mapping,
  missing/nonfinite compensation, zero compensation, invalid geometry, VT/CT
  direction, no phase/earth borrowing, per-record isolation, settings-version
  ambiguity, escaped review text and immutable previous reports.
- Architecture guard run directly and its self-tests passed. Focused Ruff and
  JS syntax checks passed. Existing Node tests passed: 16 navigation-model and
  10 native-sample cursor assertions. `git diff --check` passed; Git printed only
  its existing Windows LF/CRLF notices.
- **Stage-A 10,000 PASS:** clean p95 **0.4403%**; 9,929 located, 71 refused;
  all-located p95 **11.470%**; CT-saturated mean **11.270%**, p95 **53.902%**.
  No impossible `m` was returned without a caveat. These are the existing scalar
  regression results, not a complete TB 854 or field validation.
- Headless Edge passed input review, missing reviewer refusal, ground/phase
  boundaries, independent relay switching, withdrawal/restoration of prerequisites,
  mapping-change refusal and subsequent re-review across four revisions, HTML
  export and preservation of revision 1. No JavaScript errors or mobile page overflow.
- Desktop/mobile screenshots were inspected. A final visual/export check first
  hit `ERR_INSUFFICIENT_RESOURCES` while other heavy checks ran; it passed after
  those completed, using `--renderer-process-limit=2`. No user processes were killed.

Local QA: `out/qa/check_rx_preview.py`, `rx-preview-identity.txt`,
`rx-trajectory-desktop.png`, `rx-trajectory-mobile.png`,
`rx-review-mobile-final.png`, `rx-export.html` and earlier `rx-*` captures.
The main QA script creates a fresh synthetic incident; do not run it as a
read-only health check. A final browser-only render inspected the form without
enqueueing a fifth revision.

## Next bounded task

**Fault-stage association and clock-quality contracts** are next under the user's
operational workflow. First inspect the actual existing stage/window evidence in
`dsp/detect.py`, `dsp/pipeline.py`, `dsp/correlation.py`, `rules/evidence.py`,
`rules/operation_compare.py` and `workbench/incident.py`.

1. Represent initial/evolving/reclose intervals per relay with original bounds,
   signal provenance and uncertain/open edges; do not average incompatible stages.
2. Establish a traceable same-stage association contract for Main-1/Main-2 and
   then both ends. Advisory onset-correlation candidates currently do not establish
   confirmed event/stage identity or synchronize timestamps.
3. Keep independent trigger-zero/inception/local timelines as the fallback. A
   clock-quality claim needs a supported source and uncertainty; never silently
   apply a lag or infer carrier delay from free-running recordings.
4. Add independent synthetic evolving-fault/reclose/ambiguous-correlation cases
   before changing estimator/window gating. Preserve E5's unsynchronized path.

Settings API/document, SAP bay and GIS/GeoJSON contracts still need actual external
schemas and source evidence. Full physical breaker state, relay logic/zone
emulation, verified field settings and field fault-location oracles are not built
or established by this milestone. The TB matrix still records ambiguous E5 roots,
external distance/tower clamping, and missing section/coupled/distributed solvers.

## Working commands

Use PowerShell and explicit UTF-8 for Python text reads/writes. No applicable
`AGENTS.md` was found at the repository root. No subagents or special skills were
needed for this milestone.

```powershell
cd 'E:\dr analyser'
$env:OPENBLAS_NUM_THREADS = '1'
$env:PYTHONPATH = 'src;.'
python scripts/check_architecture.py
python scripts/check_architecture.py --self-test
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m dranalyser.cli stage-a --cases 10000
node tests/navigation_model.cjs
node tests/native_samples.cjs
git diff --check
```

System `python -m ruff` is available; Ruff is not installed in `.venv`.
System Python also has Playwright and headless Edge. Keep expensive checks
sequential if browser/system resources are constrained. Do not rerun completed
gates merely to read this handoff; run checks appropriate to the next change.
