# PROJECT CONTEXT — Two-Ended Disturbance Record Analyser for Distance Protection

> **Status:** Architecture agreed, not yet built.
> **Owner:** Surya (rscvreddy@gmail.com)
> **Version:** 1.0 · 2026-09-06
> **Purpose of this file:** single self-contained brief for any engineer or AI agent
> picking up this project. It assumes **no prior conversation**. Read it end to end before
> proposing or writing code.

---

## 0. How to use this document

If you are an AI coding agent:

1. Read **§1 Mission**, **§2 Non-goals and hard constraints**, and **§14 Definition of done for the first PR** before anything else.
2. **§2 is binding.** Several plausible-looking approaches are explicitly ruled out there with reasons. Do not reintroduce them. If you believe one is wrong, say so explicitly and argue it — do not silently build it.
3. Everything in §5–§11 is a specification, not a suggestion. Where a number or formula is given, implement that number or formula.
4. Where this document says **[OPEN]**, the decision has not been made. Do not invent an answer and proceed; surface it.

---

## 1. Mission

Build a system that automatically analyses **disturbance records (DRs)** retrieved from
**distance protection relays at both terminals** of a transmission line, and for every line
fault produces:

- a **fault location** in km and in tower number, with a defensible confidence interval;
- a **protection performance verdict** (did the correct zone operate, in the correct time, did
  teleprotection work, did the breaker clear in spec, was auto-reclose correct);
- a **two-page report** issued within minutes of the event;
- a **feedback loop** that captures the patrol-confirmed actual fault location and uses it to
  improve line parameters and future estimates.

### 1.1 Physical context

- Utility transmission network. Assume 132 / 220 / 400 kV AC overhead lines, 50 Hz.
- Indian phase convention: **R, Y, B** (equivalent to A, B, C in IEEE literature).
- Each line has exactly **two terminals**, referred to throughout as **end S** (sending /
  reference end) and **end R** (remote end). `m` always means per-unit distance from **S**.
- Each terminal typically has Main-1 and Main-2 distance relays, so one fault commonly
  produces **4+ disturbance records**, plus more if auto-reclose operates.

### 1.2 The chain being built

```
Relay (SS-A) ──┐                                    ┌── Fault location
Relay (SS-A) ──┤                                    ├── Protection verdict
               ├─> SS edge collector ─> transport ─>├── 2-page PDF report
Relay (SS-B) ──┤   (COMTRADE + manifest)   (push)   ├── Interactive event view
Relay (SS-B) ──┘                                    └── Ground-truth capture
                                                            │
                                                            └─> line parameter estimation
                                                                & residual correction
```

### 1.3 Prior work

The originator has preliminary work in a local folder `E:\dr analyser` which has **not** been
reviewed and is **not** reflected in this document. Reconcile against it before writing new
code — it may already contain a COMTRADE parser, sample records, or a UI prototype.

---

## 2. Non-goals and hard constraints — READ BEFORE CODING

These are decisions already taken after review. Each is stated with its reason so you can
argue with it if you have new information. "I'd prefer X" is not new information.

### 2.1 DO NOT build per-relay machine-learning fault location

**Ruled out.** The proposal was to "train historical fault data of every relay" so that a
learned model corrects the distance estimate per relay.

The arithmetic that kills it:

| Quantity | Realistic value | Consequence |
|---|---|---|
| Line faults per line per year | 1–3 | < 30 events per line even over a decade |
| Fraction with patrol-confirmed location | 15–30 % | Labelled set per line is single digits |
| Fraction that are single-line-to-ground | ~80 % | Almost no labelled phase or 3-ph faults per line |
| Accuracy of the "true" location itself | ± 1 span (≈ 0.3 km) | Label noise ≈ the error being corrected |
| Free parameters in a per-relay NN | 10³ – 10⁶ | Memorisation, zero generalisation |

A per-relay fit on 5 points will look excellent on those 5 points, pass review, and then move
real answers in the wrong direction on the 6th fault — while carrying the authority of "the
model said so". **Build §9 instead.**

### 2.2 DO NOT implement traveling-wave fault location

**Ruled out on hardware grounds.** Distance relay DRs sample at 1–5 kHz (20–96 samples per
cycle). Traveling-wave location requires ≥ 1 MHz sampling and ≤ 1 µs alignment between ends.
This is a different device class, not a software problem. Do not add it to the backlog as
"phase 2"; it requires capital purchase of TW-capable recorders.

### 2.3 DO NOT make GPS / time synchronisation a dependency

The **primary** fault location method (E5, §7.2) is *unsynchronised* and requires no common
time reference. Synchronised two-ended (E4) is a bonus path used only when both records
report good clock quality. A project plan that blocks on substation time sync is wrong.

### 2.4 DO NOT emit one report per file

One line fault = **one incident**, with many records attached. Emitting four reports for one
fault destroys user trust in week one. The top-level domain object is `incident`, never
`record`.

### 2.5 DO NOT silently repair bad input

If a record fails a conformance check, tag it and carry the tag through to the report. Never
guess a CT ratio, never auto-correct a polarity without flagging it, never drop a record
without a visible record of the drop.

### 2.6 DO NOT let a learned correction overrule physics

Any residual-correction model (§9.2) is capped at **±2 % of line length**, and the raw physics
estimate is always printed alongside the corrected one.

### 2.7 Scope boundary is wider than "analysis"

The original scope started at "the extracted DRs arrive at the central system". That boundary
is wrong: wrong CT/VT ratios, reversed neutral CT polarity, free-text channel names, and
records that never arrive all originate upstream and will all be reported as *the analyser*
being wrong. The project **specifies** the collector and **owns** the conformance gate, even
if another team implements the collector.

