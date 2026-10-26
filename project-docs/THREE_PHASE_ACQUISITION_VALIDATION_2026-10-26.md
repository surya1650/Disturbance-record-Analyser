# Three-phase / full-record acquisition validation — 2026-10-26

The full-record study **fails the safe-adoption gate**. All **552 paired incidents /
1,104 main and reviewed-stage outcomes** completed with zero numerical failures.
The candidate passed **81 incidents with study-defined harmful measurement error**.
The unchanged production workflows located **57 outcomes more than 1 km wrong**
under coherent gain, polarity or fundamental-alias controls. Keep the candidate
offline and retain production acquisition/CT gates. No previously refused input
is newly authorized. This is a completed negative validation result.

## What changed

Added independent three-phase state-splice waveforms, the already-tested toy CT
before noise/ADC encoding, integer ASCII COMTRADE with actual secondary scales
and CT/VT ratios, public parsing, six-channel research diagnostics and an actual
main/reviewed-stage workflow harness. No production source, frozen scalar
candidate/oracle or historical evidence changed. Protocol/code freeze: `8521053`.

The new grid has 23 scenarios crossed with AG/BC/ABG/ABC and three source profiles
in each of two splits. Development uses 49 Hz at 2400/1600 Hz; validation uses 51 Hz
at 3200/2000 Hz, different rotation, DC decay, burden, initial flux, seeds and two
different source profiles. All inputs are synthetic. The prior published scalar
holdout is preserved and was not retuned. Full parameters are in the tracked JSON
and [spec](../docs/superpowers/specs/2026-10-26-three-phase-acquisition.md).

## Actual workflow and joint-screen results

| Split | Paired incidents | Main/stage located | Refused | Failed | Joint quality pass | Harmful quality pass | Harmful CT incidents | CT harmful passes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| development | 276 | 70 | 482 | 0 | 95 | 48 | 33 | 0 |
| validation | 276 | 98 | 454 | 0 | 67 | 33 | 33 | 0 |
| All | 552 | 168 | 936 | 0 | 162 | 81 | 66 | 0 |

The joint screen passes 162/552 incidents. There are 281 study-defined harmful
measurement incidents,81 of which pass it (48 development,33 validation). All 66
CT incidents above the 5% current-error threshold refuse the joint screen, and
none produce a production location. Across all workflows:168 located/936 refused.
Main accounts for 100 located/452 refused and 32 errors above 1 km; reviewed stages
account for 68 located/484 refused and 25 errors above 1 km. All 276 balanced-control
workflow outcomes refuse; no E4 outcome or clock correction is introduced.

Among the 168 located outcomes, p95 error is 4.1075 km and maximum 24.3112 km.
These aggregate errors include deliberate coherent defects and must not be
presented as ordinary clean-record accuracy. The clean-ADC scenario locates 18
of 48 workflow outcomes with maximum 0.01522 km; the other 30 refuse. Extreme weak
R infeed (10000 x source impedance) refuses all 184 workflow outcomes.

| Scenario | Incidents | Located / refused | Joint quality pass | Harmful quality pass | Located >1 km | Maximum located error (km) |
|---|---:|---:|---:|---:|---:|---:|
| alias_fundamental | 24 | 20 / 28 | 20 | 20 | 12 | 2.39490 |
| alias_harmonic | 24 | 10 / 38 | 0 | 0 | 0 | 0.02756 |
| clean | 24 | 18 / 30 | 20 | 0 | 0 | 0.01522 |
| clip_i | 24 | 0 / 48 | 0 | 0 | 0 | — |
| clip_v | 24 | 0 / 48 | 0 | 0 | 0 | — |
| clock_skew | 24 | 18 / 30 | 20 | 0 | 0 | 0.01522 |
| colored | 24 | 0 / 48 | 1 | 1 | 0 | — |
| ct_multi | 24 | 0 / 48 | 0 | 0 | 0 | — |
| ct_noisy | 24 | 0 / 48 | 0 | 0 | 0 | — |
| ct_single | 24 | 8 / 40 | 5 | 0 | 0 | 0.01478 |
| drift | 24 | 8 / 40 | 0 | 0 | 0 | 0.04000 |
| dropout | 24 | 0 / 48 | 0 | 0 | 0 | — |
| gain_i | 24 | 18 / 30 | 20 | 20 | 18 | 4.34882 |
| gain_v | 24 | 16 / 32 | 20 | 20 | 16 | 1.81250 |
| gap | 24 | 0 / 48 | 0 | 0 | 0 | — |
| harmonic | 24 | 9 / 39 | 0 | 0 | 0 | 0.04398 |
| polarity | 24 | 19 / 29 | 20 | 20 | 11 | 24.31118 |
| quantized | 24 | 0 / 48 | 4 | 0 | 0 | — |
| rate_error | 24 | 18 / 30 | 20 | 0 | 0 | 0.01522 |
| short | 24 | 6 / 42 | 0 | 0 | 0 | 0.20964 |
| spike | 24 | 0 / 48 | 0 | 0 | 0 | — |
| white_0.001 | 24 | 0 / 48 | 11 | 0 | 0 | — |
| white_0.01 | 24 | 0 / 48 | 1 | 0 | 0 | — |

