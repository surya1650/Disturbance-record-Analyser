# DR Analyser: operator and next-owner handover

Delivery verified: **1815 primary tests passed**, one Windows-only skip and one
existing warning. The continuation heartbeat is paused. All208 QA/ledger files
have verified preserved copies. Codex refused native cleanup of this chat's primary
checkout, so that worktree remains intact; use the primary repository for takeover.
See `project-docs/NEXT_SESSION.md` for the exact manifest and retained path.

Start here. The product is the integrated FastAPI/vanillaJS application in this repository. The old standalone 8092 report is historical evidence.

## Latest review branch in Codespaces

The user authorized pushing the UI/report draft for review on 2026-10-29. Use
branch `codex/operator-ui-review`, based on published `f52911e`:

```bash
git fetch origin
git switch codex/operator-ui-review
bash start-preview.sh
```

Open **Ports → 8098 → Open in Browser**, keeping visibility Private. The launcher
installs app dependencies, serves this checkout, trusts the exact Codespaces
forwarding hostname and loads a synthetic two-record example. Upload your own
matching files to inspect them. Preview data stays in `out/web-preview`; the
existing `out/application` data and port 8091 are not changed. If port 8098 is
occupied, use `DR_PREVIEW_PORT=8099 bash start-preview.sh` and open port 8099.
Leave the terminal running. The launcher prints the actual browser URL.

## Use the demonstration

Open http://127.0.0.1:8094/#incident/bacb3608c1e84d17a377823c50e3ebfc for copied Dhone/DR2 recordings. Select either independently. Their common incident, physical ends and clock have not been authenticated.

The four-sample CT/AR example `7376748afce74321b0c42338bf60a940` is a diagnostic edge case. It cannot provide four-cycle RMS/angles. Use full recordings for the electrical-condition workflow.

The final disposable preview root is `out/qa/integrated-final-preview`, with copied examples and the existing 8094 URLs. Original captures/Downloads, workbook, Dash, real `out/application` DB/revisions and protected 8091/8113/8092 remain preserved.

## Install and run from a fresh checkout