---

## 3. Reference practice — what exists commercially

| Tool | Strength | Two-ended | Automation | Gap |
|---|---|---|---|---|
| Siemens SIGRA | Waveform / phasor / R-X views, per-record location | Manual two-record load | Analyst-driven | No unattended pipeline, no verdict, no fleet learning |
| SEL synchroWAVe Event (SEL-5601-2) | Event report analytics | Yes, within SEL ecosystem | Semi | Vendor-bound; weak on mixed fleets |
| Softstuf Wavewin | Robust COMTRADE handling, C37.114 double-ended | Yes | Semi | Data conditioning mostly manual; no protection-performance rules |
| ERLPhase / Qualitrol TESLA | DFR-grade recording and analysis | Partial | Semi | Recorder-centric, not relay-fleet-centric |
| Kalkitech SYNC / IED management | Vendor-agnostic automated DR retrieval at scale | No | Full (collection only) | Collects well, analyses barely |

**Conclusion:** collection is a solved commercial problem; automated engineering judgement is
not. If procurement permits, buy the collection layer and spend engineering effort on §7–§10.

### 3.1 Standards to conform to and cite

| Standard | Covers | Use |
|---|---|---|
| IEEE C37.111-2013 / IEC 60255-24 (COMTRADE) | Transient data exchange. 2013 adds single-file `.CFF`, `float32`/`binary32`, `time_code`, `local_code`, `tmq_code`, `leapsec`, ns timestamps | Mandate 2013 CFF on new deployments; normalise 1999 files. `tmq_code` gates E4. |
| IEEE C37.232-2011 (COMNAME) | File naming for time-sequence data | Canonical archive filenames; deterministic retrieval |
| IEEE C37.239 (COMFEDE) | Event data exchange (XML) | Optional export to RLDC / neighbouring utility |
| IEEE C37.114-2014 | Fault location on AC lines | Reference for every algorithm in §7 |
| IEC 61850 (MMS file services), IEC 60870-5-103 | DR retrieval from modern / legacy IEDs | Retrieval paths A and B (§4) |
| IEC 62443, CEA cyber security regulations | OT/IT segregation | Governs transport design (§4.2) |

---

## 4. Collection and transport (specified here, possibly implemented by others)

### 4.1 Retrieval paths, in order of preference

| Path | Applies to | Mechanism | Notes |
|---|---|---|---|
| **A · IEC 61850 file services** | Ed.1/Ed.2 IEDs (SIPROTEC 5, REL670, MiCOM P44x, SEL-400 series) | MMS `GetFile` / directory browsing; COMTRADE is native | Preferred. Vendor-neutral. Ed.1 directory conventions differ per vendor — one adapter per vendor. |
| **B · IEC 60870-5-103** | Legacy numerical relays (SIPROTEC 4, older MiCOM, ABB REL 5xx) | 103 disturbance-data upload ASDUs, reassembled to COMTRADE | Slow (minutes per record on serial) but near-universal on 1990s–2000s relays |
| **C · FTP / SFTP** | Relays exposing a filesystem | Scheduled pull of new files | Simplest. Poll faster than the relay's record buffer depth or records are lost. |
| **D · Vendor tool automation** | Anything else, proprietary formats | Headless invocation of the vendor's own tool | Last resort. Fragile, licence-bound. One adapter per relay family. |

### 4.2 Transport rules

- **Push, never pull, across the security boundary.** The central system must not be able to
  initiate a connection into the substation LAN.
- **Outbox / store-and-forward at the edge.** Delete locally only after an acknowledged,
  hash-verified receipt. Spool sized for ≥ 30 days of worst-case event rate.
- **Manifest first, payload second.** Small JSON manifest (line, terminal, relay, trigger time,
  SHA-256, size, clock quality) over MQTT/AMQP+TLS; waveform over HTTPS/SFTP. The manifest is
  what lets the central system know a far-end record *exists* but is late — instead of silently
  producing a single-ended answer.
- **Idempotency by content hash.** Re-delivery is free and harmless; retry-on-anything is safe.
- **Backfill command path** to request a historical record by ID (needed for archive back-test).

### 4.3 Relay recording settings to mandate (else data is unusable)

| Setting | Requirement | Why |
|---|---|---|
| Sample rate | Highest supported (32–96 samples/cycle where available) | Directly limits phasor accuracy |
| Pre-fault window | **≥ 5 cycles** | Takagi (E2) needs clean pre-fault current; 1–2 cycles is not enough |
| Post-fault window | **≥ 20 cycles**, long enough to include the full auto-reclose cycle and dead time | Otherwise reclose analysis is impossible |
| Digital channels | start, Z1/Z2/Z3 pickup, carrier send, carrier receive, trip A/B/C, CB aux 52a per pole, reclose initiate, reclose close | The digital timeline is often the most diagnostic graphic in the report |
| Clock | IRIG-B or PTP where available; record the quality code | Gates E4 only; E5 works without it |

---

## 5. Ingest, conformance and pairing

### 5.1 Conformance gate

Every incoming record runs a fixed checklist. `block` = does not proceed to fault location.
`flag` = proceeds, caveat printed on the report.

