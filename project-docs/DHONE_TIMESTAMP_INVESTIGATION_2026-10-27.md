# Dhone timestamp investigation —2026-10-27

**Variable DAT intervals can be legitimate recorder behavior. Dhone is consistent
with that explanation, but device identity and physical timing are unverified.**
The current uniform-DSP gate remains in force. A separately tested declared-source
inspection API preserves the supplied coordinates without fitting or resampling.

## Primary documentation
[SEL's manufacturer paper](https://selinc.com/api/download/119832/),
*Understanding the Limitations of Replaying Relay-Created COMTRADE Event Files*
(2017/2018), sectionsII/III.A, distinguishes timestamp-defined sampling when
nrates/samp are zero and hardware frequency tracking with changing sample
intervals. That makes a uniform-time assumption inappropriate for some exports.
[Schneider's firmware FAQ](https://www.se.com/au/en/faqs/FA239653/)
independently documents nrates=0 exports for variable-rate recordings.
Neither source identifies this Dhone recorder or authenticates its clock.

## Evidence and interpretation
Private inspection found contiguous sample numbers and increasing timestamps.
Changes occur in24/48-interval blocks. This is consistent with tracked sampling,
not proof of a particular manufacturer/model or continuous acquisition.
The existing recovery fits one uniform grid and blocks on its global residual;
individual-step deviation is much smaller. That result establishes unsupported
uniform recovery under a project policy, not proven corruption or a demonstrated
COMTRADE standards violation. No threshold was raised and no timestamp changed.

The upload also has no uniquely associated settings or reviewed line model.
Two differently labelled source folders contain identical CFG/DAT bytes, not
independent Main-1/Main-2 observations. No circuit, ratios, polarity, channel
wiring, missing remote terminal or clock provenance is inferred.

## Supported bounded path
New pure comtrade/source_time.py accepts explicit nrates=0 DAT counters,
sample numbers and timemult, then returns declared elapsed coordinates and
digital observed-high runs. Transition brackets use neighboring source sample
coordinates; observed-run spans and brackets are not relay operating times,
calibrated uncertainty or guarantees against unrecorded intervening transitions.
Digital input latency/filtering remains unknown. Initially/finally active points
keep unknown boundaries; gaps remain visible. Malformed/extreme inputs withhold.

All outputs explicitly deny DSP, location and alignment authorization. There is
no production caller, Record.t replacement, automatic resampling or app mutation.
The unchanged public parser still blocks Dhone and the assignment validator
still cannot select its blocked record as a primary. Real source replay remains
private, bound to the original application inventory hashes before/after.

## Independent numerical validation
Frozen protocol/code55f8e3a precedes108 outcomes. Two disjoint seeds, three sizes,
three multipliers, two origins and three schedules exercise constant, piecewise
and smooth integer-counter steps. Independent Fraction arithmetic supplies elapsed
and digital bracket expectations. All108 evaluated, zero failures; source-time
and bracket discrepancies below the frozen1e-12s arithmetic criterion. This
criterion tests arithmetic only and is not clock accuracy.
Evidence: validation/SOURCE_TIME_2026-10-27.json; eight source hashes including
full_record_signals.py preserve provenance.36new core tests plus3runner tests
and30existing timestamp tests pass (69focused). Existing slow-nonuniform,
gap/reset/missing-sample and clock-refusal tests remain unchanged.

Baseline1501pass/28missing-corpus skips/1existing warning282.88s. Final full
regression, fresh whole-branch review, any single Important-fix pass and primary
delivery remain required until explicitly recorded in the execution ledger.
This report does not claim production readiness or completed integration.

## Remaining normal-analysis work
Nonuniform DSP must handle actual sample coordinates throughout filtering,
frequency tracking, window selection, derivatives and quality screening. A new
Fourier fit by itself would not validate that chain. Resampling additionally
needs justified bandwidth/alias and interpolation-error treatment. Unknown
recorder/filter/channel/clock properties cannot be supplied by successful fits.
Until that independent validation exists, supported use is declared-source
inspection; fault classification, operation verdict and distance remain held.
