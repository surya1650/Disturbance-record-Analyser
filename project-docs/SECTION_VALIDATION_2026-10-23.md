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
section and recovers the relative terminal angle. Aligned main mode requires
both established clock-quality booleans AND both terminal inputs explicitly
declaring `phasor_reference_aligned=True`. That declaration is for callers
supplying already aligned phasors; the analyser does not perform a reference
rotation from timestamps. Ordinary DSP/CLI inputs use E5-sections.
Relative-position pairing does not prove
timestamp synchronisation, same-stage identity or incident identity.

Only two descriptions of the same adjacent physical junction deduplicate.
Multiple distinct in-line roots, a degenerate constraint, undefined recovered
angle or one unusable paired observation withhold the window. Every selected
sample must identify a unique location; no good-sample median hides a failed
sample. Main and enabled stage adapters pair at the union of both terminals'
relative sample positions, so every observation in both selected local supports
participates even at unequal sample rates. No interpolation or 24-pair reduction
is applied on this path. Reported `m` is cumulative X1 fraction from S, converted through the
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
incident location. Scalar equations and reconciliation remain unchanged. The
shared CLI no longer promotes a nonempty CFG clock-quality code into aligned
solving, including source-locked `0` and failed-clock `F`; neither establishes
a common DFT reference. Manually supplied legacy scalar `clock_good` remains a
caller contract requiring genuinely common-reference phasors.

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
pre-fault lengths and a common physical trigger epoch; one with remote phase rotation).
Those are steady sinusoidal state splices, not an EMT, vendor-filter or
instrument-transient validation. Other adapter tests explicitly replace
sequence phasors to isolate numerical dispatch from acquisition behavior.

## Verification and independent review

Pure solver RED: missing module; GREEN 73 focused tests and full suite
896 passed / 28 corpus-dependent skips. Adapter RED: enabled mixed model still
refused; GREEN full 925 passed / 28 skips before the additional balanced-label
regression. That regression and missing report-table km conversion were each
reproduced RED and corrected. Pre-review focused section suite: **109 passed**.
The numerical runner's strict JSON check caught a NumPy integer aggregate;
native integer counts now serialize without custom fallbacks.

Pre-review worktree full suite: **932 passed, 28 corpus-dependent skips**, one
upstream Starlette/httpx deprecation warning, 141.40 seconds. Architecture direct
and self-tests, all touched Python Ruff checks and `git diff --check` pass.
Corpus skips reflect absent local field files in the isolated checkout; they
are not numerical test skips.

Fresh legacy Stage-A: **10,000 PASS**, 90.6 seconds; 9,242 located / 758 refused.
Clean cohort: 4,258 located / 25 refused (4,283 total), located p95 **0.4361%**,
max 1.798%. All-located p95 6.677%, max 91.361%; saturated located p95 39.805%
(1,203 cases). Zero impossible outputs without caveat. These are unchanged from
the previous milestone. Stage-A exercises the default scalar path; it does not
replace the independent section sweep or establish section field performance.

Independent whole-branch review used a fresh gpt-6.1-sol high context and
independently passed the 109 focused tests. It found **two Important issues,
no Critical and no deferred Minor findings**:

1. Bounded 24-pair sampling missed unusable observations, also dropping some
   higher-rate terminal observations. Complete-support union pairing and
   per-observation sequence gates now cover both ends. Main/stage regressions
   inject finite bad voltage/current observations between the old sample picks,
   with unequal terminal supports; stage tests also inject one zero I2.
2. Good clocks did not establish common DFT references. Actual-DSP records with
   the same physical trigger but pre-fault lengths .12/.12001 s returned
   75.007059 km for a true 75 km location, while .12/.173 s unnecessarily
   refused. An explicit common-reference declaration now gates section E4,
   independently from clock quality. Actual-DSP tests retain E5 for source
   codes `0`/`F`, and verify E4 only after an explicit known reference rotation.
   Real CLI construction/conformance/DSP/estimator regressions verify that
   neither code enables aligned measurement processing.

The two issues produced 12 observed failing integration variants; two additional
CLI clock-code regressions failed before their correction. The single authorized
fix pass now passes **127 focused tests**, including direct unequal-support
coverage and explicitly aligned actual-DSP E4. No second reviewer was dispatched;
fresh full-suite verification follows the fixes.

Post-fix worktree full suite: **950 passed, 28 corpus-dependent skips**, one
upstream warning, 142.92 seconds. Fresh post-fix Stage-A: **10,000 PASS**,
91.6 seconds, identical located/refused and error metrics to those above.
The final aggregate retains 5,186 located / 1,870 refused and now fingerprints
ten relevant solver/adapter/registry/CLI/oracle/test sources; all hashes match.

Review rulings: field accuracy/calibrated uncertainty remain unclaimed; EMT,
vendor/instrument reconstruction and broader physics remain unsupported; the
new fixed-source SLG envelope does not establish exhaustive weak-infeed,
source-asymmetry or other fault-connection accuracy. Misdeclared inputs remain
a risk. The shared CLI metadata promotion was corrected, while custom legacy
scalar callers retain responsibility for their common-reference contract.
Only affected architecture file budgets were adjusted to measured sizes;
unrelated budgets were not reseeded (risk: future growth needs explicit review).

Focused Ruff passes on all numerical/registry/tests/runner modules. Whole CLI
file Ruff additionally reports two **pre-existing E731** findings at
`cli/commands.py:286` and `:291`; a baseline `git show 5f1d4b3:...` check proves
both predate this work. The CLI passes with only those E731 findings excluded;
the one changed clock-gate line adds no lint finding. They were not rewritten
as part of the numerical fix pass.

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