| Check | Test | Action |
|---|---|---|
| CFG/DAT integrity | Channel count matches, sample count matches `endsamp`, no truncation | **block** |
| Channel identification | All of IA/IB/IC + VA/VB/VC present and mapped to canonical schema | **block** |
| Ratio sanity | Pre-fault primary voltage within ±15 % of nominal system voltage | **block** — a wrong VT ratio scales the answer silently |
| Current balance | \|IA + IB + IC − IN\| small in pre-fault window | flag — reversed neutral CT polarity |
| Phase rotation | Pre-fault sequence is RYB (or as configured per station) | flag |
| Peak vs RMS scaling | Computed RMS vs nominal; a √2 or √3 discrepancy is diagnostic | **block** |
| Clock quality | `tmq_code` present and ≤ 1 ms error | flag — gates E4 |
| Record window | ≥ 2 cycles pre-fault, ≥ 1.5 cycles usable fault data before first CB opening | flag — degrades estimator |
| Saturation | CT saturation detector fires on any current channel | flag — down-weights that terminal |

### 5.2 Pairing the two ends

Pairing is a **matching problem**, not a lookup: clocks may disagree by seconds, and two lines
off the same busbar can fault in the same second.

1. **Topological (hard filter).** Both records belong to relays registered as terminals of the
   same line in the registry.
2. **Temporal.** Trigger timestamps within a window (default ±5 s; widen to ±60 s for stations
   with no time sync, and flag).
3. **Electrical corroboration (strongest signal).** Both records must agree on fault type;
   \|I₂\| magnitudes at the two ends must be consistent with the two source impedances;
   pre-fault power flow must be equal and opposite within line losses.

When only one end arrives: emit the single-ended report **explicitly marked single-ended**,
hold the incident open for a grace period, and **re-issue a corrected report** if the far-end
record lands late.

**Headline operational KPI: two-ended coverage %** — the fraction of line faults for which both
records arrived. This is the number that says whether the collection layer is healthy.

### 5.3 Incident grouping

One incident absorbs: Main-1 and Main-2 records at each end, auto-reclose attempt records,
and related bus-bar / breaker-failure records. Evolving faults and reclose-onto-fault are
sub-events of one incident, not separate incidents.

---

## 6. Signal processing chain

Implement in this order. Each step's output feeds the next.

| # | Step | Method | Why not the naive alternative |
|---|---|---|---|
| 1 | Resample to common grid | Band-limited (sinc / polyphase) interpolation to the lower of the two rates | Linear interpolation adds amplitude error that propagates straight into the location estimate |
| 2 | Frequency tracking | Zero-crossing or 3-point PLL on pre-fault voltage | A fixed 50 Hz assumption biases the DFT during off-nominal excursions — i.e. during big faults |
| 3 | DC offset removal | Mimic filter matched to line X/R, or explicit exponential fit and subtraction | Decaying DC is the largest phasor error source in the first cycles; plain full-cycle DFT does not remove it |
| 4 | Phasor estimation | Sliding **full-cycle DFT**, one window per sample | Half-cycle DFT converges faster but retains even harmonics — use only when the window is too short, and flag it |
| 5 | Symmetrical components | Standard `a`-operator transform on the phasor stream | — |
| 6 | Superimposed quantities | Δ = fault-cycle minus same phase angle one cycle earlier in pre-fault steady state | Required for E2 and for 3-phase faults where no negative sequence exists |
| 7 | Inception detection | Change detector on \|Δi\|; refine sub-sample by linear interpolation across the threshold crossing | Sample-quantised inception time destroys the relay-operating-time measurement |
| 8 | Fault type classification | Sequence magnitude ratios (\|I₂\|/\|I₁\|, \|I₀\|/\|I₁\|) plus angle of I₂ relative to I₁ to identify involved phase | **Do not trust the relay's own fault-type flag** — misclassification under weak infeed is a documented cause of grossly wrong locations |
| 9 | CT saturation detection | Third-difference discontinuity detector on the sample stream, plus per-half-cycle least-squares residual against a sinusoid+DC model | A saturated CT under-reports current and pushes the location outward |
| 10 | CVT transient flag | Mark first **1.5 cycles** after inception as unusable for voltage phasors | The CVT subsidence transient corrupts voltage exactly where fault data is richest |
| 11 | Window selection | See §6.1 | Most implementations get this wrong |

### 6.1 Analysis window selection — critical

```
t_start = t_inception + 1.5 cycles          # skip CVT subsidence + CT transient
t_end   = min(t_open_S, t_open_R) - 0.5 cycle
```

- Require **≥ 1.0 cycle** overlap for the full-cycle estimator.
- **0.5 – 1.0 cycle**: fall back to half-cycle DFT and flag reduced accuracy.
- **< 0.5 cycle**: single-ended only.
- Where the window permits, **run the estimator at every sample in the window and take the
  median**. The spread across the window is a free, honest uncertainty estimate.

**Worked reality check (50 Hz, 1 cycle = 20 ms), both ends tripping in Zone 1:**

| Instant | Time from inception |
|---|---|
| Fault inception | 0 ms |
| CVT + CT transient ends | 30 ms |
| S-end Z1 trip | 18 ms |
| R-end Z1 trip | 21 ms |
| S-end CB current zero | 58 ms |
| R-end CB current zero | 61 ms |
| **Usable two-ended window** | **30 → 58 ms = 28 ms = 1.4 cycles** |

This is why relay record settings (§4.3) matter more than algorithm choice, and why the
pipeline must degrade gracefully rather than refuse to answer.

---

## 7. Fault location engine

Run **all six** estimators on every incident. They disagree in informative ways, and the
disagreement itself feeds the rules engine (§8).

Notation: `m` = per-unit distance from end S; `Z1L` = total positive-sequence line impedance;
`V2`, `I2` = negative-sequence phasors; `*` = complex conjugate; `Im()` = imaginary part.

### 7.1 Single-ended family (run at each terminal independently)

