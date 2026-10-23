# Weak-infeed, source-asymmetry and fault-connection validation

This continuation expands independent numerical evidence without changing
production solvers, model gates or operational registries. **Level remains
advanced prototype / pre-pilot, zero accepted field cases.** It does not establish
TB 854 certification, operational accuracy or calibrated confidence.

## What was added

A new independent phase nodal oracle explicitly stamps line branches, two
Thevenin source matrices, source EMFs and fault-contact circuits. It imports no
locator, registry or production generator. The previous section oracle, runner
and historical numerical artifacts remain unchanged, retaining their hashes.
The new oracle is tested against source Ohm laws, fault-current KCL, contact and
earth laws, physical reversal, balanced-sequence controls and the prior SLG limit.
Maximum absolute nodal residual in the sweep: **4.602e-11 A** (<1e-6 A gate).

The oracle accepts strictly interior fault nodes. Bus/terminal faults reject:
their terminal current definition needs an explicit CT-zone convention. Line
branches remain transposed, uncoupled and series-only, with Z2=Z1. Source
asymmetry is at the measured terminal boundaries; it does not validate an
asymmetric/coupled line, charging, internal taps or series compensation.

## Source and fault circuits

Baseline source sequence impedances, primary ohms: S Z1=3+j12, Z0=6+j21;
R Z1=5+j18, Z0=11+j33. Positive-sequence phase EMF is 220 kV/sqrt(3), with
baseline R magnitude .99 and angle -.1 rad relative to S.

| Source profile | Change from baseline |
|---|---|
| baseline | Unequal S/R source impedances retained |
| weak_S_100 / weak_S_10000 | Multiply S phase impedance by 100 / 10,000 |
| weak_R_100 / weak_R_10000 | Multiply R phase impedance by 100 / 10,000 |
| voltage_angle | R positive EMF magnitude .85, angle -.35 rad |
| voltage_unbalance | Add 3% negative and 1% zero EMF at S; 5% negative EMF at R with +.4 rad offset |
| phase_impedance | Passive congruence D*Z*D: S D=diag(1.2,.8,1.1); R D=diag(.65,1,1.4) |

Weak profile names refer to the forward physical source. Physical reversal swaps
source facts as well as sections and chainage, so the weak measurement end also
swaps. These are impedance scale factors, not asserted measured current ratios;
the JSON separately reports observed I2 infeed-ratio strata. Source R/X matrices
remain reciprocal and positive definite. No synchronous-machine transient,
inverter controller or source-parameter identification is modeled.

| Connection | Explicit fault circuit; R is the sweep resistance parameter |
|---|---|
| AG/BG/CG | One phase to earth through R |
| AB/BC/CA | R directly between the two phases |
| ABG/BCG/CAG | Each affected phase through R/2 to a common fault node, then R to earth |
| ABC | Each phase through R to a floating common fault node |
| ABCG | Each phase through R to a common node, then R to earth |

R therefore has a circuit-specific meaning; it is not a universal phase-ground
equivalent across connections. A NONE state supplies the exact healthy network
for sinusoidal record generation.

## Reproducible phasor experiment

```powershell
$env:PYTHONPATH='src;.'
$env:OPENBLAS_NUM_THREADS='1'
python scripts/source_fault_validation.py --seed 854 --output out/qa/NEW-source-fault.json
python -m pytest tests/test_source_fault_oracle.py tests/test_source_fault_validation.py tests/test_source_fault_integration.py -q
```

The source checkout's test utilities are required. The exclusive-output CLI
refuses an existing file, also from another working directory. The tracked
[aggregate](validation/SOURCE_FAULT_ENVELOPE_2026-10-23.json) contains seed,
Python/NumPy versions, source hashes, worst-case witnesses, refusal reasons and
source/fault/reference/infeed/source-fault breakdowns. All relevant margins sum
to their full denominators. No oracle case or high-error result is dropped.

Numerical oracle failures retain all nine affected reference/noise windows in
their source/fault/reference denominators, with `oracle_failed_windows` counts,
typed failure reasons, up to 20 physical failure witnesses and an explicit
omitted-witness count. Failed observations have no fabricated infeed ratio;
their ratio stratum is `oracle_failure`. The run becomes
`completion_status: oracle_failure`, returns CLI exit 2 and does not claim a
guarded-DSP run. Surviving cases retain their seeded noise realizations.
Invalid configuration remains an explicit exception. Computation and strict
JSON serialization happen before exclusive publication, so those errors leave
no empty output file. `complete` means the experiment completed, not that every
location met an accuracy requirement.

