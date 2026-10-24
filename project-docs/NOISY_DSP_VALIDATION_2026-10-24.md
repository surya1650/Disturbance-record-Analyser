# Noisy waveform DSP and local timestamp recovery

Project level remains **advanced prototype / pre-pilot, zero accepted field
cases**. This continuation fixes silent acceptance of invalid local acquisition
timing and adds bounded noisy-waveform evidence. It does not establish TB854
certification, calibrated confidence, field accuracy or noisy-input readiness.

## Changes and reproduced defects

The public COMTRADE reader previously fitted DAT timestamps to a uniform grid
without validating their continuity. Repeated/reset/gapped/nonfinite stamps,
unusable timing and nonconsecutive sample numbers could therefore lose their
acquisition defects. Invalid timestamp multipliers could silently become one.
Public-parser regressions reproduced these behaviors before implementation.

The reader now retains `notes.timestamp_recovery`: declared/recovered/invalid
status, method, multiplier, fitted period and maximum trend/interval deviations.
Invalid DAT timing adds blocking `TIME-DAT`; invalid sample numbering adds
blocking `TIME-SAMPLE`. Source CFG/DAT hashes and clock fields remain intact.
No samples, scaling ratios or polarities are repaired. A finite display-only
placeholder normally accompanies invalid recovery so inspection can continue; its rate
must never be advertised as recovered acquisition or used to authorize location.
One deferred malformed-metadata edge remains: nominal frequency 1e308 can overflow
that display fallback's rate to infinity. The record stays blocked, but its
inspection path may fail. This is not accepted-location or field evidence.
The main section adapter and reviewed stage window already refuse blocked input.
When a finite positive DAT fit exists but continuity policy fails, its rate is
retained as `display_rate_basis: untrusted DAT fit; inspection only`. That avoids
distorting diagnostic waveform comparisons with an arbitrary display rate; the
invalid status and acquisition block remain, with no location permission.

Declared single-rate CFG remains authoritative, including zero DAT stamps. For
`nrates=0`, at least three finite, strictly increasing stamps are required, with
a positive finite centered least-squares slope. Subtracting the timestamp origin
before scaling protects local precision at large constant offsets. Maximum
interval and fitted-trend residual deviations must each be <=10% of fitted
period. Nonunity multipliers are applied before fitting; nonpositive/nonfinite/
malformed multipliers block. Sample numbers must be finite, nonnegative,
integral and consecutive. This **10% tolerance is an executor-selected bounded
software policy, not a COMTRADE standard tolerance, UTC error bound or drift
correction method**. It can refuse otherwise usable data outside this policy.

That cost occurs in the existing DHONE Main-1 corpus: 3,624 samples have 828-845 us
intervals (median 833 us), but the maximum accumulated linear-fit residual is
0.000343863 s, above the 10%-period policy. The reader now blocks Main-1 as outside
this recovery envelope. The approximately 1200.5 Hz fit remains available solely
for inspection. Main-2's declared 1000 Hz acquisition remains usable. This is not
a claim that Main-1 violates COMTRADE or that its physical sampling clock is
proven faulty. Corpus regressions now assert this explicit policy behavior;
14 existing-corpus direct checks pass, without changing any source recording.
The existing Garividi D60/P444 captures also exceed the accumulated-fit policy
(316.277/307.189 us residuals). Their assignment, corroboration and resolver
suggestions are now withheld; Maradam Main-1's declared 1000 Hz capture remains
usable. Primary verification initially found two outdated corpus expectations
(1,108 passed/two failed); focused corpus workflow checks now require the new
visible blocks. This changes corpus availability, not the recording bytes or
a standard-conformance verdict.

The now-single-usable-terminal report exposed a latent filename bug: slashes in
the station label became report path separators. Five regressions observed RED;
generated report IDs now replace unsafe prefix characters, limit that prefix to
100 characters and retain the hash of the original label. Source station/line
labels remain unchanged. Focused filename and actual corpus workflow checks pass.

Source clock-quality codes retain their previous interpretation. Local recovery
never establishes continuous clock lock, UTC accuracy, E4 alignment eligibility
or same-event/stage identity. E5 remains usable without timestamp synchronization.

## Reproducible raw-waveform experiment

```powershell
$env:PYTHONPATH='src;.'
$env:OPENBLAS_NUM_THREADS='1'
python scripts/noisy_dsp_validation.py --seed 854 --output out/qa/NEW-noisy-dsp.json
python -m pytest tests/test_timestamp_recovery.py tests/test_noisy_dsp.py tests/test_noisy_dsp_validation.py -q
```