Python 3.11+ and Node are used for development/testing. In PowerShell, from the repository:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[app,dev]"
$env:OPENBLAS_NUM_THREADS = '1'
.\.venv\Scripts\python.exe -m dranalyser.application serve --root out/new-user-app --port 8094 --workers 1
```

Open http://127.0.0.1:8094/. A fresh root is empty: upload paired CFG/DAT files or a ZIP retaining record folders. Include every matching DAT. Keep a worker running: `--workers 0` is for prepared previews or a separate `python -m dranalyser.application worker --root ...` process. Use another port if occupied; identify the owning command before changing any process.

## Public example for another user

No private captures are required:

```powershell
.\.venv\Scripts\python.exe scripts/create_demo.py out/synthetic-demo
New-Item -ItemType Directory -Force out/demo-registry
Copy-Item out/synthetic-demo/synthetic-line.yaml out/demo-registry/synthetic-demo.yaml
Compress-Archive -Path out/synthetic-demo/S,out/synthetic-demo/R -DestinationPath out/synthetic-demo-records.zip
.\.venv\Scripts\python.exe -m dranalyser.application serve --root out/demo-app --registry out/demo-registry --port 8095 --workers 1
```

Open 8095 and upload the ZIP. This is synthetic data, not field evidence. Use dedicated demo paths as shown.

## Operator workflow

Latest restoration: **all analogs stay visible without channel pages**, with vectors
alongside on desktop and native-state changed digital channels below. Add other
digitals using the top Channels & colours disclosure. Shared cursor readouts remain
exact; the horizontal axis uses recorded-trigger-relative milliseconds when known.

For missing secondary CT/VT ratios, open **Inputs & help → Resolve missing CT / VT
ratings**. Enter actual primary/secondary ratings, reviewer and evidence, then check
or create a reviewed copy. Saving creates a new revision and selects the marked
copy; original files are preserved. A reviewed ZIP can also be downloaded. Timing
and other independent findings remain visible. See
`project-docs/VIEWER_REGRESSION_RESTORE_ACCEPTANCE_2026-10-29.md` for verified scope.


Latest cloud draft, 2026-10-29: recording tasks are separated into Waveforms,
Simple report, Inputs & help, Compare recordings and Technical evidence. Optional
operational/history tools are under More tools. Inputs & help explains prerequisites
per feature. The simple report leads with applied pre/fault/post values, distance
availability and analog/digital interpretation; JSON and HTML carry the same model.
Read `project-docs/OPERATOR_UI_REPORT_ACCEPTANCE_2026-10-29.md` for the exact workflow,
verification, browser-session selection behavior and scalability limits.

Cloud draft continuation, 2026-10-29: **Compare independent source recordings**
shows all analog channels in matching rows, voltage first and current last. Select
the second recording below the source report. Missing/ambiguous counterparts retain
placeholders. Shared display positions measure from each source start; this does not
synchronize clocks. Each waveform has its own labelled amplitude scale. Exact cursor
values remain in the main workbench. See
`project-docs/CHANNEL_COMPARISON_ACCEPTANCE_2026-10-29.md` for verification and limits.

1. Open an incident and choose a recording. Waveforms are available before line/terminal assignment or successful operational calculation.
2. Review channel meanings and voltage level. Missing-CT defaults are 132 kV: **600/1**, 220 kV: **800/1**, only for otherwise-known secondary-current channels with valid gain/offset. Valid supplied ratios remain; unknown units/side stay counts.
3. Hover, or click a waveform to move the selected cursor. Arrow keys step one sample; numeric inputs jump precisely and the view follows off-screen pins. Instantaneous values appear beside each trace in its source units.
4. Supported fitted RMS/relative angles appear beside the same waveform. Select an angle-reference source channel. Voltage/current vectors use separate scales and follow the cursor/window. These are common model-centre phasors, not interpolated instantaneous rotating vectors or proof of physical wiring.
5. Place **A at fault start** and **B at the start of post-fault**, then select **Compare A–B conditions**. Pre-fault is `[0,A)`, fault `[A,B)`, post-fault `[B,end)`. These are operator-selected regions; fault inception is not invented.
6. Read voltage/current changes and typical fitted RMS by region. Only supported windows wholly inside a region contribute. Reapply after moving A/B. Insufficient support or transient/nonstationary fits retain specific reasons.
7. Choose phase colours, hide/reorder/group compatible channels, page channels, zoom/pan and add/remove up to 16 pins. The full matrix/deltas are in **All cursor values and delta times**. Numerical bookkeeping is under technical details.
8. Review trip/AR indications with channel meanings and asserted-state polarity. A recorded indication alone does not authenticate its physical cause.
9. Supply/select actual line facts and a supported phase loop/window for an approximate line-model projection. Missing facts remain explicit; outside-line values are not clipped into plausible locations.
10. Download snapshot JSON or printable HTML. Selected condition regions and their selection provenance travel with the same report model.

## Why a value can be unavailable

Raw inspection remains independent of fitting and operational eligibility. The reviewed fundamental estimator needs four-cycle supports, suitable source coordinates, complete data, sufficient samples and stationary half-supports. At 50 Hz four cycles are 80 ms; four samples over 2.6 ms cannot qualify.

A missing/refused/zero phasor does not become a fabricated angle. Instantaneous readings, digital states, header facts and other supported channels remain useful. Raw counts, CFG-declared units and assumption-scaled analysis units are labelled separately.

Fitted consistency does not verify CT/VT, wiring, alias protection, physical clock, common event/ends, fault location or standards conformity.

## Recovery and resource contracts

ASCII/BINARY/BINARY32/FLOAT32 CFG/DAT; explicit CFG-first CFF with matching DAT format; digital-only; short records; complete counter-consistent binary prefixes with opaque-suffix reporting. Nonuniform/multirate observations retain samples where supported; unsupported time models use sample indices. No guessed binary alignment.

Limits: CFG 1 MiB, DAT 64 MiB, CFF 65 MiB; 64 analog/256 digital channels; 200,000 samples/4,000,000 cells; native intervals 20,000 samples; cursor batches 8 channels × 17 indices; 16 pins plus hover; two decoded sources; one diagnostic worker/two jobs; bounded digital-edge detail. Unknown is null, never zero. Unsupported files/header/reasons remain available.

## Developer verification and entry points

```powershell
$env:OPENBLAS_NUM_THREADS = '1'
.\.venv\Scripts\python.exe scripts/check_architecture.py
.\.venv\Scripts\python.exe -m pytest -q
```

Run full suites serially: CLI integration tests share 8241–8243. Private-corpus cases skip without local captures. The existing Starlette/httpx warning and Windows symlink privilege skip are documented; final counts are in the goalboard. For scripts using an editable environment tied to another checkout, set `$env:PYTHONPATH = 'src;.'` explicitly.

- `application/static/inspection-workbench.js`: traces, exact cursors, cache/abort guards.
- `inspection-readings.js`: same-window conditional RMS, relative angles and vectors.
- `inspection-conditions.js`: explicit A/B regions and operator report.
- `inspection-analysis.js` / `inspection-report.js`: options, jobs, UI and exports.
- `workbench/source_inspection.py`: immutable native/batched-point adapters.
- `source_diagnostics.py`, `source_events.py`, `source_quantities.py`: supported interpretation/composition.
- `comtrade/source_observations.py`, `source_container.py`, `source_decode.py`: bounded recovery.
- `tests/inspection_*.cjs`, `test_inspection_*.py`: operator/model/transport/report/API controls.

Python paths above are under `src/dranalyser/`; JS paths under its `application/static/` directory.

## Next-owner priorities and boundaries

Replay the public example and representative complete field records with the operator. Record concrete source/selection/expected-result examples. Read this guide, the goalboard, NEXT_SESSION and Git history before starting; do not redo closed reviews.

Potential next work: authenticated boundary assistance; independently validated transient/short-support RMS/phasor methods; additional containers; broader browser/load qualification. Do not relax the estimator merely to fill blank cells. Physical measurement/line/clock and protection settings evidence must come from the asset/relay owner.

The 152-case source study at `fc7453b`, original/reviewed rows, freezes `a02945e`/`7bdb578` and historical QA remain frozen. Legacy DSP/scalar/operational adoption remains held.

Deferred recovery minor: zero-safe-row errors omit structured opaque/declared/decoded counts supplied for nonempty prefixes; hashes, explicit failure and zero samples remain correct. Actual browser coverage and any further deferred items are listed in final acceptance documents. Hash-preserve ignored QA/scoped ledgers before native worktree archival.