Grid: 2 geometries, 3 chainages (10/40/75 km), 8 source profiles, 11 connections,
R=1/50 ohms, 2 physical orientations, 3 references (aligned, unsynchronised
0/1.1 rad remote rotation), 3 noise scenarios, 8 pairs/window. This is
**19,008 raw windows: 15,552 unbalanced and 3,456 balanced controls**. Reference
rotations and physical reversals are metamorphic checks, not independent field
events or an inferential confidence sample. The initial plan arithmetic doubled
the total; it was corrected without removing or duplicating any grid axis.

Noise is independent complex Gaussian on V2/I2. RMS scales use the stronger
terminal negative sequence, floored at 1% of the stronger V1/I1; absent negative
sequence therefore does not imply absent sensor noise. Positive-sequence
references remain ideal in this phasor-only experiment. Measured strength
screening checks every I2 sample against max(.01*ideal terminal |I1|,1e-6 A).
That diagnostic layer is reported separately; it neither selects roots using
truth nor substitutes for actual-DSP quality/identity/review gates.

## Unbalanced numerical results

Each row below has 5,184 planned unbalanced windows. All lengths are 100 km,
so numerical km error also equals percent of line length in this experiment.

| Phasor noise | Located | Refused | Located p95 error, km | Located max error, km | Sample range contains truth / located |
|---|---:|---:|---:|---:|---:|
| Ideal | 5,184 | 0 | 1.01e-13 | 4.55e-13 | 5,184 / 5,184 |
| 0.1% | 5,044 | 140 | 0.11279 | 0.40601 | 5,000 / 5,044 |
| 1% | 2,017 | 3,167 | 0.73141 | 2.05788 | 1,998 / 2,017 |

All 648 ideal unbalanced windows per source profile locate correctly. All nine
unbalanced connection types locate correctly across the ideal grid. Aggregate
unbalanced result across noise scenarios: **12,245 located / 3,307 refused**.
The measured-strength-screened located/refused totals are the same here; that
screen does not establish weak-terminal signal-to-noise adequacy.

At 1% noise, unbalanced source-stratified results (648 planned per row):

| Source profile | Located | Refused | Located p95 error, km | Located max error, km |
|---|---:|---:|---:|---:|
| baseline | 424 | 224 | 0.66309 | 1.46840 |
| phase_impedance | 405 | 243 | 0.67070 | 1.13110 |
| voltage_angle | 427 | 221 | 0.67877 | 1.16738 |
| voltage_unbalance | 411 | 237 | 0.70162 | 1.27546 |
| weak_R_100 | 130 | 518 | 0.87013 | 1.70443 |
| weak_R_10000 | 115 | 533 | 0.90741 | 2.05788 |
| weak_S_100 | 47 | 601 | 0.92694 | 1.79486 |
| weak_S_10000 | 58 | 590 | 0.80377 | 1.03167 |

Weak infeed sharply increases refusal under the stated noise model. The small
surviving subsets must not be advertised as unconditional accuracy. Worst
unbalanced 1% case: forward geometry 0, weak_R_10000, BC, R=1, true 10 km,
unsynchronised remote rotation 1.1 rad; reported 7.94212 km (2.05788 km error).
Its strength screen passes. A low residual or adequate I2/I1 alone is not an
accuracy guarantee. Sample-range containment is descriptive, using only a
disclosed 32*machine-epsilon*100 km synthetic roundoff allowance, not confidence
calibration or a widened production interval.

## Balanced controls and guarded actual-DSP results

Raw low-level section solving has no fault-connection or positive-sequence
eligibility context. Balanced controls intentionally probe outside that scope:
412/1,152 ideal balanced windows return raw locations, including roundoff-scale
negative-sequence garbage up to **82.58076 km** wrong. Source-unbalanced balanced
connections may also have material negative sequence. At .1%/1% noise the raw
balanced located/refused counts are 114/1,038 and 9/1,143. These are diagnostic
counterexamples, not accepted balanced-fault performance. Across all raw windows
(including these controls), counts are 12,780 located / 6,228 refused; this total
must not be presented as an operational accuracy score.

