# Conditional negative-sequence error budget

## Purpose and scope
User authorized further autonomous software/numerical work, no new field data,
and analyser integration/push. The preceding full-record study failed adoption:
per-phase waveform quality cannot establish I2 accuracy or exclude coherent gain,
polarity or alias bias. Build a mathematically conditional error-budget utility,
not a new automatic location gate. No existing production consumer, frozen
candidate/oracle, historical artifact or Dash finding changes.

Approaches: fitting a tighter residual threshold against the published colored-
noise counterexample would tune to validation and leave coherent bias invisible.
A covariance/SNR estimate would require noise-distribution and correlation
assumptions not established by these records. Choose deterministic propagation
of caller-supplied bounds, with explicit provenance and missing-bound refusal.
Validate separately on new bounded perturbations. All returns have
authorizes_location=false; there is no confidence or certification claim.

## Conditional mathematics
Inputs to i2_budget are three measured primary RMS complex currents in A/B/C
order and three nonnegative finite error radii in primary A, with a required
nonempty provenance string. The assumption is |measured_phase-true_phase| <= radius
for each phase, including every error component the caller claims to cover.
Let a=exp(j*2*pi/3). I2=(IA+a^2*IB+a*IC)/3 and I1=(IA+a*IB+a^2*IC)/3.
The deterministic I2 perturbation radius is rho=(rA+rB+rC)/3, without independence
or white-noise assumptions. Add a published numerical guard of64 ulps of the
largest measured phase magnitude. This is conservative float arithmetic, not
certified interval arithmetic. Report the input radius and guard separately.

The true I2 magnitude lies in [max(abs(measured I2)-guarded_rho,0),
abs(measured I2)+guarded_rho]. For positive lower endpoint, the relative error
bound is guarded_rho/lower. Conditional bounded status requires lower >=
max(.01*(abs(measured I1)+guarded_rho),1e-6 primary A) and relative bound <=.05.
Otherwise withhold; do not replace a zero lower endpoint by an invented signal
floor in the relative-error denominator. Missing bounds/provenance, malformed or
nonfinite inputs, or nonfinite propagated outputs return unsupported JSON-safe
diagnostics. The1%/1e-6/5% values are study policies inherited from prior studies,
not calibrated engineering acceptance limits. Unknown gain/polarity/alias/CT or
frequency-model errors cannot be bounded by a sine residual or ADC quantization.

## Matched DSP-kernel bound
dft_noise_radius returns a conditional primary-A phasor radius from a supplied
nonnegative sample-error amplitude bound, positive finite fs/freq and optional
nonnegative mimic-filter tau. Require explicit uniform_grid=true. Match the
existing n=round(fs/freq), or max(n//2,2) for half cycle. Unsupported n<2 or
unrepresentable arithmetic refuses. No allocation proportional to n is needed.
For no mimic filter the coefficient L1 bound is sqrt(2). With mimic filter,
b=exp(-(1/fs)/max(tau,1e-6)), g=1-b*exp(-j*2*pi*freq/fs), and the upper bound is
sqrt(2)*[(n-1)/n+(1+b)/(n*abs(g))]. This includes both boundary samples and remains
conservative for the initialized first window. Add64 ulps to the coefficient
factor before multiplying the sample bound. Publish that factor. This bounds
the exact linear operator under a uniform local grid; it does not establish
the physical fundamental, frequency-model correctness, global clock alignment,
or total floating-point cumsum error. Numerical validation reports tolerance
separately; no formal floating-point interval certificate is claimed.

## Independent validation
Unit tests use direct complex kernel coefficients independent of production DSP,
including the initial mimic sample, half/full windows, fractional samples/cycle,
tau0/.02/.08/None, malformed data and very small/large numerical scales. Construct
adversarial phase errors that attain the algebraic triangle bound, plus random
complex perturbations. Test weak/balanced I2 and absent bounds explicitly.

A new metrology record generator creates six-channel integer ASCII COMTRADE,
parsed normally, with known positive current stepping100->1000 primary A and
negative current0/.1/10/100 primary A. These signals test metrology, not a line
network: do not call a fault locator or claim km accuracy. Use20-bit ADC,
64 secondary-A /150 secondary-V full scale, CT1000:1 and ideal VT2000:1.
Development48 Hz at3500 Hz, prefault .14 s, negative-sequence phase .37 rad,
seed4854. Validation52 Hz at2600 Hz, prefault .17 s, phase .91 rad, seed5854.
Fault-state duration .36 s plus .06 s tail. Voltages provide a balanced220 kV
nominal three-phase reference. Current clearing is explicit; true support has
1.5-cycle blanking and a .5-cycle end guard. This is not EMT or field identity.

Ten scenarios per split/I2: quantization only, uniform/colored/square bounded
noise at .001/.01 times(1000+I2) primary-A PEAK, then gain1.2, IA polarity reversal
and IA fundamental alias with .15 times(1000+I2) primary-A peak. Colored noise
uses a five-tap moving average of bounded uniform noise, preserving the cap.
Every supplied sample bound includes the ADC half-step. The three coherent-bias
controls deliberately omit their bias from the supplied ADC-only bound and are
explicit assumption-violation examples, never successful bound validation.
Total80 records:56 bounded cases and24 deliberately underclaimed-bound controls.

Analyse actual parsed records. Compare actual phasors against the same production
DSP kernel applied to the separately retained ideal analog waveform, at the same
tracked frequency/tau and sample support. Direct-kernel unit tests establish
independent operator agreement. This isolates additive acquisition perturbation;
it excludes frequency/window/DC-model error relative to a physical fundamental.
Evaluate every supported observation, keep per-case counts, worst observed
radius/relative-bound margins and conditional/withheld totals. Use1e-8 primary A
absolute comparison tolerance plus1e-8 relative tolerance, reported explicitly.
Record actual sample-cap satisfaction separately. No violated assumption enters
the successful-coverage denominator. Preserve typed case failures and planned
80-record denominator; unsupported observation counts remain visible.

## Evidence, decision and delivery
Freeze source/protocol before the full matrix. Strict finite JSON, exclusive
output publication and normalized UTF-8/LF source manifests. Any numerical failure
or within-assumption bound miss fails the numerical study and exits2; successful
conditional validation does not authorize production adoption. Historical data
are immutable. Review once in a fresh context, fix Important findings in one TDD
pass, run full suites serially, integrate/push under existing authorization and
preserve QA before native worktree archival. Maintain the five-hour same-chat
follow-up if quota interrupts work. The prior malformed-frequency inspection
fallback remains separate pending software work.
