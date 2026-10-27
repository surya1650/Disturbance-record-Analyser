# Independent source-time analysis, without clock synchronisation

User explicitly requests autonomous implementation, no questions or integration
approval. Latest clarification: single ends must analyse independently; unsynchronised
ends need local references/corroboration, not a fabricated common clock. PROJECT_CONTEXT
2.3 already mandates that GPS is not a dependency. Do not change original captures,
application DB/revisions, Dash/workbook, preview processes8091/8113 or existing gates.

## Approaches and choice
Resampling would require an unsupported bandwidth/interpolation-error assumption.
Changing the existing uniform grid gate would feed invalid assumptions downstream.
Choose direct time-coordinate weighted regression, independent per record, in a new
diagnostic pipeline. It is useful without line constants, physical ratios or clocks;
it cannot authenticate those facts or grant operational location/clock authority.
Do not call this the completed production protection-analysis chain.

## Source observations
Add strict, read-only source_observations.py: load CFG/DAT bytes, bind SHA256, keep
original channel IDs and explicit engineering scaling only where all required fields
are valid. Never route new ASCII input through the legacy missing-value-to-zero path.
Missing/malformed values remain missing and affected analysis refuses; structural
row/count/truncation defects retain sample inspection but withhold timed fitting.
Support ASCII and declared BINARY/BINARY32/FLOAT32 integral payloads; CFF and
unsupported structures return a visible unsupported result, never claimed universal
recovery. Limits64MB payload,200000samples,64analog/64digital channels.
For nrates=0 use reviewed source_time_axis with explicit timemult. A valid single
declared CFG rate may define a uniform source axis; unsupported multi-rate metadata
gets sample-only inspection in this milestone. Preserve original decoder/gates.
Unknown/invalid a,b,P/S/ratios/units use labelled raw counts, never invented scaling.
Nonzero/unknown skew prevents phase/sequence interpretation; no cross-channel or
cross-record physical phase claim is made by this diagnostic path at all.

## Direct numerical pipeline
New pure dsp/nonuniform.py fits actual elapsed coordinates: joint harmonics1,2,3,
constant and a linear trend; trapezoidal time weights and centred/scaled basis.
At least24 observations, span1e-5..1s, frequency20..100Hz; max gap <=1/(12f),
full-rank design condition <=1e4. Reject masks, complex/coercive/nonfinite/extreme
values; finite JSON, no silent nominal-frequency fallback. Frequency search uses
explicit nominal40..70Hz,41 points over[.9nominal,1.1nominal] and bounded refinement.
Reject boundary minima, negligible fundamental or separated comparable minima.
These search bounds are declared analytical domain, not recorder provenance.
Return RMS coefficients referenced to each support centre, raw RMS, residual and
fit diagnostics. RMS is of the exported values, not calibrated primary current.
Model consistency requires relative residual<=.03 and fundamental amplitude greater
than1e-6 of raw RMS. It is not an alias/CT/calibration certificate.

New dsp/source_analysis.py uses4nominal-cycle physical-time windows with2cycle hop,
maximum512windows and4096samples/window; retain planned/evaluated/remaining counts.
Frequency is estimated on each support from explicit voltage channels, no fixed
fs, mimic decay/XR, assumed VT type, filtering or interpolation. Half-support
fundamental disagreement>.10 withholds that channel's model result. Missing timing
or frequency leaves whole-record sample statistics/digital sample states available.
Do not guess fault inception, CT health, fault type, breaker operations or location.
Always deny location, clock alignment, physical timing and production DSP authority.

## Independent records and references
New source_compare.py builds one incident-oriented view. Each record retains its
own elapsed coordinate and quality. Optional explicit per-record digital rising
edge anchors shift display coordinates only; unknown/initially active points do
not invent an edge. No cross-record time subtraction/phase rotation or E4 grant.
Identical content hashes are duplicates, never independent corroboration.
The displayed records are caller-grouped, not authenticated as the same incident.
Existing unsynchronised E5 remains available in its validated domain; this new
measurement path does not bypass its model, quality, pairing or observability gates.

## Evidence, output and delivery
CLI accepts one or multiple CFG/DAT pairs and optional digital reference label,
produces exclusive finite JSON and escaped standalone HTML. Read-only report can
be served separately on loopback without restarting previews or writing app DB.
Expose per-record statuses, raw/declared units, all window denominators and model
refusals; no invented usable-primary assignment. No external JS/network resources.

Freeze144 analytic cases BEFORE outcomes: seeds190081/190111,4/6nominal cycles,
uniform/piecewise/smooth source schedules,47.3/50.2/53.1Hz, clean/harmonic+linearDC/
noise/amplitude-step cohorts. Clean/harmonic tolerance1e-3Hz,1e-3relative RMS,
.02degrees local phase; noise .1Hz/.02relative RMS/1degree with fixed.005RMS noise;
step must refuse stationary model. Independent analytic signals, not production
builders, provide truth. Add uniform alias/coherent gain controls demonstrating
that passing model diagnostics cannot grant physical authority. Retain all failures.
Include all source dependencies and Git freezes; no historical manifest edits or
holdout tuning. One fresh whole-branch review, one TDD Important-fix pass, full
serial worktree/primary verification, commit/push, QA preservation/native archival.
