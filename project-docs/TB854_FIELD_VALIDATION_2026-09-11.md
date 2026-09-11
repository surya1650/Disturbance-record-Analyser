# TB 854 software validation and field-evidence audit

The available software follow-ups are completed and tested. **Full TB 854 method
coverage and field-distance validation are not complete.** Their remaining data
and model requirements cannot be replaced by passing synthetic tests.

## Implemented corrections

| Matrix item | Current behavior and evidence |
|---|---|
| V06: E5 ambiguity | Distinct roots separated by more than 1e-4 pu with the same interval preference and angle-spread difference at most 1e-6 rad are refused. Candidate distances remain diagnostic fields; no selected m is returned. Rotation tests and a process-local bypass prove the refusal. This is a numerical-indistinguishability policy, not a calibrated noisy-root discriminator. |
| V07/V08: paired windows | E5 refuses empty, unequal, nonfinite or fewer-than-two-sample inputs. Ambiguous roots or insufficient paired samples cannot silently fall back to a single-ended location. A usable synchronized E4 remains possible under its existing prerequisites. E5 never requires GPS. |
| V09/V10: impossible/external distances | Impossible m outside [-0.5,1.5] remains a refusal. Every remaining m outside [0,1], including the former 2% tolerance band, is an external indication: signed m/method retained, `ok=false`, km and interval-km unavailable, no towers. Rule inputs cannot treat it as a location. HTML/CLI estimator tables cannot clamp external m to endpoint km. |
| V12: mixed sections | New independent phase nodal oracle explicitly inserts section junctions and a fault at physical chainage. KCL/KVL, all three ground-faulted phases, physical terminal/source reversal, faults just before/at/after a junction, and the proportional-section limit are tested. A deliberately wrong summed model fails the physical-chainage benchmark. Nonproportional sections are now refused by both location entry points; a general section solver remains unimplemented. |
| V13/V14/V16: model domain | Both main and stage location refuse declared double circuits, nonzero shunt parameters, series compensation and invalid/noncontiguous sections. Proportional sections require common R1/X1, R0/X1 and X0/X1 (rtol 1e-8, atol 1e-10). An independent pi-network counterexample demonstrates charging changes terminal currents. These are conservative domain gates, not coupled/distributed/capacitor solvers. Undeclared topology still cannot be detected reliably. |
| V15: waveform stresses | Fifteen cases at 1000/1200/2400 Hz verify stage-window refusal for a decaying voltage oscillation, clipped current, voltage drift, short interiors and nonuniform sampling. These are explicit perturbations of the independent network waveform, not validated CT/CVT hardware transfer functions or an EMT model. |
| V18: interval interpretation | README and incident HTML identify displayed intervals as diagnostic spread, not calibrated confidence coverage. Coverage cannot be established from correlated estimator agreement or a small residual. |
| V17/V21/V22: field inputs | A repeatable read-only inventory records source hashes, parser/conformance/DSP findings, provisional registry evidence, generated tower grids and stored confirmation counts. It does not infer end identity from folder order, repair scaling, authenticate declarations or calculate an accepted field-distance score. |

All thresholds above are project policies, not CIGRE requirements. No TB catalogue
entry was promoted to an automatic compliance check. The local 137-page source
`E:/cigre/854.pdf` retains SHA-256
`0406508feb3154dff584a5818823ea6be01b0dd1e82f523d0d7ac2d8797a7886`.
Pages 49-50 were visually rechecked for the nonhomogeneous-line example. The
independent fixtures do not reproduce its measured field waveforms or Table 9.

## Verification

- **666 tests passed**, 63 added, final full run 41.08 seconds; one upstream
  Starlette TestClient deprecation warning. The existing real-record suite passes.
- Architecture guard run directly and self-tests passed; focused Ruff passed.
- Process-local bypass experiments detected ambiguity refusal, external-field
  suppression and model-domain gating. Existing distance and branch-selection
  mutations were detected too. No source or live process was mutated by them.
