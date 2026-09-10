# Initial DR analysis workflow and implementation priorities

Recorded 2026-09-08 from the user's revised requirements. **Requirements and
implementation plan, with delivery status below.** This supersedes the
previous suggestion to make section-aware fault-location modelling the next
main workstream. Preserve the local application and existing uncommitted work.

The initial product must explain the fault and protection operation from one
terminal's DRs, or both terminals when available. Settings-system access and
SAP/GIS integration are later enrichments, not prerequisites for record-based
analysis. Fault distance remains conditional on valid electrical parameters
and the limits documented in [TB854_VALIDATION_MATRIX.md](TB854_VALIDATION_MATRIX.md).

## Incident workflow

1. Upload one or more DRs. Parse, retain originals, identify channels, units,
   sample rates, primary/secondary declarations and quality issues. Existing
   parser/conformance components are the starting point, not a rebuild.
2. Establish line/circuit, terminal and relay identity. Main-1 and Main-2 are
   separate protection systems at the same terminal. They are not the two ends
   of the line and not the application's primary/corroborating selection roles.
   Keep unknown/ambiguous identity explicit and allow reviewed assignment.
3. Identify fault inception, phase involvement and eligible analysis intervals
   independently for every usable record. Retain evolving stages and reclose
   shots as sub-events of one incident; do not average incompatible stages.
4. Establish what each relay recorded: pickup, trip command, indicated zone,
   teleprotection, breaker-position changes, current interruption and reclose.
   Present the evidence for whether operation occurred at each available end.
5. Compare Main-1/Main-2 at each end before comparing the ends. Distinguish
   intentional scheme differences from inconsistent measurements, missing
   evidence, configuration differences and uncertain identity. Disagreement
   alone does not identify which relay is wrong.
6. Associate corresponding stages across ends using identity and electrical
   evidence. Use each record's fault trigger as its **0 ms** display reference,
   as clarified by the user. Keep waveform-detected fault inception separately.
   With usable clocks, retain their quality/uncertainty. Without
   synchronization, retain local time, trigger-relative and inception-relative time; attempt
   waveform/event correlation only where it is identifiable. Show the recovered
   offset and method. If correlation is ambiguous, retain separate timelines.
7. Present per-phase voltage/current measurements and an SLD-style event
   sequence linked to waveforms, digital points and the R-X trajectory.
8. Audit recording completeness and evaluate the applicable protection
   philosophy to the extent the evidence permits. Unknown settings, incomplete
   channels or missing remote records make affected checks not evaluable.
9. Issue one incident report with all relay evidence and limitations. A later
   remote record, reviewed channel mapping or settings delivery creates a new
   report revision, preserving the previous inputs and conclusions.

## Evidence semantics

For each terminal show record availability separately from operation evidence.
For each relay and signal distinguish:

- assertion observed in the recorded interval;
- mapped signal with no assertion observed in that interval;
- signal not recorded/unmapped or mapping ambiguous;
- record missing, blocked or insufficient for the question;
- signal already active at capture start, with onset time unknown.

A missing remote DR does not mean the remote relay failed to operate. A trip
command does not by itself prove breaker opening; current interruption and
breaker auxiliary status are distinct evidence. A nonasserted mapped signal in
a short record cannot establish that no later operation occurred. Fault evidence
in analog channels must remain visible when digital indication is absent.

Relay operate time, breaker time and total clearing time require different
reference events. Do not fabricate milliseconds when inception, trip or opening
is uncertain. Do not infer carrier transit delay from onset-aligned free-running
clocks. E5's recovered phasor angle is modulo one cycle and is not a unique
absolute timestamp correction. E4 stays clock-gated; E5 remains unsynchronized.

The user clarified **"OMS" as "0 millisecond, time of fault trigger"**.
Each record's trigger is its 0 ms reference, with negative pre-trigger and
positive post-trigger times. Show waveform-detected fault inception as its own
marker; a recorder trigger is not automatically the physical fault inception.
Retain original timestamps and expose a separately labelled common aligned
timeline when cross-record evidence supports one. Setting both triggers to
zero alone does not establish physical simultaneity or synchronize clocks.
Missing/invalid trigger metadata must be shown as unavailable; any explicit
manual or detected-onset reference is labelled with its provenance. Relay
operating duration remains measured from the stated physical/evidence event,
not silently substituted with time since recording trigger.

## Current implementation versus required work

Paths below are relative to `src/dranalyser/`. The inventory records the initial
code inspection; the delivery update below supersedes its all-relay evidence,
identity and measurement gaps. Other extensions remain pending.