The source checkout and test utilities are required. The new helper uses the
previous independent phase-nodal source/fault oracle and sinusoidal state splice,
then writes six-channel primary A/V ASCII COMTRADE pairs and reparses them through
the public reader. No production synthesizer, phasor substitution, quality-flag
override or truth-based root selection is used. Record-level noise is applied
before parsing/DSP. This is not EMT, a real instrument transfer function or a
physical sampling-aperture jitter model.

180 incidents / **360 workflow outcomes**: baseline, weak_R_100 and source voltage
unbalance; AG, BC, ABG and ABC balanced control; waveform noise of 0/0.1%/1%; declared,
rounded, bounded_jitter, clock_skew and gap timing modes. Geometry is the previous
40/60km mixed-section line, fault at 75 km, R=4 ohms, 2400/1200 Hz, remote phase 1.1 rad.
Both main and source-bound reviewed-stage workflows run. Stage identity is
explicitly declared from the known synthetic one-step schedule, not inferred
from field records. A record with no stable eligible stage stays unreviewed and
withheld; the driver no longer attempts to submit an invalid empty review.

Noise is IID real Gaussian per waveform/channel. Sigma is the stated fraction
of the stronger terminal maximum phase RMS, separately for V and I, over the
ideal capture. Thus noise remains nonzero at weak terminals and does not vanish
with negative sequence. This is an absolute family-based noise model; a weak
phase may have far worse relative SNR than the stated percentage. The seed is
854+100*profile_index+10*fault_index. Perturbations are matched across timing
modes and noise amplitudes: these are metamorphic comparisons, not independent
field events or a confidence-calibration sample.

Rounded and jitter modes use timestamp-only CFG (`nrates=0`, multiplier1);
rounded stamps are integral microseconds. Jitter adds uniform +/-5us before
rounding. Clock_skew uses declared rates and shifts both remote CFG dates by
1418 s while retaining identical local samples/support. Gap uses timestamp-only
CFG and adds 10 ms to the second half of remote DAT stamps. Clock skew is metadata
invariance, not successful reconstruction of a physical varying clock error.

## Measured results

Each noise row contains 90 unbalanced workflow outcomes, plus 30 balanced controls.

| Waveform noise | Unbalanced located | Unbalanced refused | Located max error, km | Balanced refused/planned |
|---|---:|---:|---:|---:|
| 0 | 72 | 18 | 1.45e-12 | 30/30 |
| 0.1% | 0 | 90 | unavailable | 30/30 |
| 1% | 0 | 90 | unavailable | 30/30 |

Noiseless gap cases account for all 18 noiseless unbalanced refusals. Each of the
four nongap timing modes locates all 18 noiseless unbalanced outcomes. Overall:
**72 located / 288 refused / zero numerical failures**, with 270 unbalanced and 90
balanced outcomes. Both workflows independently locate 36/180 and refuse 144/180;
all 45 balanced controls per workflow refuse. Located errors come entirely from
noise-free cases: they provide **no positive-noise accuracy evidence**.

All 72 gap outcomes refuse. All 36 metadata clock-skew comparisons (three profiles
x four faults x three noise levels), in both workflows, retain corresponding
declared-rate outcomes without any applied clock correction or E4 promotion.
Rounded/jitter local recovery preserves clean chainage within numerical roundoff.
These results do not establish recovery from time-varying clock drift, missing
events, unknown trigger latency or automatic inter-terminal record pairing.

The key practical limitation is **zero location coverage at the two positive
noise levels in this grid**. On baseline AG at .1% noise, the current third-
difference saturation detector marks phase-current channels, and local stage
quality also refuses. The synthetic input contains Gaussian noise and no
physical CT saturation; the diagnostic is therefore a quality-screen response,
not proof of magnetic CT behavior. Weak noisy inputs can additionally lose
stable stage inventory or fault classification. Per-terminal saturation channels,
severity, clipping, classification and stage-quality reasons are retained in the
aggregate. No gate was relaxed or tuned to increase this grid's acceptance.

The [tracked aggregate](validation/NOISY_DSP_ENVELOPE_2026-10-24.json) retains every
case, recovery/clock metadata, hashes, frequencies, DSP quality, refusal reasons,
conditional error and witnesses. Every workflow/noise/timing/source/fault margin
includes separate unbalanced and balanced cohorts. Genuine configuration is
validated before case execution. Unexpected per-case exceptions, including
numerical-library ValueError, retain both failed workflow outcomes and fail the
run explicitly. Complete case output, including diagnostics, passes strict JSON
validation before either outcome is appended; nonfinite output becomes explicit
JSON-safe failed evidence without fabricated acquisition values. Configuration
errors remain exceptions. Strict JSON is computed before exclusive output creation;
existing evidence and concurrently published files cannot be overwritten.

## Verification, review and delivery