**E1 · Simple reactance**
```
m = Im( V_loop / I_loop ) / Im( Z1L )
```
For ground loops: `V_loop = V_ph`, `I_loop = I_ph + k0 · 3I0`, where
```
k0 = (Z0L - Z1L) / (3 · Z1L)
```
Fast, but corrupted by the combination of fault resistance and load flow (the classic
reactance effect).

**E2 · Takagi**
```
m = Im( V_S · conj(I_sup) ) / Im( Z1L · I_S · conj(I_sup) )
I_sup = I_S,fault - I_S,prefault
```
Cancels fault resistance when the system is homogeneous. Requires the ≥5-cycle pre-fault
window from §4.3.

**E3 · Modified Takagi with homogeneity correction**
```
m = Im( V_S · conj(3I0) · e^(-j·beta) ) / Im( Z1L · I_S · conj(3I0) · e^(-j·beta) )
```
Uses zero-sequence current instead of superimposed current, so no pre-fault data needed.
`beta` is the current-distribution-factor angle, computed from source impedances in the
registry. **Ground faults only.**

### 7.2 Two-ended family — the primary answer

**E4 · Two-ended synchronised** (only when `tmq_code` ≤ 1 ms at both ends)
```
m = ( V2S - V2R + Z1L·I2R ) / ( Z1L · ( I2S + I2R ) )
```
Negative-sequence quantities, records time-aligned. Independent of fault resistance, load flow
and zero-sequence data. Use **superimposed positive-sequence** quantities for 3-phase faults.

**E5 · Two-ended unsynchronised — THE WORKHORSE, build this first**

The fault-point negative-sequence voltage seen from each end must be equal in magnitude,
whatever the unknown synchronisation angle δ:
```
| V2S - m·Z1L·I2S | = | V2R - (1-m)·Z1L·I2R |
```
Substituting `A = V2S`, `B = Z1L·I2S`, `C = V2R - Z1L·I2R`, `D = Z1L·I2R`, this becomes a
**real quadratic in m**:
```
( |B|^2 - |D|^2 )·m^2  -  2·[ Re(A·conj(B)) + Re(C·conj(D)) ]·m  +  ( |A|^2 - |C|^2 )  =  0
```
Solve; take the root in [0, 1]. Then recover the synchronisation angle:
```
delta = arg( V2S - m·Z1L·I2S ) - arg( V2R - (1-m)·Z1L·I2R )
```
Requires **no GPS, no time alignment, no zero-sequence impedance, no mutual-coupling
compensation.** For 3-phase faults, substitute superimposed positive-sequence quantities.

> **Free consistency check — implement this, it is one line and catches most silent failures.**
> The recovered `delta` is a physical quantity: the clock offset between the two records,
> expressed in degrees at system frequency. Compare it against the offset implied by the two
> trigger timestamps. Disagreement beyond a few degrees means wrong pairing, wrong ratio, or a
> saturated CT. Emit finding MS-03.

**E6 · Ensemble reconciliation**

Weight each estimator by:
- (a) the residual of its own defining equation across the analysis window;
- (b) its prior accuracy on this line class from the back-test archive;
- (c) hard gates — E4 disabled without clock quality; E3 disabled for phase faults; any
  estimator from a terminal with detected CT saturation down-weighted by an order of magnitude.

Report the weighted estimate, the **90 % interval from the window-wise spread**, the winning
method **by name**, and the full per-method table. **Never report a single number with no
method attached.**

### 7.3 From per-unit to a tower number

Two conversions routinely done wrong:

1. **Non-uniform lines.** `m` is per-unit of **reactance**, not of length. Walk the line-section
   table accumulating reactance until reaching `m`, then convert that section's fraction to km.
   A linear length conversion on a mixed-conductor line can be kilometres out.
2. **Chainage, not kilometres.** The patrol team works in tower numbers. Report
   *"between tower 118 and 124, most likely 121"* alongside *"km 43.7 ± 1.2 from Bus A"*.

### 7.4 Accuracy targets (as % of line length)

| Condition | Single-ended | Two-ended |
|---|---|---|
| SLG, low R_F, strong sources, good records | 1–3 % | 0.1–0.5 % |
| SLG, high R_F (tree, bird, pollution flashover) | 3–15 % | 0.3–1.0 % |
| Weak infeed at one end | > 20 %, sign errors possible | 0.5–2 % |
| Double-circuit with mutual coupling | 2–10 % | 0.2–1.0 % |
| Three-phase fault | 1–4 % | 0.3–1.5 % |
| Short window (< 1 cycle overlap) | 3–10 % | 1–4 % |

---

## 8. Conclusions engine

Rules are **data, not code**: each is a YAML entry with a condition over the computed feature
set, a severity, an evidence pointer (channel + time), and a recommended action. Protection
engineers must be able to add rules without a software release.

Every finding rolls up to one of three verdicts on page 1 of the report:
**Correct operation** / **Correct but investigate** / **Incorrect operation**.

### 8.1 Starter rule catalogue