| Requirement | Existing implementation/evidence | Required extension |
|---|---|---|
| Parser and quality | `comtrade/parser.py`, `conformance.py`; CFG/DAT/CFF, supported encodings, units/scaling and conformance; real-corpus tests | Browser channel review with original labels, canonical mapping, unit/ratio provenance and visible ambiguities; retain blocks and explicit corrections |
| Single or both ends | `workbench/incident.py`, application intake/revisions support one or two selected terminal records without a line definition | Make operation evidence, not distance, the initial report emphasis; include an explicit missing-end state |
| Fault identification | `dsp/pipeline.py` and `detect.py` classify fault/inception and choose windows | Expose per-relay fault calls, quality and stage boundaries; validate evolving faults and reclose stages |
| Main-1/Main-2 identity | Assignment records an end and primary/corroborating role; asset resolver proposes identities | Record protection-system identity independently of analytical role; preserve unknown IDs; do not label the first uploaded record Main-1 |
| Same-end comparison | `workbench/corroborate.py` compares fault type, prefault/fault current and negative-sequence source impedance; results persisted by worker | Display comparisons in the current app and downloadable report; expand to per-phase V/I, operation, zones and timing; avoid automatically selecting a correct relay from disagreement |
| Both-end operation | `rules/features.py` computes operation/clearing features for selected records | Structured per-record evidence states and end-level reconciliation that retain Main-1/Main-2 contradictions; report missing evidence explicitly |
| Trigger at 0 ms | Parser retains record/trigger timestamps; current report axes use detected inception | Provide trigger-zero axes for each record and separate detected-inception markers; identify the reference and offset on every common/aligned view |
| Cross-end correlation | `faultloc/ensemble.py` aligns analysis windows by inception; report plots use inception-relative axes | Explicit correlation result, ambiguity/uncertainty, same-stage checks and local-time fallback; inception alignment is not validated automatic event pairing |
| RMS and peak measurements | Fundamental phasors exist; same-end comparison uses a windowed fundamental-current percentile | Per-phase waveform RMS, fundamental RMS and measured peak for defined windows; voltage/current units and source channels; timestamp/sample provenance |
| Measurement defect to repair | `rules/features.py` takes a whole-record maximum current and derives `i_fault_ka` by dividing by sqrt(2); report shows it as fault current | Replace/report the quantity honestly. Peak/sqrt(2) is a sinusoidal equivalent, not general waveform RMS; define fault windows and avoid pre/post-event maxima contaminating the fault summary |
| Sequence-of-events view | `report/render.py` creates static digital intervals and tables for selected terminal records | SLD-style terminal/CB/relay states linked to a time cursor and a from/to event table covering every relay; preserve unknown and initially-active states |
| DR standardization | `standards/audit.py` checks sampling, capture length, analog channels and grouped digital evidence; CLI integration exists | Per-record browser/report checklist showing required point, original channel, mapping, availability, result and source locator. Presence in a DR is not proof of the full relay configuration |
| Protection philosophy | Rules and separate settings/record audit paths exist, with not-evaluable handling | Surface the applicable source/version and required settings for each judgment; separate measured behavior, recording completeness and settings conformity |
| Online channel selection/navigation | App supports upload, assignment, history and embedded report | Interactive analog/digital channel selection, zoom/pan, cursors, window selection and traceable mapping overrides; distinguish selecting a visible trace from changing its analytical identity |
| R-X plot | Static report renders one selected end's trajectory and settings polygons; current trajectory path requires settings | Select terminal/relay/loop/window; synchronized cursors; verified unit basis and parameter source. Show phase-loop V/I where valid without zone settings; ground compensation and zone overlays require their own inputs |
| SAP/settings and GIS | Native settings importer and local asset registry exist; no SAP/API/GIS association contract implemented | Later adapters and reviewed identity joins; do not invent service endpoints or treat geometry as electrical line constants |

## First implementation milestone: all-relay evidence

**Delivered locally, 2026-09-08:** API, browser and HTML report now retain each
analysed relay's fault call, quality flags, explicit protection-system identity,
windowed phase measurements and digital observations. Unavailable records and
missing terminals remain visible. Main-1/Main-2/other/unknown is reviewed
independently of terminal S/R and analytical primary/corroborating role.

Each record has its own trigger-zero reference, separate detected inception,
raw-point assertion intervals and a local inception-to-first-trip duration when
identifiable. Invalid trigger metadata produces unavailable trigger-relative
times. Existing waveform plots still use inception-relative axes; there is no
new common aligned timeline. Initially active points have unknown onset;
contradictory raw mappings require review. A trip observation does not establish
breaker opening or a correct protection scheme. Existing same-end comparisons
are displayed, while the rule verdict still uses selected terminal records.

