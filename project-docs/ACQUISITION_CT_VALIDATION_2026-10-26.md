# Independent acquisition / CT-quality validation — 2026-10-26

The frozen research candidate separates bounded noise from coherent waveform
distortion in this experiment. **306/306 outcomes completed, zero numerical
failures, zero candidate passes among 136 outcomes with >5% CT fundamental
current error.** The disjoint holdout contributes 104 of those harmful outcomes.
Production fault-location and CT-quality gates are unchanged. No previously
refused incident is newly authorized by this study.

## What was tested

The new test-only oracle solves secondary-referred current balance
`u = is + im(lambda)` and `d(lambda)/dt = Rb * is` using a continuous odd
piecewise-linear excitation curve and implicit trapezoidal substeps. Independent
checks cover current balance, volt-second identity, analytic linear response,
odd symmetry, knee continuity, nonnegative flux/excitation product and substep
convergence. No production synthesizer, detector or fault locator generates CT
truth. Flux state and complete-cycle complex-current quadrature determine truth.

This is a resistive-burden toy CT, with a 1000:1 ratio, 10 H unsaturated and
0.0005 H saturated inductance, 0.03 V s knee, sinusoid plus decaying DC, and
initial flux bias. Initial bias does not model hysteretic remanence. The
[SEL CT-suitability paper](https://cdn.selinc.com/assets/Literature/Publications/Technical%20Papers/6096_DetermineCurrent_991007_Web.pdf)
describes burden and excitation modeling. The
[MathWorks nonlinear-inductor documentation](https://www.mathworks.com/help/simscape-electrical/ref/nonlinearinductor.html)
describes flux/current saturation relationships and distinguishes simpler curves
from hysteretic models. These motivate the equations, not the synthetic parameter
values or an assertion of standards conformance.

The candidate fits a fundamental, harmonics 2–5, constant and fixed 10/30/100 ms
exponential nuisance terms. It reports residual RMS, residual peak and fitted
harmonic RMS against fundamental RMS. Frozen limits are respectively 2%, 8%
and 3%; at least four cycles and 16 samples/cycle are required. Its result is
explicitly `candidate_pass`, **never production eligibility or proof of CT health**.
After independent review, a 1e-9 secondary-A RMS absolute fundamental floor
supplements the relative 1e-5 prominence guard. This is a numerical cutoff,
not a calibrated engineering current or signal-to-noise requirement.
`authorizes_location` is always false. The legacy third-difference detector is
scored alongside it, without changing its result.

Protocol/spec and candidate were committed before the full holdout run
(candidate freeze `4005c7d`). Development and holdout differ in frequency, sample
rate, phase, DC magnitude/decay, burden, initial flux bias and random seeds.
Parameters and seeds are reproducible from the runner and tracked evidence.
There are 144 physical CT parameter realizations, each scored without noise and
with 1% RMS white measurement noise, plus 18 non-CT controls: **306 waveform
outcomes, not 306 independent physical incidents**. Analysis starts after 1.5
cycles. Harmfulness means >5% complex fundamental change caused by the CT before
measurement noise, measured by a separate complete-cycle quadrature. It is a
study threshold, not a protection acceptance limit or fault-location error bound.

## Results

| Stratum | Outcomes | Candidate pass | Harmful CT outcomes | Harmful CT passed | Legacy flagged |
|---|---:|---:|---:|---:|---:|
| Development | 105 | 61 | 32 | 0 | 60 |
| Holdout | 201 | 69 | 104 | 0 | 156 |
| Total | 306 | 130 | 136 | 0 | 216 |

The candidate rejects all eight harmful control outcomes: 5% white noise,
10% third harmonic, clipping, and quarter-cycle dropout in each split. It accepts
all ten bounded controls: clean, 0.1%/1% white noise, 1% RMS colored noise and
1% quantization step in each split. The legacy screen flags the 1% white,
colored and quantized controls in both splits, and also the holdout's 0.1% white
noise. Conversely, it misses both 10% third-harmonic controls. This confirms that
its third-difference flag cannot by itself distinguish noise from distortion.

Of 152 CT outcomes at or below the chosen 5% error threshold, the candidate still
refuses 32 (8 development, 24 holdout). The maximum modeled CT fundamental error
is 25.824%. No accuracy claim is made for noise beyond the frozen budgets, weak
phases, or negative-sequence fault-location sensitivity. Colored noise is one
five-tap moving-average realization per split; quantization uses a synthetic
step, not a measured ADC transfer characteristic.

## Adoption decision and remaining software work

The **bounded-study gate passes**: the holdout contains harmful CT cases and no
harmful CT/control passes or numerical failures. Keep production gates unchanged.
This gate is necessary evidence for integration, not a sufficient operational
approval: the study is single-current-channel, fixed-frequency and lacks voltage
quality, three-phase weak-current floors, frequency-error/clock-drift stress and
full parsed-record main/reviewed-stage acquisition integration. The candidate's
exponential nuisance fit also needs adversarial distortion tests before it can
be trusted to clear a legacy flag. No production code imports this candidate.

Next software work can use this frozen benchmark as regression evidence while
adding a new disjoint full-record study: CT before ADC/noise, complete current
families and voltage channels, sample-rate/frequency uncertainty, transient and
short windows, aliasing, spikes, persistent gain/polarity faults and source-bound
main/stage gates. Keep unsupported acquisition, clipping, weak negative sequence,
clock provenance and model eligibility gates authoritative. Do not tune against
this published holdout. More realistic CT excitation/hysteresis and burden models
need separately justified parameters. Field acceptance, calibration and operating
authorization still require suitable independent evidence and accepted cases.

## Reproduction and evidence

Current corrected aggregate: [ACQUISITION_CT_ENVELOPE_2026-10-26_CORRECTED.json](validation/ACQUISITION_CT_ENVELOPE_2026-10-26_CORRECTED.json).
The [original frozen aggregate](validation/ACQUISITION_CT_ENVELOPE_2026-10-26.json)
remains unchanged and binds the source at `e204a25`. Corrected candidate freeze:
`608cd33`. All 306 outcome rows and numerical scores match the original exactly;
only policy metadata and source hashes differ. The original seven hashes verify
against their historical source; the corrected seven verify against current code.
Use existing environment, `PYTHONPATH=src;.` and `OPENBLAS_NUM_THREADS=1`:

```powershell
& 'E:\dr analyser\.venv\Scripts\python.exe' -m pytest tests/test_ct_quality_oracle.py tests/test_acquisition_ct_validation.py -q
& 'E:\dr analyser\.venv\Scripts\python.exe' scripts/acquisition_ct_validation.py --output out/qa/acquisition-ct-new-run.json
```

The output path must be new. Per-case exceptions retain failed rows and planned
denominators; numerical failures produce CLI exit 2. A scientific gate failure
with completed numerical execution is retained as evidence rather than hidden.
Source manifests bind seven files with normalized UTF-8/LF text (BOM excluded).
Historical aggregates and source manifests were not rewritten. No production
source changed, so the prior Stage-A 10,000 result remains historical regression
evidence, not a newly rerun CT-model acceptance result.

New focused checks after review correction: **31 passed**. Clean isolated baseline: **1,087 passed,
28 corpus-dependent skips**, one upstream Starlette/httpx deprecation warning.
Release worktree: **1,116 passed, 28 corpus-dependent skips**, one upstream
warning, 1797.27 s elapsed. Review and primary verification
will be recorded after completion.

Project level remains **advanced prototype / pre-pilot**, zero accepted field
cases; no TB854 certification, calibrated confidence, or new operational line
enablement. Dash findings, workbook, source captures, app database and preview
processes remain outside this change.

Architecture and its guard self-tests pass. Ruff passes for every new Python
file; the repository-wide check retains 40 pre-existing findings, all in
unchanged files. Both local Dash findings retain their recorded SHA-256 hashes.

Independent review found one Important issue and no Critical/Minor issues: a
DC-dominated sub-nanoampere fundamental could pass the relative-only guard. Two
regressions failed before the fix and pass after it, with and without DC. The
absolute RMS floor fixes it. The frozen grid and noise/harmonic budgets were not
tuned; the complete corrected run has zero failures and identical outcomes. The
reviewer explicitly left operational suitability, three-phase location safety
and field acceptance outside this offline study. Production gates stay unchanged.