| ID | Title | Condition and meaning |
|---|---|---|
| FL-01 | Zone-1 operation beyond reach | Z1 asserted but reconciled location > Z1 setting (typically 80 % of line). Suspected overreach: check Z1 reach, k0, or relay CT/VT ratio. |
| FL-02 | In-zone fault cleared in Zone 2 time | Location within Z1 reach but tripping delayed to Z2. Suspected underreach or failed teleprotection — cross-check CR-01. |
| CR-01 | Carrier receive absent | Carrier send asserted at one end, no receive at the other, for an in-section fault. PLCC/teleprotection defect. **Highest-value finding in the catalogue and invisible without two-end data.** |
| CR-02 | Asymmetric clearing | Clearing times differ by more than one Z2 step. Scheme coordination or channel issue. |
| CB-01 | Breaker time out of spec | Trip contact to current zero exceeds type-test time by > 10 ms. Feeds breaker maintenance with an objective measurement. |
| CB-02 | Pole discrepancy | Per-pole current zeros differ by > half a cycle. Mechanism or interrupter concern. |
| CB-03 | Restrike / re-ignition | Current reappears after interruption within the same half-cycle. Interrupter degradation. |
| AR-01 | Reclose onto permanent fault | Reclose followed by immediate re-trip at the same computed location. Drives whether a patrol is dispatched at all. |
| AR-02 | Dead time out of setting | Measured dead time deviates from configured value by > 10 %. |
| FT-01 | Evolving fault | Fault type changes during the record (e.g. R-G → R-Y-G). Different estimators valid in different sub-windows; must be handled, not averaged. |
| FT-02 | Cross-country fault | Ground faults on different phases at the two ends in the same window. Single-ended location is meaningless; **suppress two-ended and escalate.** |
| FT-03 | High arc resistance | Estimated R_F greatly exceeds the Warrington estimate `R_arc ≈ 28710 · L / I^1.4` (L in m, I in A) for the flashover distance. Suggests tree/bird/pollution rather than clean insulator flashover — different maintenance action. |
| MS-01 | CT saturation | Reports terminal and phase, quantifies impact, down-weights that terminal. |
| MS-02 | VT fuse failure / MCB trip | Voltage collapse on one or two phases with no corresponding current change. Prevents a spurious fault report. |
| MS-03 | Sync-angle inconsistency | δ recovered from E5 disagrees with timestamp-implied offset. Wrong pairing, wrong ratio, or bad data. |
| SY-01 | Switch-onto-fault | Fault current within one cycle of CB close, no healthy pre-fault period. Different clearing logic; must not be scored as a protection failure. |
| SY-02 | Power swing / out-of-step | Slow smooth impedance trajectory entering the characteristic without a step change in current. Also flags whether blocking operated correctly. |
| SY-03 | Zone-3 on load encroachment | Z3 pickup with balanced currents, no negative or zero sequence, near-nominal voltage. A recognised contributor to cascading events in the Indian grid — report every occurrence. |
| AS-01 | Repeat-offender section | ≥ 3 faults located within the same ±2-span band over the rolling window. Drives targeted patrol, insulator replacement, tree cutting. **Highest-ROI output of the system.** |
| AS-02 | Fault level trending | Measured through-fault current at a terminal drifting against design short-circuit level. Feeds switchgear rating review. |

---

## 9. The learning layer — three tiers, in this order

### 9.1 Tier 1 — estimate line parameters, do not correct the answer (**build first**)

The dominant residual error in impedance-based location is **wrong line data**, particularly
`Z0`, which is routinely taken from a design calculation, is soil-resistivity dependent, and is
often 10–20 % wrong.

With two-ended records you can solve for the line's **actual `Z1` and `Z0`** from the fault data
itself, using records already being collected. This is parameter estimation, not machine
learning; it needs only a handful of events; and it improves **every** subsequent single-ended
calculation — including the one the relay itself performs.

Reference: Wang et al., *Algorithms and field experiences for estimating transmission line
parameters based on fault record data*, IET GTD (2015).

### 9.2 Tier 2 — hierarchical residual model, pooled across the fleet

Define residual `e = d_true - d_model` in per-unit of line length. Fit a partial-pooling
(mixed-effects / hierarchical Bayesian) model:

- **Fixed effects** — features available at prediction time: fault type, estimated R_F,
  source-impedance ratio at each end, pre-fault load angle, `m` itself (catches reach
  non-linearity), \|I₂\|/\|I₁\|, saturation flags, window length in cycles, season.
- **Random effects per line** — a scalar correction on X₁ per km and a complex correction on
  `k0`. **Two or three parameters, not thousands.** A line with one confirmed fault contributes
  almost nothing and shrinks to the fleet mean; a line with fifteen gets a real correction.
- **Output** — a corrected distance **with a posterior interval**. The interval is the product,
  not the point estimate.

**Guardrails (non-negotiable):**
- (a) Cap the correction at **±2 % of line length**.
- (b) Always print **both** the raw physics estimate and the corrected estimate on the report.

**Gate:** do not start Tier 2 until **≥ 100 confirmed ground-truth events exist across the
fleet.**

### 9.3 Tier 3 — use ML where labels are actually plentiful

These are supervised problems with thousands of labels available, where learned models
genuinely beat hand-written rules:

- **Fault type classification** — labels from confirmed post-event analysis, not patrol.
- **CT saturation detection** — labels generated synthetically in unlimited quantity from a CT model.
- **Record quality anomaly detection** — unsupervised; catches ratio errors, polarity errors,
  channel-mapping drift as the fleet changes.
- **Incident clustering** — groups faults by electrical signature to surface repeat causes.

**Synthetic data is the way out of the small-sample trap.** Published physics-informed methods
generate 10⁵–10⁶ simulated fault cases from an EMT model of the actual line, constrained to
parameter ranges estimated from field records, train on those, and validate on the handful of
real events — reporting ~0.1 km field errors on 220 kV lines (arXiv:2307.09740). That path
requires an accurate line model per corridor, which is exactly what Tier 1 produces.

**Tier 1 → synthetic generation → Tier 3 is one coherent programme. Per-relay training on ten
real faults is not a step on that path.**

### 9.4 Validation of the learning layer

- **Leave-one-line-out** cross-validation, never a random split. A random split leaks the same
  line's events across train and test and flatters the model badly.
- Report **MAE in km and as % of line length**, plus the **90th percentile error** — the tail is
  what destroys credibility with the patrol team.