Per-phase sample RMS includes DC/harmonics, fundamental RMS uses the median
eligible DFT magnitude, and peak means measured absolute peak in the selected
fault window. Source labels, primary A/V units, declared ratios and window/sample
provenance accompany the values. The old peak/sqrt(2) fault-current summary and
its overcurrent ratio now use measured sample RMS. This is not a model of every
relay's pickup filter and does not reconstruct saturated currents. Historical
reports are preserved; review/rerun produces a new revision using these fields.

**Bounded validation:** 384 repository tests pass, including independent
waveform/digital fixtures and application revision checks; architecture checks
and the 10,000-case Stage-A gate pass. Desktop/mobile browser checks cover four
relays, identity review and report display. These checks validate the stated
software behavior within their fixtures, not TB 854 compliance, field accuracy,
all fault stages or automatic cross-end association.

**Still pending within the wider workflow:** evolving-stage/reclose association,
reviewed analog/digital mapping overrides, operation reconciliation across
relays, verified clock-offset alignment, complete configuration/philosophy
adjudication, SLD/channel/R-X interaction and SAP/GIS adapters. Later bounded
comparison/checklist deliveries are recorded below. The acceptance scenarios
remain the target; the first delivery does not satisfy all of them.

Build a per-record evidence result behind the current application, retaining
each relay's identity, quality, channels, measurement windows and operation
observations. Extend the report/API to consume it. This is the common foundation
for Main-1/Main-2 assessment, both-end operation, audit presentation and the
interactive navigator; do not build separate numerical paths for each view.

Acceptance scenarios:

1. One-end, one-relay input produces fault, measurements and local operation
   evidence; the remote end remains unknown. No settings/geometry dependency.
2. One-end Main-1/Main-2 inputs both remain visible, including disagreement;
   changing the selected analytical primary does not erase either operation.
3. Four-relay, two-end input separates same-end and cross-end comparisons;
   unavailable or blocked records and their effects remain visible.
4. A mapped trip that never asserts differs from an absent trip point, an
   initially-high trip and a trip outside an incomplete recording interval.
5. Pure sine, DC-offset, distorted, clipped and truncated waveform fixtures
   verify per-phase RMS and peak definitions, windows and units. Include a
   counterexample where peak/sqrt(2) differs from measured RMS.
6. Unsynchronized records retain local operation times. Wrong-stage or
   ambiguous matches cannot create a falsely precise cross-end event order.
   Test different trigger delays for the same fault: each local trigger remains
   0 ms, detected inception may lie before/after it, and only justified alignment
   places those events on a common time axis. Missing trigger time is explicit.
7. Channel mapping changes are explicit, versioned and reversible. Original
   recorded values and labels remain available; no silent ratio/polarity repair.

Before implementing these semantics, inspect and reuse existing tests rather
than assuming current feature booleans or report labels already implement them.
Carry the required architecture/full-suite/Stage-A gates for production changes.

## Following milestones

**Milestone 2 bounded delivery, 2026-09-09:** all-pair digital observation and
local-duration comparisons, explicit identity review, advisory onset-shape
correlation and conservative stage/quality refusal are now implemented in the
API, browser and HTML report. A review warning accompanies conflicting relay
observations. See [OPERATION_ASSOCIATION_VALIDATION.md](OPERATION_ASSOCIATION_VALIDATION.md)
for exact criteria and 411-test evidence. Candidate shapes are not confirmed
event/stage matches; global alignment, verified clocks and complete operation
adjudication remain pending. The table below retains the broader completion targets.

**Milestone 3 bounded delivery, 2026-09-09:** per-relay WG-3 profiles, all base-table
requirements, separate RIO association/provenance and philosophy evidence screens
are integrated into API/browser/revisioned HTML. Missing or unsupported semantics,
event-time validity, complete trigger configuration and full scheme coordination
remain not evaluable. See
[RECORDING_PHILOSOPHY_VALIDATION.md](RECORDING_PHILOSOPHY_VALIDATION.md) for 437-test
and browser evidence. Next is milestone 4; no settings/SAP/GIS integration is needed
to begin logical SLD and local event/channel navigation.