- Stage-A 10,000 passed after numerical changes, before final field checks:
  **9,707 located; 293 refused**. Clean total **4,283**, located **4,258**, refused
  **25**. Clean located p95 **0.4361%**, maximum **1.7977%**. **4,095/4,283 (95.61%)**
  of all clean cases produced a result within 0.5% of line length.
- All-located p95 **8.0513%**, maximum **91.3605%**; CT-saturated located p95
  **35.2249%**. These difficult-case tails remain unacceptable as general field
  accuracy claims. The reduced tail partly reflects additional abstentions.
- An intermediate sweep exposed a 20.747% clean-case error after insufficient
  E5 samples fell back to single-ended estimation. The final fallback gate
  removes that regression through explicit refusal, not by hiding its cases.

Detailed Stage-A statistics and clean refusal seeds are local in
`out/qa/tb-field-stage-a.json`; its full report is `tb-field-stage-a.txt`.

Desktop/mobile Edge checks passed on the updated 8102 backend with no page
errors. A synthetic declared-double-circuit incident retains operational
evidence while its location and saved HTML explicitly refuse the unsupported
model. Screenshots were inspected. Current backend PID at handoff: 45132;
root `out/application-stage-location-preview`, one worker. New refusal example:
`19637ed2855b45cd840f6c6e5ec6119b`, revision 1. The earlier reviewed stage example
`3833fb155e04488da2c1764a828035b2` and all its revisions remain intact.

All original revision rows and report/navigator artifacts in eleven application
roots were verified against the pre-work hashes. The 8091 root gained one
additional revision during the session, left intact; its original rows and
artifacts are unchanged. The new synthetic refusal incident was created only in
the existing 8102 preview root. Only that preview server was restarted.

## Available field evidence

The complete CFG/CFF search outside generated output and environments found
**16 recordings** in the three existing corpus roots. **11** parse and reach
analysis; **five** are blocked by CT/VT ratio/P-S declarations. No declarations
were repaired. Existing findings include clock/time-basis gaps, clipping and
absent zero-sequence voltage support; these do not prove wiring causality.

All **three** registry definitions are marked provisional and generate a tower
grid from a typical span rather than an explicit surveyed tower schedule. Two
declare double-circuit topology, now outside the scalar location domain. The
read-only inspection of `out/dranalyser.db` found **zero ground-truth rows**.
The inventory therefore does not establish any accepted field-accuracy case.
This is an evidence-readiness conclusion, not a claim that records lack faults
or that relay-reported distances are patrol truth.

Run the inventory without changing application state:

```powershell
$env:OPENBLAS_NUM_THREADS='1'
$env:PYTHONPATH='src;.'
.venv/Scripts/python.exe scripts/field_evidence_inventory.py --records 'DR & Events 9-4-2026' 'DR 9-4-2026' 'drs sphoorthi' --registry data/registry --truth-db out/dranalyser.db
```

The detailed, private result is
`out/field-validation/evidence-inventory.json`. Raw field records, settings,
databases, source PDF and generated QA evidence remain outside Git.

## Inputs still required to finish field acceptance

1. Opposite-end recordings explicitly tied to the same circuit, incident and
   physical stage, with reviewed phase mapping, CT/VT ratios and polarity.
2. Approved, event-effective line sections, Z1/Z0, units, topology and source
   evidence. Coupled or materially shunt-loaded corridors additionally require
   an independently validated electrical model and its physical parameters.
3. Surveyed tower coordinates/chainages and uncertainty, plus an independent
   patrol-confirmed fault location/uncertainty linked to the selected incident.
4. A frozen acceptance protocol and held-out confirmed cases for error and
   interval coverage. A single demonstration cannot establish fleet accuracy.

The user was asked where these verified inputs are available. No substitute
values or fabricated confirmations have been entered. Further unimplemented TB
methods—coupled/distributed/general section solving, acquisition reconstruction,
PMU/current-ratio/reactance-method variants and calibrated uncertainty—remain
explicitly outside current validation. Travelling-wave and per-relay ML remain
excluded by the binding project scope.
