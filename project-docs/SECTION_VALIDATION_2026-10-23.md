# Section-aware solver and independent numerical validation

This milestone implements opt-in two-ended negative-sequence location for
reviewed, uncoupled series sections. Main and reviewed-stage paths use each
section's own impedance, retain all in-line candidates and refuse distinct
solutions. **Project level: advanced prototype / pre-pilot with bounded synthetic
validation, not TB 854 certification or established field accuracy.** There are
still zero accepted patrol-confirmed field cases.

## Model and activation

`Line.section_solver_enabled` defaults to false. A reviewed YAML model may
explicitly set `section_solver_enabled: true`; the loader rejects strings,
numbers, null and other non-booleans. This work enables no operational line.
In particular the DHN-NNR source candidate remains subject to model review,
the circuit/length conflict and existing instrument/topology prerequisites.
Enabling the solver does not clear `model_review_required`.

Accepted domain: contiguous finite passive sections starting at 0 km, positive
X1, unique section identifiers, transposed uncoupled sequence model Z2=Z1,
no declared charging or series compensation, two terminal currents into the
line, no taps/internal sources. The registry cannot discover undeclared topology
or bad instrument ratios; this remains an engineering input obligation.

For a candidate section, propagate S voltage through its prefix and R voltage
through its suffix. Aligned E4-sections solves complex voltage continuity;
E5-sections solves equality of recovered fault-voltage magnitudes in each
section and recovers the relative terminal angle. Aligned mode requires both
established clock-quality booleans. Relative-position pairing does not prove
timestamp synchronisation, same-stage identity or incident identity.

Only two descriptions of the same adjacent physical junction deduplicate.
Multiple distinct in-line roots, a degenerate constraint, undefined recovered
angle or one unusable paired observation withhold the window. Every selected
sample must identify a unique location; no good-sample median hides a failed
sample. Reported `m` is cumulative X1 fraction from S, converted through the
section geometry to physical chainage; it is never a local section fraction.

Engineering screens: <=1% relative complex voltage mismatch in aligned mode,
<=1e-8 relative magnitude mismatch for an unsynchronised algebraic root,
<=5 degrees recovered-angle circular standard deviation, <=0.02 global
reactance-fraction window spread. These are conservative project bounds,
**not calibrated accuracy, noise tolerance or confidence limits**. Endpoint
roundoff snapping is limited to 1e-10 of local section fraction.

Main dispatch requires both ends, unbalanced evidence, valid declared polarity,
finite phase/sequence support, sufficient negative sequence, a uniform grid,
overlapping local windows, no detected transition, clipping or CT saturation.
It never falls back to scalar single-ended estimates and never assigns towers.
Its interval is the selected samples' descriptive range without a confidence
claim. Reviewed stages retain source-bound review permission and guarded local
interiors; balanced stages refuse. Stage output remains separate from a blended
incident location. The disabled scalar path and its existing gates are retained.

## Independent experiment

Reproduce from the source checkout with its tests present:

```powershell
$env:PYTHONPATH='src;.'
$env:OPENBLAS_NUM_THREADS='1'
python scripts/section_numerical_validation.py --seed 854 --output out/qa/NEW-section-envelope.json
python -m pytest tests/test_section_solver.py tests/test_section_integration.py tests/test_section_validation.py -q
```

The exclusive-output CLI refuses an existing file. The tracked
[JSON aggregate](validation/SECTION_ENVELOPE_2026-10-23.json) records seed,
denominators, mode splits, refusal reasons, worst-case witnesses and UTF-8/LF
source hashes. Historical numerical-envelope artifacts remain unchanged.

Truth comes from the independent phase nodal admittance oracle, with an explicit
fault node at physical chainage and phase-matrix branch stamps. It imports no
locator, registry or production synthetic generator. Maximum KCL residual was
3.520e-10 A. The solver consumes the resulting negative-sequence quantities.
The sweep has three geometries (mixed two-section, proportional two-section,
mixed three-section), seven chainages, three SLG phases, fault resistances 1/50
ohms, physical reversal and four reference modes: aligned, unsynchronised at
0/-2.4/1.1 radians remote rotation. Each window contains eight phasor pairs.
Each scenario therefore has 1,008 cases (252 aligned / 756 unsynchronised).

