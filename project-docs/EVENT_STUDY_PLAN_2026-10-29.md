# Incident report and shared cursor measurement

User goal: a simple incident report comparing sending and receiving end voltages
and currents, pre-fault/fault changes, method-labelled distance and relay-reported
distance, plus recorded digital timing evidence. Waveforms retain all analogs,
changed digitals below, and side values/vectors following one locked or live cursor.

Implementation separates three measurements:

- Trailing one-nominal-cycle sample RMS includes DC/harmonics and restores a dense
  measured trend independently of the four-cycle operational fit.
- A pure harmonic-plus-DC least-squares cursor measurement uses actual timestamps
  over that same complete trailing cycle. It is DFT-equivalent for a uniformly
  sampled integral cycle. It reports support, residual and unavailable reasons.
- Existing four-cycle fitter and reviewed E1–E5 operational location remain
  unchanged. One-cycle display measurements never authorize location.

All plots share a source index. Click/numeric/keyboard actions lock the readouts;
an explicit follow-hover control resumes live movement. Requests are bounded,
source/revision/hash validated, cancelled on replacement, and applied atomically.
Missing observations, incomplete cycles and gaps stay unavailable.

The incident report requires explicit S/R records/substation names and region
selection. Successive captures from one relay are not opposite ends. Each region
uses complete contained RMS supports, retains unit/scaling warnings, and names
the existing eligible location method. Relay distance is optional, evidence-bound
and explicitly relay-reported. Recorded trip is not physical CB opening; AR
commands alone do not establish successful restoration. Relative display alignment
does not establish synchronized clocks.

Validation: analytic and synthetic-oracle Fourier checks, sample-RMS edge cases,
revision/source-bound API and persistence tests, frontend locking/staleness tests,
browser checks of real local DR2 and synthetic two-ended data, architecture direct
check, full pytest, and unchanged Stage-A 10,000-case grading. Private records and
browser artifacts remain under ignored out/qa. Push the authorized review branch
after checks; do not merge main or publish environment configuration.