- Report the **baselines** alongside: the relay's own reported location, and the raw two-ended
  estimate. **If the learned layer does not beat the raw two-ended estimate on held-out lines,
  it does not ship.**

---

## 10. The two-page report

Page 1 is a decision. Page 2 is the evidence for it. Everything else goes to the interactive
event view, linked by QR from page 1.

### 10.1 Page 1 — the decision (readable in 90 seconds by a shift engineer)

| Block | Content |
|---|---|
| Header band | Line name, both substations, voltage, incident ID, fault date/time to the millisecond, report issue time |
| **Verdict banner** | One of three states + the single most important finding in one sentence. Largest element on the page. |
| **Fault location (headline)** | km from each end, ± interval, **between tower N and tower M**, method used, and agreement/disagreement vs the relay's own reported location |
| Fault summary | Type and phases, inception instant, fault current at each end, estimated fault resistance, total duration, breaker operations |
| Clearing performance | Two rows, one per end: relay operating time, breaker time, total clearing time, zone operated, carrier send/receive, against spec |
| Auto-reclose outcome | Attempted / successful / locked out, dead time, whether reclose was onto a permanent fault |
| Findings — **top three only** | From §8, ranked by severity, each with recommended action and owner |
| **Ground-truth capture** | QR code + short URL: "confirm the tower where the fault was found". **This block is what makes §9 possible.** |

### 10.2 Page 2 — the evidence

| Block | Content |
|---|---|
| Aligned oscillograms, both ends | Currents and voltages on a common time axis, aligned by recovered δ. Phase colours R/Y/B. Inception, trip and CB-open marked. |
| Digital channel timeline | Start · Z1 · Z2 · carrier send · carrier receive · trip A/B/C · 52a per pole · reclose initiate · reclose close, both ends on one axis. Often the most diagnostic graphic. |
| Impedance trajectory on R-X | Measured loop impedance against the actual relay characteristic and zone settings from the registry. Shows overreach, underreach, load encroachment instantly. |
| Phasor diagram at analysis instant | Both ends, sequence components, recovered sync angle annotated |
| Method comparison table | All six estimators, outputs, residuals, weights. Shows *why* the reconciled answer was chosen. |
| Data quality caveats | Every conformance flag raised at ingest, in plain language. **Never hide a caveat to make the report look cleaner.** |
| Section history footer | Previous faults located within ±2 spans over the rolling window |

---

## 11. Data model

Registry entities are the part to get right first; everything else can be rewritten cheaply.

| Entity | Key fields | Notes |
|---|---|---|
| `line` | id, name, voltage, ckt_no, length_km, is_double_circuit, in_service_from | Two terminals; length derived from section table, never entered twice |
| `terminal` | line_id, substation_id, end (S/R), bus | Exactly two per line |
| `relay` | terminal_id, make, model, firmware, function (main1/main2/backup), comms path, retrieval protocol | Drives which collector adapter is used |
| `line_section` | line_id, seq, from_chainage, to_chainage, conductor, R1, X1, B1, R0, X0, B0 (Ω/km) | Enables correct per-unit-reactance → km conversion on mixed lines |
| `mutual_coupling` | line_id, coupled_line_id, from_chainage, to_chainage, Z0m | Needed only for single-ended methods on double-circuit lines |
| `instrument_transformer` | terminal_id, ct_ratio, ct_class, ct_knee, ct_burden, vt_ratio, vt_type (VT/CVT) | CVT flag drives the §6 step-10 transient window |
| `relay_setting` | relay_id, effective_from, effective_to, Z1/Z2/Z3 reach & angle, k0 mag & angle, timers, scheme type | **Version this.** An event is judged against settings in force at that instant, not today's. |
| `tower` | line_id, tower_no, chainage_km, type, lat, lon | Makes the report usable by the line crew |
| `source_impedance` | terminal_id, scenario (max/min gen), Z1s, Z0s, fault levels | Feeds homogeneity angle β and ensemble weighting |
| `record` | hash (PK), relay_id, trigger_time, sample_rate, n_samples, clock_quality, conformance_flags, blob_uri | Content-addressed, immutable |
| `incident` | line_id, first_inception, fault_type, is_evolving, reclose_outcome | **Top-level object.** Many records, one incident. |
| `location_estimate` | incident_id, method, m, km_from_S, residual, weight, algo_version | One row per estimator per incident — **never overwrite, always append** |
| `finding` | incident_id, rule_id, severity, evidence, recommended_action, status | Lifecycle: open → acknowledged → actioned |
| `ground_truth` | incident_id, tower_no, chainage_km, cause, confirmed_by, confirmed_at, confidence | **Scarcest and most valuable table in the system** |

### 11.1 Companion data-collection workbook

A workbook `DR_Analyser_Data_Collection.xlsx` accompanies this document and is to be circulated
to substation / protection engineers at both ends of every line. Its sheets map 1:1 onto the
registry entities above:

| Sheet | Maps to | Criticality |
|---|---|---|
| 00 README | — | Instructions, colour legend |
| 01 Line Master | `line` | Fill first — the Line ID is the key everywhere else |
| 02 Terminal & Relay | `terminal`, `relay` | Decides which retrieval adapter is needed |
| 03 Line Sections | `line_section` | **CRITICAL** — Z0 error is the largest single cause of wrong location |
| 04 Mutual Coupling | `mutual_coupling` | Double-circuit lines only |
| 05 CT & VT | `instrument_transformer` | Wrong ratios scale the answer directly |
| 06 Relay Settings | `relay_setting` | Versioned — new row per change, never overwrite |
| 07 Tower Schedule | `tower` | **CRITICAL for usefulness** — converts km into a tower number |
| 08 Source Impedance | `source_impedance` | Homogeneity correction |
| 09 Historical Faults | `ground_truth` + past incidents | **CRITICAL for §9** — only patrol-confirmed rows; blanks beat guesses |
| 99 Lists | — | Dropdown validation lists |

