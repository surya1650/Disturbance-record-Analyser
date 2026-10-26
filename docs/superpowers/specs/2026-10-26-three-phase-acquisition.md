# Three-phase, full-record acquisition / CT-quality study

## Purpose and approach
Extend the frozen scalar study through independent phase-network waveforms,
secondary CT response, noise, ADC encoding, public COMTRADE parsing, actual DSP,
main location and source-bound reviewed-stage location. User authorized autonomous
execution, no new field data, and analyser integration. Work inline with one fresh
whole-branch reviewer. Keep Dash, sources, database and preview processes unchanged.

Alternatives considered: replacing the legacy gate immediately would extrapolate
single-channel evidence; another isolated waveform sweep would omit the requested
acquisition chain. Choose a full-record research harness with no gate override.
No production code or frozen candidate/oracle/historical evidence is modified.

## Independent signals and acquisition
Use the independent phase-nodal oracle on the existing 40/60 km series geometry,
fault at 75 km, contact resistance 4 ohm. Faults AG, BC, ABG and ABC. Each terminal
has three currents and three voltages, known fault inception, trip and clearing
digital signals. Quiet/fault/cleared states are sinusoid splices, not full EMT.
CT scenarios add decaying DC during the fault before the independent secondary-
referred CT circuit, using its already-tested piecewise excitation curve. Initial
flux bias is not hysteretic remanence. Ratio 1000:1; VT conversion 2000:1 is ideal.
Apply CT before noise/defects, then quantize to signed 20-bit ADC counts, with
current full scale 64 secondary A and voltage full scale 150 secondary V. Encode
scale, ratios, secondary units and finite ADC rails in real ASCII CFG/DAT files.
Parse with the public parser; feed those Records to actual production workflows.

Development: 49 Hz, S/R rates 2400/1600 Hz, remote rotation .63 rad, prefault
.14/.181 s, fault duration .36 s, DC multiplier .7, decay .055 s, burden .6 ohm,
initial flux .3 knee, seed 2854. Profiles baseline, weak_R_100, voltage_unbalance.
Validation: 51 Hz, 3200/2000 Hz, remote rotation 1.37 rad, prefault .16/.193 s,
duration .39 s, DC multiplier 1.2, decay .085 s, burden 1.3 ohm, flux -.45 knee,
seed 3854. Profiles baseline, weak_R_10000, phase_impedance. These are new grids;
the earlier published holdout remains a regression artifact and is not retuned.

Scenarios: clean, 0.1%/1% white family noise, 1% colored family noise, 1%
quantization step, CT on S IA, CT on all six currents, noisy six-current CT,
current/voltage ADC clipping, current dropout/spike/third harmonic, harmonic and
fundamental alias controls, S current gain 1.2, S voltage gain 1.2, R IA polarity
reversal, short fault window, DAT timing gap, R declared rate +0.5%, 1 Hz/s chirp,
and metadata-only R clock skew +1418 s. All 23 scenarios cross every fault/profile
in each split: 552 paired incidents and 1104 main/stage workflow outcomes.
Noise RMS references the stronger-terminal maximum ideal phase RMS per I/V family
over the capture, with deterministic matched perturbations. Quantization noise is
not assumed white. Aliasing controls are analytic sampled-sinusoid identities,
not a model of a manufacturer's anti-alias filter. Clearing has a .06 s tail.

## Research screen and truth
Apply the frozen scalar math to every current in secondary A. For voltage shape,
apply the same dimensionally homogeneous RMS/harmonic/peak budgets to secondary
V, with the analogous 1e-9 V numerical fundamental floor; this is exploratory VT
shape evidence, not calibrated VT quality. Publish explicit units. Four-cycle
support, 16 samples/cycle, residual 2%, harmonic 3%, peak residual 8% and relative
fundamental prominence 1e-5 are unchanged. All six channel screens must pass.
Before screen pass, require complete finite waveforms, valid ratios, unblocked
single-rate finite uniform acquisition, adequate guarded fault-window support,
and no ADC clipping. Always return authorizes_location=false. Never clear legacy
saturation, clipping, negative-sequence, clock or model gates. Oracle-known windows
are explicitly research support, not automatically detected field windows.

Independent complete-cycle quadrature compares ideal, CT-only and actual parsed
waveforms on corresponding sample-index supports, without replacing DSP phasors.
Report maximum per-phase complex current/voltage error with a 1% family/1e-6
secondary-unit denominator floor, and negative-sequence current error over
max(abs(reference I2), .01*abs(reference I1), 1e-6 secondary A). Error >5% is a
study challenge threshold, not a protection standard or confidence calibration.
Record known true frequency, sample rate and window beside DSP estimates and
acquisition provenance. Current known truth never enters the candidate screen.

## Evidence and decision
Retain every planned paired incident and both workflow outcomes on exceptions,
with typed failure and JSON-safe diagnostics. Scientific unsafe passes remain
successful numerical execution; CLI exit 2 denotes numerical failures. Exclusive
output publication, finite JSON, immutable historical artifacts, normalized
UTF-8/LF source hashes and complete split/profile/fault/scenario strata required.
Count both waveform-quality passes with harmful measurement errors and actual
located errors >1 km, including balanced controls. A safe-adoption gate requires
nonempty harmful validation coverage, no numerical failure, no harmful quality
passes, and no wrong located result or balanced location. A passing finite grid
would still not establish universal safety; any failure keeps the candidate
offline. Do not tune on validation. Full suites run serially (fixed HTTP ports).

No new field data, manufacturer CT/VT acceptance, full EMT/hysteresis, operational
model enablement, E4 clock promotion, confidence calibration or standards claim.
