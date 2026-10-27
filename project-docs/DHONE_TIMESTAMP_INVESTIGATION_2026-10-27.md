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

The3624 samples have3623 intervals:832us for791 intervals,833us for24,
819us for24,817us for24,830us for48,833us for48, then832us for2664.
The uniform fit has period831.794533us and maximum global residual394.648650us;
the10% project allowance is83.179453us. Maximum individual-step deviation is
14.794533us. These are different measures; passing the latter would not make
the global grid valid. The exported Any Start point is high at samples739..778
and returns low at779. Its source-coordinate span is33.280ms, with neighboring
sample-coordinate bracket32.448..34.112ms. This is not calibrated physical
duration. The other31 recorded digital points remain zero in this capture;
their state cannot establish that no physical operation occurred.

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

One fresh whole-branch review reproduced all108 original rows and verified all
eight historical bindings. Its two Important findings were reproduced before
fixing: actual masked numeric observations now refuse instead of losing their
mask, and subnormal time conversions refuse instead of returning distorted
positive coordinates. Eight regression/control cases take the focused suite
to77passes; the five failing cases were observed RED before the fixes. There
are no deferred Minor findings. No repeat review is required by this workflow.

Reviewed code frozen atd0eb3aa; separate evidence
validation/SOURCE_TIME_2026-10-27_REVIEWED.json preserves all108 numerical rows
unchanged and binds all eight reviewed sources. The original freeze/manifest is
retained. This is an arithmetic inspection result, without production authority.

Baseline1501pass/28missing-corpus skips/1existing warning282.88s; original release
1540pass/28skips212.73s. After the single review-fix pass,77focused and1548full
tests pass, with28missing-corpus skips/1existing upstream warning254.60s.
Architecture and changed-file Ruff pass. Primary integration/regression results
are recorded separately on delivery. This report does not claim field readiness.

## Remaining normal-analysis work
Nonuniform DSP must handle actual sample coordinates throughout filtering,
frequency tracking, window selection, derivatives and quality screening. A new
Fourier fit by itself would not validate that chain. Resampling additionally
needs justified bandwidth/alias and interpolation-error treatment. Unknown
recorder/filter/channel/clock properties cannot be supplied by successful fits.
Until that independent validation exists, supported use is declared-source
inspection; fault classification, operation verdict and distance remain held.