---

## 12. Technology stack

| Concern | Choice | Rationale |
|---|---|---|
| Numerics & DSP | Python · NumPy / SciPy | The protection-analytics literature is reproducible in it; utility engineers can read the code |
| COMTRADE parsing | **Write your own**, tested against a corpus of real vendor files | Every off-the-shelf parser assumes conformance you will not get. Two-week job; saves a year of mysteries. |
| Registry & events | PostgreSQL | Relational with strict constraints — the registry is where correctness lives |
| Waveform storage | Object store (MinIO on-prem / S3), content-addressed by hash | Immutable, cheap, trivially re-processable |
| Orchestration | Celery or Temporal | Retries and idempotent re-runs are first-class requirements |
| Transport broker | EMQX / RabbitMQ over TLS, mutual TLS with per-substation certificates | Manifest channel |
| API & web view | FastAPI + React | — |
| PDF generation | WeasyPrint (HTML→PDF) or ReportLab | HTML templating keeps the two-page layout maintainable by non-programmers |
| Learning layer | statsmodels / PyMC (Tier 2); scikit-learn (Tier 3) | Interpretable and auditable |
| Deployment | Docker Compose (single site) → Kubernetes (multi-region), **air-gap capable** | No dependency on outbound internet at run time |

### 12.1 Suggested repository layout

```
dr-analyser/
├── PROJECT_CONTEXT.md          # this file
├── docs/
│   ├── adr/                    # architecture decision records
│   └── standards/              # extracts / references
├── packages/
│   ├── comtrade/               # parser + conformance gate + normaliser
│   ├── dsp/                    # §6 chain
│   ├── faultloc/               # §7 estimators E1–E6
│   ├── rules/                  # §8 engine + YAML rule catalogue
│   ├── registry/               # §11 schema, migrations, loaders (incl. xlsx importer)
│   └── report/                 # §10 templates + PDF renderer
├── services/
│   ├── ingest/                 # L3
│   ├── correlate/              # L5 pairing
│   ├── analyse/                # L6–L8 orchestration
│   └── api/                    # FastAPI + web view
├── edge/
│   └── collector/              # L0–L2, per-vendor adapters
├── tests/
│   ├── corpus/                 # real vendor COMTRADE files (redacted)
│   ├── synthetic/              # generated fault cases with known m
│   └── golden/                 # end-to-end expected outputs
└── notebooks/                  # validation and back-test analyses
```

---

## 13. Validation plan and acceptance criteria

Write these into the project charter **now**, before anyone is invested in the answer.

| Stage | Method | Sample | Acceptance criterion |
|---|---|---|---|
| **A · Synthetic** | EMT / short-circuit simulation of the actual lines, sweeping m, fault type, R_F, SIR, inception angle, CT saturation, sampling rate | 10⁴–10⁵ cases | Two-ended error < 0.5 % of line length in 95 % of clean-data cases; algorithm never returns a physically impossible `m` without flagging it |
| **B · Archive back-test** | Replay every historical DR pair recoverable; compare against relay-reported location and any recorded patrol result | All available | Two-ended beats the relay's own single-ended figure on ≥ 80 % of events where both exist |
| **C · Shadow running** | System runs live and issues reports; patrol dispatch still follows the existing process; both logged | 6 months | ≤ 1.0 % error for 80 % of two-ended events; ≤ 2.0 % for 95 %; two-ended coverage ≥ 70 % of line faults |

**Report the tail, not the mean.** Publish the 90th-percentile error. A locator with 0.4 % mean
error and occasional 15 % excursions will be abandoned by the line crew after the second wasted
patrol.

---

## 14. Definition of done for the first PR

Before adding any pipeline, service, UI or ML, the first deliverable is:

1. A **COMTRADE parser** handling 1991 / 1999 / 2013 editions, ASCII and binary, `.CFF` and the
   four-file form, with a test corpus of real vendor files.
2. The **§5.1 conformance gate** as a pure function returning structured flags.
3. The **§6 DSP chain** steps 1–8, unit-tested against synthetic waveforms with known content.
4. **E5** (§7.2) plus **E1/E2** as baselines, with the δ consistency check.
5. A **CLI** that takes two COMTRADE record paths + a line parameter file and prints the
   per-method table and the reconciled estimate.
6. A **synthetic test harness** that generates fault cases with known `m` and asserts the
   Stage-A criterion in §13.

That CLI, run against a pair of real archived records, is the proof the project works. Build
everything else after it.

---

## 15. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Far-end record frequently missing → two-ended coverage collapses | **High** | Track coverage % as a headline KPI from day one; manifest-first transport makes a missing record immediately visible; escalate collection defects as operational faults, not IT tickets |
| Registry data (Z0, k0, tower chainage) wrong or unobtainable | **High** | This is what the data-collection workbook is for. Missing Z0 blocks single-ended methods but **not E5** — a strong argument for making E5 primary |
| Relay record settings too short for two-ended analysis | Medium | Audit and change settings in Phase 1, before building anything that depends on them |
| Clocks unsynchronised across substations | Medium | Already handled — E5 needs no synchronisation. Do not let this become a project dependency. |
| Ground truth never flows back | **High** | Organisational, not technical. One click on the report, a named owner, monthly confirmation-rate reporting to whoever owns patrol costs |
| Cyber-security review blocks the transport design late | Medium | Involve the OT security owner in Phase 1. Push-only, one-way, mutual TLS, no inbound path — design it to pass first time |
| Scope creep into traveling-wave location | Medium | §2.2 is written to be quoted back |
| Report becomes a wall of waveforms nobody reads | Medium | Hold the two-page discipline. Page 1 is a decision, not a data dump. |

