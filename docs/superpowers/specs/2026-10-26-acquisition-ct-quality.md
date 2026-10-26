# Independent acquisition and CT-quality validation

Date: 2026-10-26. User authorized autonomous execution and GitHub integration.

## Purpose
Investigate the noisy-input refusals without new field data. Independently generate
secondary-referred nonlinear CT waveforms, test a frozen noise-aware candidate,
and publish every planned outcome, including failures and harmful misses.

## Physical oracle
Current balance is u = is + im(lambda), with dlambda/dt = Rb*is. Excitation
is continuous odd piecewise linear, unsaturated inductance 10 H, saturated
inductance 0.0005 H, knee flux linkage 0.03 V s. Ratio is 1000:1. This is a
resistive-burden, memoryless excitation model with initial flux bias; it does not
model hysteresis, true remanence, leakage or a manufacturer's CT. Integrate with
implicit trapezoidal substeps; test linear analytic response, balance, volt-second
identity, convergence and odd symmetry before using it as an oracle.

## Candidate and adoption
Use a fixed least-squares fundamental and harmonics 2-5, constant and exponential
DC nuisance bases (10, 30, 100 ms). Report residual RMS and coherent harmonic RMS
relative to fitted fundamental. Fixed candidate budgets: residual 2%, harmonics
3%, and peak residual 8% of fundamental RMS. At least four cycles and 16 samples
per cycle are required. This candidate cannot certify magnetic CT saturation;
its labels are candidate_pass, distortion, noise_or_transient, unsupported.
It has no authority to change current production gates. Adoption requires zero
harmful CT misses (complex fundamental error >5%) on a disjoint holdout plus
non-CT distortion/dropout controls. Publish failures, never tune on holdout.
A failed adoption gate completes this study with production refusals retained.

## Protocol
Development: 50 Hz, 1000/2400 Hz, phase 0/0.7 rad, DC 0/1, decay 40 ms,
burden 0.2/1/2 ohm, bias 0/0.7 knee. Holdout: 47/53 Hz, 1200/4800 Hz,
phase 0.31/1.23 rad, DC 0.4/1.4, decay 65 ms, burden 0.35/0.8/1.6 ohm,
bias -0.6/0.4 knee. RMS primary current 1000 A, duration 0.3 s. Each CT
case is scored clean and with 1% primary RMS Gaussian noise. Controls: clean,
0.1%/1%/5% white noise, 1% colored noise, 1% quantization step, 10% third
harmonic, clipping and a missing quarter-cycle. Analysis excludes the first
1.5 cycles. Seeds are deterministic and disjoint. Truth is derived only from
oracle flux and independent complex fundamental error, never the candidate.

## Boundaries
No operational enablement, clock promotion, confidence calibration, new inputs,
Dash changes, source-file changes or historical hash rewriting. Frozen reports
retain their original source revision. New evidence uses UTF-8/LF source hashes.
Serial full tests avoid workbench fixed-port interference. Record test and review
logs locally. One fresh whole-branch review; fix Important findings with TDD.
