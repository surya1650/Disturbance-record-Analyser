# Next-session handoff: TB 854 validation

Prepared 2026-09-08 for a new agent chat session. Workspace: `E:\dr analyser`,
Windows PowerShell. The user asked for this handoff after asking whether the
analyser has correctly captured and validated the problems in CIGRE TB 854.

## Next objective

Build a traceable TB 854 validation matrix and strengthen the validation of
the currently supported analyser. Start by repairing the ineffective refusal
test below. Do not start a new UI rebuild or claim that the brochure's entire
method inventory is implemented. This handoff documents proposed next work;
no new electrical model was implemented in preparing it.

## Read before editing

1. `PROJECT_CONTEXT.md`, especially binding section 2, and `CLAUDE.md`.
2. README's implementation differences before touching `faultloc/` or `ml/`.
3. `project-docs/CIGRE_TB854_METHODS.md`, especially sections 3, 7 and 8.
4. `project-docs/LOCAL_APPLICATION.md` and the newest STATUS_LEDGER entries.
5. Inspect `git status` and current code. Older documents contain historical
   statements such as “not built”, “clean tree” and obsolete test counts.

The working tree contains substantial uncommitted TB extraction and local-app
work. Preserve it. Do not reset, stash indiscriminately, commit or push without
the user's instruction. Real relay recordings and the source PDF stay local.

## What is built

- Existing COMTRADE parser, conformance gates, DSP, E1-E5 estimators, E6 ensemble,
  protection rules, HTML reports, line registry and separate ground-truth tools.
- New local application in `src/dranalyser/application/`: manual CFG/DAT, CFF,
  ZIP/folder uploads; shared push API and ready-marked folder intake; durable
  SQLite jobs; worker leases; assignment review; report revisions; late records.
- `start-local.cmd` / `start-local.ps1` launch the app on **8091**. It was left
  running at http://127.0.0.1:8091; check health before starting another instance.
  An older workbench uses 8090. Do not terminate unrelated processes.
- UI contains a clearly labelled synthetic demonstration incident. Its demo
  report uses no line constants and therefore makes no fault-distance claim.
- Shared settings association was fixed: RIO exports follow the folder of the
  primary terminal record; ambiguous/multiple exports are flagged.

The app's intake integration does not implement direct relay protocols or
autonomous pairing of unrelated deliveries. SQLite worker scaling is local to
one computer/disk. Ground-truth capture remains separate; the legacy report's
default `http://dr/confirm/...` URL is not integrated into this application.

## TB 854 source and completed extraction

- Source: `E:\cigre\854.pdf`, CIGRE WG B5.52, *Analysis and comparison of fault
  location systems in AC power networks*, December 2021, 137 PDF pages.
- SHA-256 verified against the original:
  `0406508feb3154dff584a5818823ea6be01b0dd1e82f523d0d7ac2d8797a7886`.
- Selective project-relevant synthesis: `project-docs/CIGRE_TB854_METHODS.md`.
- Local scratch: `tmp/pdfs/cigre854/text.txt`, `pages.json`, and rendered pages.
  Use the original PDF for equations/tables; extracted text can lose operators.
- `standards/sources.yaml` and `catalogue.yaml` contain **22 TB-specific entries**.
  All have `analyzer_state: catalogued`; none adds a TB-specific compliance check.
- Retrieval: `python -m dranalyser.cli standards --show-context --source cigre-tb854`.

Do not equate catalogue integrity tests, application tests or general Stage-A
acceptance with independent validation against TB 854. The brochure is technical
guidance, not a certificate or the source of our 0.5% acceptance threshold.

## Current evidence and gaps

| Topic | Current evidence | Next validation need |
|---|---|---|
| E1-E5 scalar models | Ideal phasor tests and synthetic waveform sweeps | Explicit assumptions, independent expected results, adversarial cases |
| Unknown remote phase reference | E5 synthetic angle invariance and branch tests | Ambiguous roots, weak sequence content, same-stage validity; exact E5 quadratic is a project derivation |
| Line parameters | Unit/k0 conversion and registry tests | Verified field parameters and sensitivity/identifiability evidence |
| Mixed sections | `m_to_km()` walks section reactance | Conversion is not section-aware electrical solving; varying R/X, Z0/Z1 and boundary physics need an independent model |
| Parallel circuits/asymmetry | Documented in extraction | No coupled-network solver or independent coupled oracle |
| Shunt admittance/long lines | Registry fields exist | Present scalar equations omit this physics; no distributed-model validation |
| CT saturation/transient windows | Detection and synthetic stress sweeps | No validated saturation reconstruction; evolving faults and acquisition-chain effects need stronger evidence |
| Confidence intervals | Spread-based ensemble intervals | Held-out empirical coverage, shared bias and parameter uncertainty remain uncalibrated |
| Field accuracy | Real DHONE Main-1/Main-2 parsing/scaling and consistency tests | Those are same-terminal records, not a validated real two-ended pair with confirmed fault location |

Do not mark a gap validated using a generator that omits the physics being
tested. Section/coupled/distributed models require independently derived oracles.
Retain the current generator and acceptance sweep for the current supported domain.

## First concrete defect to fix

