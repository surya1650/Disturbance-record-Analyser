# Conditional sequence-error budget — started 2026-10-26, verified 2026-10-27

**The supplied-cap additive-error study passes; physical I2 accuracy and production
adoption do not follow.** All 80 parsed metrology records and 73,160 DSP supports
completed with zero numerical failures. In the 56 records that actually satisfy
the declared sample caps, all 51,212 observations stay within the conditional
bound. The separate physical-reference monitor exposes up to 1.14386 A of
rounded-window kernel bias. No location gate or existing DSP consumer changed.

## Utility and assumptions

Added pure functions in `src/dranalyser/dsp/sequence_budget.py`:

- `dft_noise_radius` bounds the matched linear DFT/mimic operator from an explicitly
  supplied sample-amplitude error cap and verified uniform local grid.
- `i2_budget` propagates three primary-A complex-current error circles to I2,
  with required provenance, conservative weak-signal/relative-error screens,
  and explicit unsupported/withheld/conditional statuses.

Every return has `authorizes_location=false`. Provenance records an assumption;
it does not prove that assumption. Missing radii or provenance refuse. A zero
radius is permitted only as an explicitly supplied assumption, not as a default
for unknown noise. No waveform residual, ADC scale, manufacturer name or clock
metadata is promoted into a complete measurement-error bound.

For primary RMS phase errors `rA,rB,rC`, the triangle inequality gives
`rho=(rA+rB+rC)/3`, without independent/white-noise assumptions. The function
adds a published numerical guard of 64 ulps of the largest measured phase.
With `L=max(abs(measured I2)-guarded_rho,0)`, a positive L yields relative bound
`guarded_rho/L`. Conditional status requires L at least
`max(.01*(abs(measured I1)+guarded_rho),1e-6 A)` and relative bound at most 5%.
A zero lower endpoint remains indeterminate; it is not replaced with an invented
nonzero relative-error denominator. These are study policies and float guards,
not a calibrated protection acceptance limit or certified interval arithmetic.

The matched-kernel sample bound includes both mimic boundary samples, initialized
first support and full/half-cycle normalization. Its L1 factor is sqrt(2) without
mimic; with `b=exp(-(1/fs)/max(tau,1e-6))`, `g=1-b*exp(-j*2*pi*freq/fs)` it is
`sqrt(2)*[(n-1)/n+(1+b)/(n*abs(g))]`, plus a 64-ulp coefficient guard. It bounds
the linear operator, not all floating-point cumsum error or the difference
between that operator and a physical fundamental. Validation comparison
tolerances are explicitly 1e-8 primary A and 1e-8 relative.

## Independent validation and scope masks

Code/protocol freeze `34a6cb3`. New development data use 48 Hz / 3500 Hz and
validation data 52 Hz / 2600 Hz, with different prefault span, sequence phase and
seeds. Source signals are six-channel synthetic metrology states, not a physical
line network; no fault locator or km-accuracy claim is used. They pass through
20-bit integer ASCII COMTRADE, real secondary scales/ratios, public parsing and
actual DSP. Positive current steps from 100 to 1000 primary A; physical negative
current is 0/.1/10/100 A. Source signals and ideal analog references are retained
separately. No field inputs or historical published grids are retuned.

Quantization and bounded uniform/colored/square perturbations have explicit PEAK
caps, not Gaussian RMS estimates. The five-tap colored filter preserves that cap.
Each supplied cap includes ADC half-step. The ideal reference is the same DSP
kernel applied to independently generated noiseless analog inputs at the same
frequency/tau/time support. Independent direct-coefficient unit tests separately
verify operator agreement, first-window behavior and adversarial error algebra.

| Split | Records | Within-cap observations | Conditional statuses within caps | Bound misses within caps | Maximum observed error / bound |
|---|---:|---:|---:|---:|---:|
| development | 40 | 29176 | 4676 | 0 | 0.157022 |
| validation | 40 | 22036 | 3148 | 0 | 0.192181 |

Across both splits: 7,824 within-cap observations receive conditional status and
43,388 withhold, generally for weak I2 or conservative noise radius. The largest
observed additive I2 error is only 0.192182 times its supplied-cap bound. This is
a deterministic bounded-input result, not a statistical confidence percentile.