## Counterexamples and interpretation

- All four coherent-defect families—current gain 1.2, voltage gain 1.2, R IA
  polarity reversal and a fundamental-alias sinusoid—pass the joint screen in 20
  of 24 incidents each. These 80 passes account for all 57 locations above 1 km.
  A coherent sine remains a coherent sine after gain or polarity error. Sampling
  an analytic sinusoid at fs−f aliases to the fundamental; this control does not
  model a real anti-alias filter or establish that a particular relay aliases.
- Worst outcome: case 294, validation/baseline/AG/polarity, reviewed-stage E5-sections
  reports 50.68882 km for true 75 km:24.31118 km error. Its section fit is unique
  across the paired samples. That numerical consistency does not establish
  correct channel polarity, gain or physical chainage.
- The remaining harmful pass is case 349, validation/baseline/ABC/colored.
  Maximum phase-current error is 0.1800% and voltage error 0.2354%, but I2 error
  over the declared reference floor reaches 9.6103%. Both actual workflows refuse
  this balanced control. It is evidence that phase-shape budgets do not provide
  a negative-sequence accuracy guarantee, not an observed noise-induced wrong
  location. The 5% threshold/floor combination is a study challenge, not a standard.
- White 0.1%/1%, colored 1% and quantization scenarios all refuse production location
  (192 workflow outcomes). Their joint-screen passes total 17, including the
  colored balanced counterexample. No positive-noise location-accuracy claim is
  supported by these production outcomes.

Clipping, dropout, spike, harmonic/alias-harmonic, frequency chirp and short
windows produce no joint-screen passes. All 48 gap outcomes refuse. All 24
metadata-skew pairs have exactly identical workflow results to their clean
counterparts (48 workflow comparisons), with no E4 promotion. A +0.5% R declared
rate defect does not establish physical clock recovery: declared rates remain
authoritative, and observed chainage errors stay bounded in this stationary toy
grid. The drift scenario is a 1 Hz/s physical-frequency chirp, not a clock-drift
or sampling-aperture model.

## Physical model, truth and limits

The line has 40/60 km balanced series sections, known fault 75 km and 4 ohm
contacts. Complex nodal impedances are held fixed as synthetic phasor parameters
at each frequency; no frequency-dependent line, charging or coupled-line model
is introduced. Quiet/fault/cleared sinusoidal states and added decaying DC are
not EMT reconstruction. CT response is secondary-referred current balance and
flux integration with the frozen continuous piecewise excitation curve. Initial
flux bias is not hysteretic remanence. VT conversion is ideal. CT cases contain
DC; their independent CT-only error compares against matched ideal DC waveforms,
but across-scenario production comparisons do not isolate DC from CT response.

ADC encoding uses 20-bit signed counts, nominal full scale 64 secondary A and 150
secondary V, CT 1000:1 and VT 2000:1. Forced clipping uses explicit lower per-channel
count rails. The parser scales once to primary A/V; the research wrapper converts
back using the recorded ratios. Even clean-ADC captures retain quantization:
two extreme weak-infeed clean incidents exceed the study measurement threshold.
No manufacturer ADC/CT/VT parameter claim is made.

Frozen scalar shape limits apply to all six channels:2% residual RMS,3%
harmonic RMS and 8% peak residual; four cycles,16 samples/cycle and numerical
fundamental floors 1e-9 secondary A or analogous V are required. Voltage transfers
the dimensionally homogeneous scalar math as an exploratory diagnostic; it is
not calibrated VT quality. All outputs retain authorizes_location=false.
Acquisition blocks, finite waveform/metadata, uniform time grid and ADC clipping
are checked separately. Candidate support is the known synthetic interval after
1.5-cycle blanking and before a 0.5-cycle clearing guard. It is not autonomous
field inception/stage identification. Actual production windows/gates are
exercised independently, including source-bound known synthetic stage review.