| Scenario | Located / planned | Refused | Located p95 error, km | Located max error, km | Sample range contains truth / located |
|---|---:|---:|---:|---:|---:|
| Ideal | 1,008 / 1,008 | 0 | 8.53e-14 | 1.56e-13 | 1,008 / 1,008 |
| 0.1% phasor noise | 984 / 1,008 | 24 | 0.06546 | 0.15636 | 974 / 984 |
| 1% phasor noise | 671 / 1,008 | 337 | 0.48622 | 1.24297 | 663 / 671 |
| 5% phasor noise | 3 / 1,008 | 1,005 | 1.21809 | 1.32441 | 2 / 3 |
| Remote current +10% | 990 / 1,008 | 18 | 4.16380 | 5.49940 | 0 / 990 |
| First section Z1 +20% | 972 / 1,008 | 36 | 5.33738 | 7.87188 | 0 / 972 |
| Undeclared reversed remote current | 558 / 1,008 | 450 | 59.52854 | 78.86976 | 0 / 558 |

Total: **7,056 planned, 5,186 located, 1,870 refused**. Errors are conditional
on location, not all-case accuracy. The three surviving 5% noise cases do not
establish acceptable performance at that noise level. Noise is independent
complex Gaussian RMS relative to the stronger terminal V2/I2, not ADC/waveform
noise. All line lengths are 100 km, so numerical km error also equals percent
of line length here. Sample-range containment uses only a disclosed
32-machine-epsilon x 100 km roundoff allowance in this synthetic report; the
production sample range is not widened or advertised as confidence coverage.

The gain, impedance and polarity scenarios are **counterexamples**, not passed
accuracy requirements. All biased located sample ranges miss truth. In
particular E5 magnitude consistency cannot authenticate current polarity:
558 reversed-current cases still locate, up to 78.87 km wrong. The known input
polarity must be declared correctly and independently reviewed. Low residual
and stable recovered phase do not prove correct inputs.

Focused tests additionally cover invalid/duplicate geometry, missing models,
model-review/coupling/charging/compensation refusals, root ambiguity, one bad
observation, angle/distance drift, common scaling and main/stage no-fallback
behavior. Two independent phase-nodal sinusoidal record cases pass through
the actual DSP without phasor replacement (different terminal sample rates,
pre-fault lengths and timestamp offset; one with remote phase rotation).
Those are steady sinusoidal state splices, not an EMT, vendor-filter or
instrument-transient validation. Other adapter tests explicitly replace
sequence phasors to isolate numerical dispatch from acquisition behavior.

## Verification and independent review

Pure solver RED: missing module; GREEN 73 focused tests and full suite
896 passed / 28 corpus-dependent skips. Adapter RED: enabled mixed model still
refused; GREEN full 925 passed / 28 skips before the additional balanced-label
regression. That regression and missing report-table km conversion were each
reproduced RED and corrected. Current focused section suite: **109 passed**.
The numerical runner's strict JSON check caught a NumPy integer aggregate;
native integer counts now serialize without custom fallbacks.

Final full-suite, Stage-A and independent whole-branch review results are
recorded below once finished. Corpus skips reflect absent local field files
in the isolated checkout; they are not numerical test skips.

## Pending work

Field acceptance still requires verified event-effective line/instrument data,
same-circuit/same-stage paired records and independent patrol-confirmed truth
with held-out refusal-aware replay. Broader electrical work includes coupled
circuits/asymmetry, charging/distributed models, balanced section-fault solving,
taps/internal sources and series compensation. Numerical work includes weak
infeed/source-asymmetry envelopes, additional fault connections, noisy-root
identifiability and calibrated uncertainty. Acquisition work includes CT/CVT
reconstruction, vendor filtering and realistic transient validation. Existing
running preview processes require a normal restart to load these new modules;
this continuation does not restart them or edit the active application database.

Dash findings and the supplied source workbook remain local and unchanged.