`tests/test_stagea.py:53`,
`test_ensemble_refuses_to_report_a_distance_far_outside_the_line`:

- Calls `locate` twice, modifies the second result's estimates after analysis,
  then asserts only the first result's mode.
- It does **not** prove that invalid estimates are rejected by reconciliation.
- Replace it with a test that supplies controlled invalid estimates before the
  ensemble's actual reconciliation/gating step, or constructs inputs that
  deterministically exercise the boundary. Inspect the implementation first.
- Assert the final refusal/caveat and that an invalid distance is not published
  as a valid location/tower range. Keep genuine external-fault indications distinct
  from impossible estimates; do not silently clamp a bad estimate onto the line.
- Demonstrate that the corrected test fails if the relevant guard is bypassed.
  Restore any temporary mutation immediately; never leave disabled guards behind.

This is a test-coverage defect, not yet evidence of a production numerical bug.

## Source cautions already identified

Recheck the original when using these as benchmarks; they are observations,
not published CIGRE errata:

- Table 1, p. 10: printed k0/I0 convention has a factor-of-three inconsistency
  under the repository's definition `I0=(IA+IB+IC)/3`.
- Equation 7, p. 11: magnitude bars differ from our deliberate E4 real-part
  estimate plus imaginary diagnostic. Do not replace reviewed code blindly.
- Table 5, p. 25: 65.8 minus 60.8 is 5.0 km, while the error cell prints 6.0.
- Table 6, p. 32: current-ratio numbers conflict; p. 33 also mixes error
  normalisation by actual fault distance versus total line length.
- Mixed-line example, pp. 49-50: terminal naming is inconsistent. Its 0.09-mile
  section-method error versus 2.18 miles for the conventional two-end method
  is a source-reported example, not a project-reproduced result.

The PDF supplies neither a complete implementation recipe for our E5 quadratic
nor a CT saturation reconstruction method or calibrated confidence algorithm.

## Recommended bounded work package

1. Create `project-docs/TB854_VALIDATION_MATRIX.md`. For each relevant topic record:
   source page/equation/table, problem, assumptions, implementation path,
   independent oracle/data, existing test, missing test, expected behaviour,
   acceptance criterion and evidence status. Distinguish source claims,
   project-derived criteria, implemented behaviour, validated behaviour and gaps.
2. Repair the ineffective refusal test and demonstrate that it detects a bypass.
3. Add meaningful missing tests for currently supported physics after inspecting
   existing coverage: ground-loop convention; E4 real/imaginary diagnostics;
   E5 angle invariance/root ambiguity; terminal reversal; parameter perturbation
   and honest refusal. Avoid duplicating existing tests or asserting equations
   against a copy of their own implementation. Do not invent pass thresholds
   and attribute them to CIGRE.
4. Add TB catalogue regression coverage for source filtering, unique locators,
   catalogued status and non-promotion into automatic compliance claims. Label
   this retrieval/integration validation, not electrical validation.
5. Record unimplemented electrical models and missing field data explicitly.
   Prioritise the next independent modelling task from evidence; do not bundle
   several speculative new solvers into this validation change.
6. Run the required gates, update matrix/ledger with exact results, and explain
   what is proven and what is still unvalidated. Keep the local app usable.

## Binding constraints

- One fault is one incident with multiple records and report revisions.
- E5 unsynchronised is primary; no mandatory GPS dependency.
- No travelling-wave implementation or per-relay ML; learned correction cannot
  overrule physics. No silent CT/VT ratio, polarity or phase repairs.
- Currents are positive bus-to-line at both ends. `m` is positive-sequence
  series-reactance fraction from S; km conversion walks sections.
- Do not infer terminal/line identity from argument order or silently treat
  provisional registry values as verified field constants.
- Vendor-specific settings types stay inside their importer boundary.

## Baseline and commands

Last completed verification before this handoff:

- **316 tests passed**, one upstream Starlette TestClient deprecation warning.
- Architecture guard and self-tests passed; new-code Ruff and JS syntax passed.
- 10,000-case Stage-A in the fresh app environment: **clean p95 0.4403%, PASS**.
  9,929 located, 71 unlocated; all-located p95 **11.470%**; CT-saturated mean
  **11.270%**. Clean acceptance does not establish difficult-case or field accuracy.
- Chrome upload/review/report/rerun passed; desktop/mobile screenshots inspected.

```powershell
cd 'E:\dr analyser'
$env:OPENBLAS_NUM_THREADS = '1'
$env:PYTHONPATH = 'src'
# App environment currently has .[app]; install dev extras if pytest is absent.
.venv/Scripts/python.exe -m pip install -e '.[app,dev]'
python scripts/check_architecture.py --self-test
python scripts/check_architecture.py
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m dranalyser.cli stage-a --cases 10000
git diff --check
```

Run the architecture guard directly, not through a pipe. Update only deliberate
file growth in `scripts/architecture_budgets.json`; do not blindly reseed all
budgets. `OPENBLAS_NUM_THREADS=1` prevents thread/memory failures on this computer.
Use focused tests during development and the full gates for the final change.

Do not restart the entire extraction or rerun all checks merely to read this
handoff. Begin by inspecting the weak test and current reconciliation code.