The actual-DSP matrix uses 88 independent sinusoidal state-splice incidents
(8 profiles x 11 connections), geometry 0 at 75 km, R=4 ohms, 2,400/1,200 Hz,
.12/.173 s pre-fault supports and remote phase rotation 1.1 rad. No phasors or
quality flags are replaced. Known synthetic one-step identity is explicitly
declared for source-bound reviewed stages; it is not autonomous field pairing.

| Workflow | Unbalanced located / planned | Balanced refused / planned | Located max error, km |
|---|---:|---:|---:|
| Main incident | 72 / 72 | 16 / 16 | 1.02e-12 |
| Reviewed stages | 72 / 72 | 16 / 16 | 1.15e-12 |

The production balanced/model/sequence/reference/quality/review gates remain
unchanged. No balanced section capability is enabled. These record cases cover
steady sinusoidal state changes, not EMT, CT/CVT distortion, relay filtering,
sensor noise, timestamp recovery or a field acceptance cohort.

## Verification and review

Baseline worktree: 950 passed / 28 corpus-dependent skips, one upstream
Starlette/httpx warning, 119.99s. Oracle RED missing module, then 60 focused
checks pass; first full suite 1,010 passed / 28 skips, 115.96s. Wider runner and
record helper were observed missing before implementation. Real staged workflow
also exposed missing Terminal objects in the validation fixture; fixed there.
Behavioral noise-scale tests caught the missing floor helper RED, and explicit
per-source cohort assertions caught missing raw/control partitions RED.

Fresh Stage-A **10,000 PASS**, 56.2s: unchanged 9,242 located / 758 refused,
clean 4,258 located / 25 refused, located clean p95 .4361%. All-located p95
6.677%, saturated located p95 39.805%, zero impossible outputs without caveat.
This legacy scalar regression does not replace the new section/source evidence.
Architecture direct/self-tests and focused Ruff pass. Final full-suite and
independent review evidence are recorded below.

Final pre-review worktree full suite: **1,028 passed, 28 corpus-dependent skips**,
one upstream warning, 150.53s. Task completion rechecked the wider runner/DSP
tests: **18 passed**, 49.69s; the 60 oracle tests also pass. All new evidence
source hashes and all ten historical section-evidence hashes match current
sources. `git diff 897087d -- src` is empty: this milestone changes validation
and documentation, not production algorithms. Both local Dash findings retain
their previous hashes. The fresh whole-branch review is recorded below after
its verdict and any required fix pass.

The fresh read-only reviewer independently passed **78 tests** (49.53s),
reproduced the saved phasor aggregate and all source hashes, checked every
scenario margin, and verified reversal/internal KCL across another 176
profile/connection/geometry combinations. Verdict: one Important finding,
no Critical or deferred Minor findings. A numerical oracle exception could
abort denominator accounting and leave an empty exclusive output. Four
failure-injection/configuration tests reproduced the issue RED. The single
fix pass now passes all five focused failure tests, including a mixed
success/failure check proving surviving seeded numerical outcomes do not move.
No second review is used; a fresh full-suite and nominal evidence rerun verify
the fix. Production algorithms remain untouched.

Post-fix worktree full suite: **1,033 passed, 28 corpus-dependent skips**,
one upstream warning, 85.78s. A fresh complete CLI experiment reports zero
oracle failures and exactly reproduces every previous nominal numerical and
guarded outcome. Both new and historical evidence hashes still match.

Review rulings preserve the disclosed terminal CT-zone, wider line physics,
EMT/nonlinear/inverter/instrument and noisy guarded-record/timestamp limits.
Field accuracy, certification, calibration and exhaustive coverage remain
unclaimed; accuracy outside this evidence remains unknown. The runner continues
to require a source checkout with test utilities. Dash/workbook/field/app/preview
states remain outside mutation scope, and primary integration/push verification
are completion requirements, not deferred work.

## Remaining limits

Source impedance scales, EMF profiles and three chainages form a bounded grid,
not an exhaustive weak-infeed/source-asymmetry envelope. Positive-sequence
references are held ideal in numerical noise screens. Fault resistance circuits
are explicit approximations, not arc dynamics. Balanced section solving remains
unsupported despite raw mathematical fits. Charging/coupled/asymmetric lines,
CT/CVT reconstruction, vendor/transient models, taps/internal sources, terminal
CT-zone faults, uncertainty calibration and verified field acceptance remain
pending. No field data, workbook, Dash findings, active app database or preview
process is changed; no operational line is enabled.