| Order | Deliverable | Completion evidence |
|---|---|---|
| 2 | Main-1/Main-2 reconciliation and cross-end event association | Unequal rates, large clock offsets, intentionally wrong pairs, changing fault stages and missing operation points; ambiguous cases remain inconclusive |
| 3 | Integrated DR completeness and protection-philosophy views | Applicable source locators, per-point channel evidence, versioned settings when available, and not-evaluable results when prerequisites are missing |
| 4 | Channel navigator, linked R-X view and SLD-style event sequence | Every view uses the same records/windows/events; cursors and selected interval agree; initial/terminal/unknown states represented; browser verification on single/two-end and four-relay incidents |
| 5 | Settings API/document ingestion and SAP/GIS integration | Reviewed ID mapping, provenance and effective dates, ambiguous/unmapped join handling and repeatable report revisions |

**Milestone 4 bounded delivery, 2026-09-09:** mapped waveform channel selection,
local interval/cursor linkage, phase-phase R-X, digital interval navigation,
logical SLD and a standalone current-view export are implemented. Single-end,
two-end and four-relay browser scenarios pass. See
[NAVIGATION_VALIDATION.md](NAVIGATION_VALIDATION.md) for 452-test evidence and
display limits. Ground-loop/zone overlays, full-resolution zoom, reviewed mapping
overrides and verified physical breaker interpretation remain pending. Common
clock/stage alignment is deliberately absent until supported by evidence.

**Milestone 4 extension, 2026-09-09:** reviewed analog/digital mappings now bind
to exact record hashes and flow through conformance, DSP timing, rules and views.
Native sample inspection loads exact selected waveform samples with sample stepping
and separate interval RMS/peak metrics (20,000-sample request limit). Revisions,
original labels/values and pre-review flags remain preserved. See
[CHANNEL_MAPPING_VALIDATION.md](CHANNEL_MAPPING_VALIDATION.md) for 480-test and
browser evidence. Ground-loop/zone prerequisites and common-stage/clock contracts
remain unvalidated; raw-unmapped analog navigation and indexed retrieval remain pending.

**Milestone 4 ground/zone extension, completed 2026-09-10:** per-record source-
bound input review, native-derived AG/BG/CG and separately selected exported
phase/earth outlines are implemented. Missing/stale/ambiguous inputs are withheld;
reviewer declarations do not verify field settings or protection operation.
See [RX_INPUT_VALIDATION.md](RX_INPUT_VALIDATION.md) for the 509-test and browser
evidence. The next work remains fault-stage association and clock-quality
contracts; the navigator still uses independent local timelines.

**Stage/clock contract extension, completed 2026-09-10:** advisory initial,
evolving and reclose current-pattern intervals retain raw signal provenance,
original bounds and uncertain/open edges. Per-record source-bound stage-group
reviews can associate corresponding intervals under explicit reviewer declarations;
repeated patterns otherwise remain ambiguous. Clock metadata reports code meanings
and declared error bounds separately from verified accuracy. All clocks remain
unaligned, E4 receives no new authorization and E5's unsynchronized path is unchanged.
See [STAGE_CLOCK_VALIDATION.md](STAGE_CLOCK_VALIDATION.md) for 573-test, Stage-A and
browser evidence. Next is independent evolving/reclose network validation before
stage-aware estimator/window gating; full clock/physical-stage validation is pending.

The SLD initially represents logical connectivity (terminal bus, breaker, line,
remote breaker/bus, relay indications). It does not require surveyed geometry
and must not invent breaker/disconnector positions absent from the evidence.
Events carry start/end time or an explicit open/unknown boundary, origin relay,
raw digital point or analog inference, trigger-zero/local/aligned time basis and uncertainty.

## Later identity and data integration

Keep internal incident, line/circuit, terminal, bay and relay identities separate.
The intended association is:

```text
Settings API/document -> relay + terminal SAP bay ID + effective settings version
SAP bay ID at S / SAP bay ID at R -> reviewed internal line/circuit association
GIS ID -> line/section GeoJSON -> reviewed line/circuit association via SAP mapping
```

Do not assume that one SAP bay ID identifies both terminals or that every GIS
feature is one complete electrical circuit. Preserve externally supplied IDs,
source/version, validity dates, mapping confidence and operator decisions.
GeoJSON coordinates/route length do not provide Z1/Z0, coupling or verified
electrical section parameters. Exact API, document format, SAP/GIS join
cardinalities and coordinate reference details will be specified with those
integrations; none blocks the initial record-based workflow.

The TB validation findings remain active limitations, especially external
distance/tower presentation and ambiguous E5 roots. Address them when publishing
distance; they do not replace the new operational-analysis priority.

## Change record

The initial requirements update inspected the current parser/pipeline, all-relay corroboration,
operation features, standards audits, report rendering and application display.
It changed documentation and work ordering only. The subsequent implementation
is recorded in the first-milestone delivery update and newest STATUS_LEDGER entry.