Truth uses independent complete-cycle quadrature of ideal, CT-only and parsed
secondary waveforms on corresponding physical sample indices. Per-phase errors
use denominator max(abs(reference phase),1% of maximum reference family phase,
1e-6 secondary units). I2 errors use max(abs(reference I2),1% abs(reference I1),
1e-6 secondary A). The 5% threshold is not calibrated uncertainty or a protection
acceptance limit. Twelve development short-window incidents have no complete
cycle for truth quadrature and retain unknown/null error metrics; their joint
screens refuse. No unknown metric is described as zero error.

## Decision and next work

The safe-adoption gate fails because validation has harmful joint-screen passes
and existing workflows return wrong locations on coherent defects. Keep the
candidate offline; do not clear a legacy noise/CT flag merely because all six
waveforms look sinusoidal. A future change needs a separately frozen
negative-sequence noise/error budget and evaluation of observability limits
under gain, polarity and aliasing. Independent ratio/polarity and anti-alias
provenance cannot be manufactured from a good sine fit. More realistic instrument
curves, sampling-aperture/clock-drift models, parameter evidence and eventual
accepted field cases remain pending. No production threshold was tuned to this
grid, and its validation cases must remain regression evidence for future work.

## Reproduction and verification

[Current corrected complete evidence](validation/THREE_PHASE_ACQUISITION_ENVELOPE_2026-10-26_CORRECTED.json)
contains every case, both workflows, strata and 29 normalized UTF-8/LF source
hashes. Scientific failure is a complete numerical result; numerical exceptions
retain both failed workflows and produce CLI exit 2. Publication rejects existing
or racing output files and nonfinite JSON. Use a source checkout and the existing
environment with PYTHONPATH=src;. and OPENBLAS_NUM_THREADS=1:

```powershell
& 'E:\dr analyser\.venv\Scripts\python.exe' -m pytest tests/test_full_record_acquisition.py tests/test_full_record_validation.py -q
& 'E:\dr analyser\.venv\Scripts\python.exe' scripts/full_record_validation.py --output out/qa/full-record-new-run.json
```

Focused tests:34 passed. Clean isolated baseline:1118 passed,28 corpus-dependent
skips, one existing upstream Starlette/httpx warning. Architecture and new-file
Ruff pass. The seven frozen scalar-corrected source hashes remain valid. Full
release: **1,152 passed, 28 corpus-dependent skips**, one upstream warning,
252.84 s. Independent review and final primary verification follow below.

Project remains advanced prototype / pre-pilot with zero accepted field cases.
No standards certification, calibrated confidence or operational line enablement.
Dash, workbook, source captures, app database and preview processes are unchanged.

## Independent review correction

One Important finding, no Critical or Minor findings: the study decision checked
harmful passes only in validation, so a known harmful development pass could be
ignored. A real two-incident regression reproduced that erroneous pass before
the fix and refuses afterward. The decision now checks harmful passes across
both splits. All35 focused tests pass. Corrected code freeze: `5bb9dd2`.

The [original frozen aggregate](validation/THREE_PHASE_ACQUISITION_ENVELOPE_2026-10-26.json)
is preserved with its source binding at `57576b7`; the corrected full rerun is
published separately. No scalar threshold, source model or validation grid was
tuned. The natural usage reset allowed the original interrupted reviewer to
finish; there was one completed independent review and no re-review.

The full corrected rerun has identical552 case rows,1104 workflow outcomes and
all numerical aggregates. Only the corrected decision-reason wording and two
source hashes differ. All29 corrected hashes verify against current code and all
29 original hashes verify against the historical source. Numerical failures remain
zero and the scientific adoption decision remains failed.

## Final verification and delivery

Final serial primary after the review correction: **1,181 passed, no skips**,
one existing upstream Starlette/httpx warning,347.15 s. The complete corrected
study has552 identical incident rows and1104 workflow outcomes;29 current and
29 historical source hashes verify. Architecture/self-tests and all new-file
Ruff checks pass;40 repository-wide findings are pre-existing in unchanged files.

Reviewed changes are integrated into main. QA, RED/GREEN evidence, review and
execution ledger are saved locally under ignored
`out/qa/three-phase-acquisition-2026-10-26/`. Production source, prior historical
artifacts and both local Dash findings remain unchanged. No new deferred Minors;
the earlier malformed-frequency inspection fallback remains a pending software
fix. The candidate remains offline because the scientific adoption criteria fail.