---

## 16. Roadmap

| Phase | Window | Deliverables |
|---|---|---|
| **1** | months 0–3 | COMTRADE parser + conformance gate tested against a real multi-vendor corpus · registry schema loaded for a pilot corridor of 5–10 lines · DSP chain and estimators E1–E5 with ensemble · two-page PDF from a manually supplied record pair · Stage-B archive back-test |
| **2** | months 3–6 | Edge collector for the 2–3 relay families in the pilot corridor · transport, store-and-forward, ingest, pairing · conclusions engine with starter rule catalogue · web event view, automatic distribution, ground-truth capture by QR · begin Stage-C shadow running |
| **3** | months 6–10 | Remaining relay families; regional rollout · Tier 1 line-parameter estimation · repeat-offender and fleet-health dashboards · rule catalogue extended by the protection group themselves |
| **4** | months 10–15 | Tier 2 hierarchical residual model (gated on ≥ 100 confirmed ground-truth events) · synthetic-data programme for Tier 3 seeded by Tier 1 estimates · leave-one-line-out validation against the raw two-ended baseline; ship only if it wins |

---

## 17. [OPEN] Decisions not yet made

Each changes the design materially. A default assumption is stated; overrule it explicitly
rather than silently.

| # | Question | Assumed default | What it changes |
|---|---|---|---|
| 1 | Which relay makes/models are in the fleet, in what proportion? | Mixed Siemens SIPROTEC / ABB REL / GE-Alstom MiCOM / SEL with a legacy tail | How many collector adapters; whether path A, B, C or D dominates |
| 2 | How many substations and line terminals, over what WAN? | Tens of substations on a utility MPLS/OPGW WAN with intermittent availability | Transport sizing; per-substation vs per-region collector |
| 3 | Are both terminals of each line under the same utility's control? | Yes for most, no for inter-utility tie lines | Tie lines are permanently single-ended without a data-sharing agreement — affects the promised coverage figure |
| 4 | IRIG-B / PTP time sync present? Does the relay stamp clock quality? | Partial, unreliable | Whether E4 is ever usable. If "no", nothing changes — E5 carries the system |
| 5 | How many years of archived DRs and patrol results are recoverable? | Some archive exists but is unindexed | Entire input to Stage-B validation and the first Tier-1 parameter estimates. Worth a dedicated work package. |
| 6 | Buy or build the collection layer? | Build (originator framed collection as already in hand) | If buying is allowed, do it and spend the saved months on §7–§9 |
| 7 | Internal tool or a product to be sold? | Internal | A product makes multi-tenancy, vendor-neutrality guarantees and a conformance test suite first-class; the rule catalogue becomes the sellable asset |
| 8 | What is in `E:\dr analyser`? | Unknown — never reviewed | May already contain a parser, sample records or a UI prototype. Reconcile before writing new code. |

---

## 18. Sources

1. IEEE Std C37.114-2014 — *Guide for Determining Fault Location on AC Transmission and Distribution Lines* — https://ieeexplore.ieee.org/document/7024095/
2. Softstuf — *Double-Ended Fault Location Application using IEEE C37.114* (2013) — https://www.softstuf.com/2013%20FDC%20Double%20Ended%20Fault%20Location%20Paper.pdf
3. Zimmerman & Costello — *Impedance-Based Fault Location Experience*, Schweitzer Engineering Laboratories — https://selinc.com/api/download/4912
4. IEEE PSRC — *Summary of Changes in the 2013 COMTRADE Standard* — https://www.pes-psrc.org/kb/report/1014.pdf
5. IEEE Std C37.111-2013 / IEC 60255-24 — COMTRADE — https://ieeexplore.ieee.org/document/6512503/
6. IEEE Std C37.232-2011 — COMNAME — https://ieeexplore.ieee.org/document/6081885/
7. IEEE Std C37.239 — COMFEDE — https://ieeexplore.ieee.org/document/5514460/
8. *A Physics-Informed Data-Driven Fault Location Method for Transmission Lines Using Single-Ended Measurements with Field Data Validation* — https://arxiv.org/abs/2307.09740
9. Wang et al. — *Algorithms and field experiences for estimating transmission line parameters based on fault record data*, IET GTD (2015) — https://ietresearch.onlinelibrary.wiley.com/doi/full/10.1049/iet-gtd.2014.1092
10. Novosel & Hart — *Unsynchronized Two-Terminal Fault Location Estimation* — https://www.semanticscholar.org/paper/ce0ee35226b59a15a5c2d1df0bad2e386b671b46
11. Siemens — *SIPROTEC Fault Record Analysis SIGRA* manual — https://cache.industry.siemens.com/dl/files/837/109752837/att_1362568/v1/SIGRA_MANUAL_B5_EN.pdf
12. SEL-5601-2 synchroWAVe Event Software — https://selinc.com/products/5601-2/
13. Kalkitech — Centralised IED Management & Substation Fault Record Collection — https://kalkitech.com/products/control-room-software/ied-management/
14. IEEE PSRC — *Considerations for Use of Disturbance Recorders* — https://www.pes-psrc.org/kb/report/102.pdf
15. SEL — Traveling-Wave Fault Locating (sampling-rate requirements) — https://selinc.com/solutions/traveling-wave-fault-location/

---

*End of PROJECT_CONTEXT.md*