| Scenario | Valid-cap records | Violated-cap records | Conditional statuses (all scopes) | Out-of-scope radius exceedances |
|---|---:|---:|---:|---:|
| alias | 0 | 8 | 7316 | 7316 |
| colored_large | 8 | 0 | 0 | 0 |
| colored_small | 8 | 0 | 1829 | 0 |
| gain | 0 | 8 | 2343 | 5742 |
| polarity | 0 | 8 | 7316 | 7316 |
| quantization | 8 | 0 | 2337 | 0 |
| square_large | 8 | 0 | 0 | 0 |
| square_small | 8 | 0 | 1829 | 0 |
| uniform_large | 8 | 0 | 0 | 0 |
| uniform_small | 8 | 0 | 1829 | 0 |

The 24 gain/polarity/alias controls intentionally understate the error cap by
providing only ADC quantization, excluding the injected bias. They violate the
caller precondition and are excluded from validated coverage. They produce
20,374 out-of-scope absolute-radius exceedances and 16,975 conditional statuses.
These are explicit counterexamples to treating a declared cap as verified truth.
All-scope totals (24,799 conditional / 48,361 withheld) must not be presented as
24,799 validated field-quality passes. All outputs remain non-authorizing.

## Separate physical-kernel bias found

Case 21 (development, physical I2=10 A, quantization only) contains 508 supports
with conditional additive status but more than 5% physical-I2 error. These
supports satisfy the sample caps and the matched-kernel additive bound. Their
physical error lies outside that bound’s stated reference domain. The maximum
ideal matched-kernel physical bias in the matrix is 1.1438625 A; integer-grid
validation is at numerical noise (approximately 1.01e-11 A).

The development grid has `fs/f=72.9166667`, but the existing DFT uses 73 samples.
For a real sinusoid its raw complex estimate is `Y=P+conj(P)*g2`, where
`g2=mean(exp(-2j*w*t))` on the window. Rounding makes g2 nonzero: the conjugate
positive-sequence component leaks into negative sequence. The independently
constructed direct kernels confirm the existing operator rather than masking
its bias. This finding supports a separate exact-frequency/conjugate-basis DSP
correction study, including mimic gain and half-cycle/initialization behavior.
It is not fixed by tightening a noise threshold or by claiming the additive
budget bounds every physical error. No existing DSP behavior changed here.

## Decision and remaining work

Use this as a conditional mathematical utility and regression benchmark.
Production use would need defensible bounds for all claimed error components,
plus physical-kernel, gain/polarity/CT, frequency-model and anti-alias provenance.
Unbounded Gaussian noise does not acquire a hard amplitude cap from a residual
fit or from the observed maximum of one capture. No field-noise calibration,
clock alignment, standards certification or operational approval is implied.

Next actionable software work is to reproduce and validate a correction for
fractional-cycle conjugate leakage, updating the matched-kernel noise bound and
independent operator tests together. That production-DSP change requires fresh
full-record and Stage-A regressions before adoption. The previously deferred
malformed-frequency inspection fallback also remains pending. The five-hour
same-chat continuation is active under the user’s autonomous-work instruction.

## Reproduction and verification

[Complete 80-case evidence](validation/SEQUENCE_ERROR_BUDGET_2026-10-26.json)
binds 12 normalized UTF-8/LF source files. Every record/observation denominator and
assumption mask remains visible. Typed failures retain planned records; a valid-
assumption bound miss or numerical failure returns failed evidence/CLI exit 2.
Existing/racing outputs are preserved and nonfinite JSON is rejected.

```powershell
$env:PYTHONPATH='src;.'
$env:OPENBLAS_NUM_THREADS='1'
& 'E:\dr analyser\.venv\Scripts\python.exe' -m pytest tests/test_sequence_budget.py tests/test_sequence_budget_validation.py -q
& 'E:\dr analyser\.venv\Scripts\python.exe' scripts/sequence_budget_validation.py --output out/qa/sequence-budget-new-run.json
```

Focused tests: 77 passed. Isolated baseline: 1,153 passed / 28 corpus-dependent
skips, one existing upstream warning, 355.94 s. Full release: **1,230 passed /
28 corpus skips**, one upstream warning, 95.83 s. Architecture and new-file Ruff
pass; existing consumers are unchanged, so the previous Stage-A 10,000 run remains
historical, not a new validation of this unwired utility. Independent review and
final primary verification are recorded below. Project remains advanced prototype /
pre-pilot with zero accepted field cases. Dash and source inputs are unchanged.

Fresh independent whole-branch review found no Critical, Important or Minor
issues. It independently ran all 77 focused tests and verified the 12 source
hashes. Review excluded physical-kernel correction, proof of caller caps, formal
floating-point intervals and location readiness; none is claimed here.
Final primary regression: **1,258 passed, no skips**, one existing upstream
Starlette/httpx warning, 93.32 s. QA, review and execution ledger are retained in
ignored `out/qa/sequence-error-budget-2026-10-26/` before worktree archival.