Baseline worktree: 1,033 passed/28 corpus-dependent skips, one upstream
Starlette/httpx warning, 186.59 s. Timing fixtures were corrected before accepting
the intended RED failures. Timestamp/clock focused 49 pass, including four bad
multiplier regressions. Task1 full 1,059 passed/28 skips, 202.60 s preceded the final
malformed multiplier test; subsequent full suites cover that final guard.
Task2 initial focused 12 pass; a real weak-noisy case exposed the driver's empty
stage review, reproduced RED then fixed. Missing quality evidence and mixed-
control strata were separately observed RED. Final focused 15 pass, 7.21 s.

Fresh Stage-A 10,000 **PASS**, 53.1 s: 9,242 located/758 refused; clean 4,258 located/
25 refused, clean p95 .4361%, all-located p95 6.677%, saturated located p95
39.805%, zero impossible outputs without a caveat. Architecture direct/self-
tests and focused Ruff pass. Historical numerical artifacts/oracles stay frozen.
Final pre-review worktree suite: **1,075 passed, 28 corpus-dependent skips**,
one upstream warning, 251.70 s. All 16 new source hashes and both historical
section/source manifests match; prior oracles/artifacts have no diff. All 72
workflow clock-skew comparisons match exactly and no alignment is promoted.
Both local Dash findings retain their previous hashes. Independent review and
publication evidence follow after completion.

Fresh read-only whole-branch review (gpt-6-astra high) independently passed 64
focused checks and verified all 360 cases, 16 source hashes, clock-skew invariance
and gap refusal. No Critical findings; two Important findings reproduced by seven
RED regressions: empty ASCII timing fields were zero-filled before validation,
and numerical-library ValueError/nonfinite diagnostics could lose denominators.
The single fix pass preserves missingness in the first two ASCII columns and
blocks acquisition; it validates configuration before execution and complete
case output before atomically recording either workflow. All 70 focused
timestamp/clock/DSP/runner checks pass, 14.55 s. There is no second review.
The subsequent existing-corpus compatibility check exposed the display-rate
effect above; an independent synthetic regression observed RED, then retained
the untrusted fit without relaxing the acquisition block.71 focused checks now
pass, 8.95 s, plus 14 existing-corpus direct checks. The final manifest additionally
binds the updated corpus regression source.

Final corrected worktree suite: **1,082 passed, 28 corpus-dependent skips**,
one upstream warning, 214.02 s. Final regenerated experiment retains 360 outcomes,
72 located/288 refused/zero failed. Every nongap case exactly matches the
pre-review experiment; gap cases all stay blocked/withheld, with untrusted
display-rate provenance (one diagnostic classification/reason changes). All 17
final source hashes match. All historical numerical 4/section 10/source 10 manifests
also match current sources, and their artifacts remain unchanged. Architecture
direct/self-tests and focused Ruff pass; both Dash hashes remain unchanged.
The subsequent primary corpus checks and bounded report-name fix above are
covered by the final delivery suite recorded below; the final manifest additionally
binds their regression/report sources (20 files total).
Final release worktree: **1,087 passed, 28 corpus-dependent skips**, one upstream
warning,196.21s. The concurrent primary run reached1,114 passed but one HTTP
upload test reset its connection; both suites use fixed local ports8241-8243.
The upload test passed alone1.99s. Full suites must run serially on this host;
the final serial primary result follows below. The regenerated20-source study
has exactly unchanged numerical/workflow outcomes and metadata.

Final serial primary checkout: **1,115 passed, no skips**, one upstream
Starlette/httpx warning,190.99s. No software/test changes were needed for the
parallel-server connection failure. Final architecture direct/self-tests,
focused Ruff, all20 evidence hashes and the historical manifests pass. The
implementation and final verification evidence are published through Git history;
delivery/cleanup confirmation follows after remote verification.

One Minor is deferred: grossly malformed nominal frequency 1e308 can overflow
the invalid-record display fallback. Input remains blocked, but inspection can
fail. Review scope rulings retain the current noisy-input coverage limitation,
defer wider EMT/instrument/noise/physical-drift/field and binary/multirate studies,
and do not validate broader malformed multirate/truncated binary handling or
timestamp ticks beyond float64 resolution. Exclusive publication is not a
crash/disk-full transaction; interruption during the final write can leave partial
new evidence. These limits do not authorize location or confidence claims.

## Pending work and limits

A noise-aware acquisition/CT quality model needs independently validated
distortion/CT scenarios and sensitivity analysis before gate changes are justified.
Remaining software studies include varying frequency/clock drift, ADC quantization,
colored/correlated noise, binary format noise roundtrips, multirate acquisition,
CT/CVT transient reconstruction and wider line physics. Timestamp integrity
policy does not recover missing samples or authorize UTC synchronization.
Confidence calibration, patrol-confirmed field acceptance and event-effective
electrical/scaling settings still require independent evidence. No operational
line was enabled, and no Dash findings, workbook, field record, app database or
preview process was changed.
