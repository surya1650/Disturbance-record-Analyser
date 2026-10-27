# Dhone timestamp investigation and supported source-time inspection

Autonomous inline under standing authorization. Preserve original recordings,
application DB/revisions, preview processes, Dash and every existing safety gate.

## Finding and scope
SEL's manufacturer paper https://selinc.com/api/download/119832/ (Understanding
the Limitations of Replaying Relay-Created COMTRADE Event Files,2017/2018,
sectionII timing and sectionIII.A) explains timestamp-defined nrates=0 data and
hardware frequency tracking that changes sample intervals. Schneider's primary
FAQ https://www.se.com/au/en/faqs/FA239653/ documents variable-rate nrates=0
exports. These establish legitimate behavior in general, not Dhone device identity.
No manufacturer, model, firmware or physical clock accuracy is established here.
No third-party COMTRADE parser may be installed or imported.

Dhone shows monotonically increasing DAT counters, consecutive sample numbers,
and period runs832us(791 intervals),833(24),819(24),817(24),830(48),833(48),
832(2664). The24/48 changes are consistent with tracked recording but not proof.
Current recovery replaces nrates=0 source timestamps with a uniform fitted grid;
its394.65us global residual exceeds the10%-period policy even though maximum
individual step deviation is14.79us. That proves unsupported uniform recovery,
not corrupt recording. An existing test intentionally blocks slow nonuniformity.

## Deliverable
Add pure comtrade/source_time.py with source_time_axis(numbers,stamps,*,nrates,
timemult) and digital_source_intervals(numbers,stamps,states,*,nrates,timemult).
These ONLY inspect explicitly declared DAT source time for nrates=0; they do not
alter Record.t, resample, run DSP, select primary, classify faults or locate.
Always authorizes_dsp=false, authorizes_location=false, alignment_eligible=false,
recorder_accuracy_verified=false, basis clearly declared-source only.

Require3..200000 one-dimensional numeric finite samples, equal lengths,
nonboolean integer consecutive nonnegative sample numbers <=2**53-1, strictly
increasing nonnegative timestamps <=2**53-1, finite positive explicit timemult and exactly
integer nrates=0 (not bool). Reject coercive strings/complex/bool/object/ragged
inputs, overflow/underflow/collapsed time coordinates. Invalid input returns finite
JSON withheld, never exceptions or silently invented data. Returns elapsed_s,
interval extrema and exact raw-period runs. Gaps remain visible; monotonicity
does not authenticate continuous acquisition. No imputed or calibrated error cap.

Digital states must be binary, finite and length matched. Each transition at k
has recorded source time t[k] and sample-bracketing[t[k-1],t[k]], conditional on
source correspondence. Initially active onset is unknown; final active ending
unknown. A closed observed-high interval gives point-span and sample-bracketing
duration range; none is a relay operating time or clock confidence interval.

Use TDD analytic irregular times and malformed/resource/extreme cases. Independent
disjoint synthetic axis/digital grids before outcomes: seeds103811/104729,
sizes[17,257,2049], scales[.1,1,10], origin[0,1e12], timing schedules constant,
piecewise and smooth =>108 cases; compare source edges/elapsed against direct
integer-counter arithmetic, preserve every failure. Full existing timestamp and
regression tests must stay green. Real source replay stays private, verifies
SHA256 matches existing inventory before/after; candidate should report declared
Any Start span33.280ms, bracket[32.448,34.112]ms, normal parser remains blocked.
Those expected times derive from source counters, not an assumed sample rate.

## Alternatives / next boundary
Do not raise the10% limit or overwrite timestamps/rates. Automatic uniform
resampling lacks a validated bandwidth/alias-error model. Nonuniform DSP needs
explicit support through filtering, frequency tracking, windows, derivatives and
quality tests; a new Fourier fit alone would not validate the full chain.
This milestone supports source-time inspection only and records that remaining
boundary. One fresh whole-branch review; one TDD Important-fix pass, no repeat
review. Preserve ledgers/QA before native archive. No field/clock/CT/VT claims.
