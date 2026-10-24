# Noisy DSP and DAT timestamp recovery

User authorized autonomous continuation, integration and publication without new
field data. Use existing Python/NumPy/pytest and one inline implementation with
one fresh whole-branch reviewer. No further design questions are needed.

## Approach and scope

Generate noisy primary A/V waveform samples from the independent phase nodal
oracle, serialize real ASCII COMTRADE pairs, parse them, and run unchanged actual
DSP plus main and source-bound reviewed-stage section location. This exercises
more of the real path than further phasor noise injection. An EMT simulator or
automatic cross-terminal clock correction would be a different project.

Validate recovery of local uniform sample time from rounded/jittered DAT stamps,
not absolute clock synchronization. Preserve CFG clock quality, source hashes,
start/trigger dates and recovery provenance. Declared single-rate CFG remains
authoritative even when DAT timestamp fields are zero. Missing/repeated/reset/
nonfinite/gapped DAT times with no declared rate must never silently become a
trusted uniform acquisition. Nonconsecutive sample numbers must remain visible.
Only fix production behavior after a failing regression establishes the defect.

Recovery policy (executor choice): finite strictly increasing timestamps, at least
three observations, positive finite centered least-squares slope, maximum local
interval and trend residual deviations <=10% of fitted sample period. This is a
bounded software policy, not a COMTRADE standard tolerance or UTC accuracy claim.
Invalid input remains inspectable on a finite fallback grid with blocking flags,
explicit invalid provenance and no authorized location. Do not guess a valid rate.

## Experiment

180 incidents: three source profiles (baseline, weak_R_100, voltage_unbalance),
four connections (AG, BC, ABG, ABC balanced control), three waveform noise levels
(0, .1%, 1%), five timestamp modes (declared, rounded, bounded_jitter, clock_skew,
gap), seed854. Each incident produces both main and reviewed-stage outcomes.
Sources/sections/fault resistance/chainage match the previous source experiment's
first geometry, 75km, R4, native2400/1200Hz, remote1.1rad. White noise sigma uses
the stronger terminal's phase RMS maximum per V/I family over the ideal capture;
noise therefore does not disappear at the weak terminal or in a balanced sequence.
No post-DSP phasor/quality substitution, error-based filtering or truth root pick.
Rounded/jitter DAT uses nrates0/timemult1; jitter<=5us. Clock_skew shifts both R
CFG dates by1418s with identical local samples; it must not authorize E4 or alter
corresponding results. Gap adds .01s to the second half of R DAT stamps (nrates0).

Report all planned outcomes, exceptions/failures, refusal reasons, balanced controls,
noise/source/fault/time strata, located conditional errors and witnesses, frequencies,
clock metadata and recovery facts. Every failure retains its denominators and fails
the experiment explicitly. Use strict JSON and exclusive publication after compute.
Historical artifacts stay immutable; new hashes bind the changed parser and DSP path.

No model/quality/review gates relaxed, operational registry enabled, fields fabricated,
Dash/workbook/app database/preview changed. No EMT/CT-CVT, timestamp drift estimator,
automatic event pairing, calibrated confidence, exhaustive or field/TB854 claims.
