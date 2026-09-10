# CIGRE TB 854: methods and useful content for the DR analyser

Extracted 2026-09-08 from **Analysis and comparison of fault location systems
in AC power networks**, CIGRE WG B5.52, Technical Brochure 854, December 2021,
ISBN 978-2-85873-559-4. Local source: `E:/cigre/854.pdf`, 137 PDF pages.
Printed page numbers equal the one-based PDF page positions from page 3.
SHA-256: `0406508feb3154dff584a5818823ea6be01b0dd1e82f523d0d7ac2d8797a7886`.

This is a selective engineering synthesis for this project. Source claims
have page/section locators; proposed work and mathematical interpretations
are labelled separately. Text was extracted across the PDF, with detailed
review of relevant sections and visual checks of key equations and tables.
This note does not certify the analyser or turn the brochure into a settings
standard. The original PDF, full extracted text and rendered pages stay local.

## 1. What matters most to this project

The brochure supports using existing relay recordings for centralised
impedance-based analysis, including unsynchronised two-ended methods
(pp. 9-14, 28-31). Our E1-E5 family already covers much of that foundation.
Its greatest additional value is in **model validity, window selection,
mixed sections, double-circuit coupling, and field feedback**.

| Priority | Finding and source | Project implication / proposed work |
|---|---|---|
| P0 | Incorrect line constants materially affect results; measured parameters improved a specific field series (pp. 24-26, Table 5). | Obtain verified section lengths and impedances. Existing provisional registry values cannot establish operational accuracy. |
| P0 | Asymmetry couples sequence networks, especially on parallel circuits (pp. 53-56, equations 25-27). | Assess the Garividi-Maradam corridor's geometry and adjacent-circuit state. Negative-sequence E5 avoids explicit Z0 input but is not universally immune to coupling. |
| P1 | Mixed lines require calculating electrical quantities at section boundaries (pp. 47-51, equation 24). | Add a section-aware electrical solver. `Line.m_to_km()` already walks reactance sections, but that conversion alone does not solve varying R/X, Z0/Z1 or shunt admittance. |
| P1 | Fault windows must settle after inception and finish before the circuit changes (pp. 26-27). | Extend window validation for evolving faults, per-pole opening and unequal end clearing; compare the same fault stage at both ends. |
| P1 | Time-tag faults and autoreclose make file correlation difficult (p. 29); different vendor filtering also matters (p. 105). | Supports the existing pairing priority and electrical corroboration first. Add filter provenance and event-stage evidence to pairing. |
| P2 | Tower maps, environmental evidence and actual inspection results improve use of estimates (pp. 79-90). | Give patrols a tower interval, keep environmental matches as corroboration, and retain confirmed locations and repeated temporary faults. |

Priorities above are project judgment, not priorities assigned by CIGRE.
CT saturation remains a major project gap, but TB 854 identifies the error
source rather than providing a ready-to-implement waveform reconstruction
algorithm (pp. 11, 24, 27). It does not remove that research/validation need.

## 2. Method inventory and implementation fit

| Method | Inputs and assumptions from the brochure | Current fit / boundary |
|---|---|---|
| Reactance | Fault V/I and line reactance; line/source angle assumptions affect resistance error (pp. 9-11, Table 2). | E1 exists. Retain as a gated single-ended estimate. |
| Takagi | Pre-fault current, fault current/voltage and line impedance; load compensation relies on the model assumptions (p. 10, Table 2). | E2 exists. Preserve the repository's compensated loop-current denominator. |
| Modified Takagi | Fault V/I and line impedance; partial correction for source-angle differences (p. 10). | E3 exists with source impedances for its iterative distribution-factor correction. TB's brief table does not fully specify this exact variant. |
| Eriksson | Pre-fault/fault quantities, local and remote source impedances, potentially parallel-line zero-sequence current; negligible charging and stable source assumptions (p. 10). | Not implemented as a separate estimator. Candidate only after source/topology data exist; Table 2 is not a complete algorithm. |
| Synchronised two-ended | Equal fault-point voltages from two ends; phasors share a reference and fault stage (pp. 11-12, equations 5-8). | E4 exists, with clock gating and an imaginary-component diagnostic. A separate one-end-voltage/two-end-current variant is described by equation 8. |
| Unsynchronised two-ended | Iterative angle recovery, pre-fault alignment, and non-iterative sequence methods are described (pp. 12-13). | E5 exists as a magnitude-equality quadratic with branch checks. The brochure does not give our exact quadratic or establish our root-selection policy. |
| Current-magnitude model matching | End current magnitudes and an accurate short-circuit network model; search for a simulated current ratio matching observation (pp. 13-14, 31-33). | Useful independent candidate if voltage evidence is unusable, but no such network-model adapter exists. It cannot manufacture missing line/source data. |
| Distributed voltage-drop | Several voltage monitors, impedances, topology, pre-fault calibration, fault classification and section search (pp. 14-15, Annex A pp. 117-118). | Primarily a distribution-network extension, outside the current two-terminal deployment. Do not import its one-second timestamp-grouping assumption into our fleet. |
| Section-aware impedance | Transfer V/I across known healthy sections, then locate within candidate sections (pp. 47-51). | High-value extension to the existing section registry; no section-boundary estimator presently exists. |
| Coupled phase/sequence model | Self and mutual impedance matrices; inter-circuit state changes the observed impedance (pp. 53-56, Annex F p. 124). | High-value model extension, not equivalent to merely adding a scalar mutual k0. |
| Travelling wave | High-bandwidth acquisition, suitable transducers and wavefront processing (pp. 15-20, 24, 33-47). | Excluded by `PROJECT_CONTEXT.md` section 2.2. Ordinary relay DR data do not supply the missing bandwidth. |
| Three-/multi-terminal, FCI, PMU and distribution methods | Additional topology and measurement coverage (pp. 21-23, 56-78, 91-94). | Reference material, not an expansion of current project scope or a new GPS dependency. |

For balanced ABC faults, negative sequence becomes negligible (p. 12).
`faultloc/ensemble.py` already uses superimposed positive sequence in that
case. The brochure mentions positive sequence as an alternative; the
superimposed implementation and its quality gates are project choices.

## 3. Equations normalised to our conventions

These equations are an engineering translation/derivation for review, not a
literal transcription. Currents point **from each bus into the line**.
`I0 = (IA + IB + IC)/3`; `IN = 3*I0`. For a homogeneous scalar line the
distance fraction is both length and impedance fraction. The project uses
`m` as a fraction of total positive-sequence series reactance when converting
through sections; that does not make a homogeneous electrical model exact
for every non-homogeneous line.

### Ground loop and compensation (pp. 9-10)

```text
k0 = (Z0L - Z1L) / (3*Z1L)
I_loop = I_phase + k0*IN = I_phase + 3*k0*I0
V_phase = m*Z1L*I_loop + Rf*If
```

The coefficient must match whether the input is residual or sequence
current. Table 1's printed convention is inconsistent; see section 7 below.
Vendor-native k0 conversion in `registry/model.py` remains authoritative
for our implementation.

### Equal fault-point voltage and clock angle (pp. 11-13)

```text
VF_S(m) = VS - m*ZL*IS
VF_R(m) = VR - (1-m)*ZL*IR
q = (VS - VR + ZL*IR) / (ZL*(IS + IR))
```

With truly aligned phasors and a valid scalar model, `q` is real and equals
`m`. Our E4 returns `Re(q)` and retains `abs(Im(q))` as inconsistency
evidence. It does not replace this with the magnitude printed in equation 7.

With an unknown common rotation at the remote terminal, eliminate that
rotation through `abs(VF_S(m)) = abs(VF_R(m))`. Expanding this equality
produces the quadratic used in E5. This is a project derivation connected
to the brochure's unsynchronised-method discussion, not an equation printed
there. A small magnitude residual alone cannot identify a bad CT ratio or
prove that the selected root is physically correct.

The p. 12 discussion gives 3 degrees as generally accepted angle-error
guidance. At 50 Hz that is `3/(360*50) = 166.7 microseconds` (derived).
It is not a guaranteed accuracy bound or a reason to relax our clock gate.
An unsynchronised phasor method still needs matching fault regimes; it does
not solve record pairing or fault evolution by itself.

### Section propagation (equation 24, p. 48)

```text
V_next = V_current - Z_section*I_current
I_next = I_current                     # series-only section
```

Proposed extension: walk healthy sections from each terminal and solve for
a position inside each candidate section. Convert that section-local
distance to global chainage and then to the repository's reactance fraction.
Retain all plausible intersections when the observations do not distinguish
them. With shunt admittance, use a consistently derived two-port transfer
model instead of assuming constant current. The brochure supports this
modelling direction; it does not supply a complete distributed-parameter
replacement for E5. `LineSection.b1/b0` fields exist but the present
fault-location equations use the summed series impedance.

### Asymmetry and coupling (pp. 53-56; Annex F, p. 124)

The brochure represents a double circuit using a 6-by-6 phase impedance
matrix. Its diagonal blocks describe each circuit and its off-diagonal
blocks describe coupling between circuits. Transforming an asymmetric model
to sequence coordinates need not diagonalise it.

Annex F illustrates a positive-sequence voltage-drop equation with terms
`Z11*I1 + Z12*I2 + Z10*I0`. Thus omitting explicit `Z0` from E5 does not
prove immunity to all zero-sequence-related effects when cross-sequence
coupling exists. Annex F alone is not a complete six-conductor corridor
solver. Derive the transform using our phase order and current directions,
and validate independently before any implementation.

## 4. Data-quality, pairing and confidence content

| Source content | Proposed application |
|---|---|
| CT/CVT transformation, transient and bandwidth errors (pp. 11, 24, 27). | Retain CT saturation, ADC clipping and VT defects separately; record eligible samples and why a method was suppressed. TB 854 supplies no numerical saturation detector threshold. |
| One-cycle Fourier windows are common; settling, frequency error and breaker action constrain placement (pp. 26-27, Figure 12). | Validate each estimator window against the actual event. The 1.5-cycle example is not a mandatory delay and may leave insufficient data on a fast trip. |
| Clock defects complicate pairing, especially through autoreclose (p. 29). | Match asset identity, electrical signature and shot/stage; retain timestamps with their uncertainty. Fleet evidence still requires electrical corroboration before narrow timestamp filtering. |
| Vendors may record raw or filtered waveforms at different rates (p. 105, survey comment). | Proposed manifest fields: signal/filter provenance, rate, known delay and time-reference quality. Resampling alone does not undo unknown filter response. |
| Parameter units include per-length, total and per-unit values (p. 25). | Preserve units, frequency, base MVA/kV, measurement/design provenance, section boundaries and effective dates. Never substitute a nominal conductor table for measured line data silently. |
| Accuracy can be expressed in km and percent of total line length (p. 6). | Report signed bias separately from absolute errors, plus mean/p90/p95, refusal rate and interval coverage on held-out incidents. These evaluation choices are project proposals. |

The brochure does **not** prescribe our 0.5% acceptance target, estimator
weights, confidence level or interval floor. The current spread-based
ensemble interval is not calibrated coverage merely because it is displayed
as an interval. Evaluate observed coverage, parameter uncertainty and shared
model bias; correlated estimators are not independent confirmation.

For Tier 1, a fitted k0 can absorb omitted coupling, source assumptions or
measurement error. Proposed prerequisite: validate the E5 geometry and
ground-loop model before using an incident to update Z0. Keep original
parameters and evidence. This is a project inference from pp. 24-26 and
53-56, not a Tier-1 algorithm supplied by TB 854.

## 5. Field examples worth retaining

These are examples from the brochure, not benchmarks run by this project.
They do not establish fleet-wide accuracy or provide reusable COMTRADE data.

| Source and sample | Reported result | Useful lesson / qualification |
|---|---|---|
| Table 5, pp. 25-26: 12 ground-fault records at the same 60.8 km location on one 92.3 km, 420 kV line. | DFR mean error reported as 4.8 km with table parameters and 2.3 km with measured parameters. | Strong motivation to improve inputs; repeated observations at one site are not broad validation. Table contains arithmetic inconsistencies, so these are reported summary values. |
| pp. 29-31: one 124.7 km, 400 kV line fault, inspected at 34.5 km from S. | Single-ended errors 4.6% and 7.9%; manually aligned two-ended error 0.78%. | Reusing remote records can help. This is neither E5 validation nor evidence of an automatic alignment guarantee. |
| pp. 49-50, Tables 8-9: one fault on a four-section overhead/cable 230 kV line. | Section-aware absolute error 0.09 mile versus 2.18 miles for the conventional summed-impedance two-ended method. | A useful future model-validation scenario. Terminal naming is inconsistent in the prose; resolve before constructing an oracle. |
| pp. 54-55, Table 11: 11 listed events on an asymmetric 500 kV double circuit; only four rows list inspected locations. | One row gives 90.4 km single-ended, 128.9 km two-ended, and 98.0 km inspected. | Derived errors are 7.6 and 30.9 km respectively. Two ends alone do not cure a wrong line model. The table does not identify this as our E5 implementation. |

## 6. Report, GIS and feedback improvements

The source recommends retaining equipment identity, fault time/phases,
protection indications, suspected cause, estimated distance, breaker/reclose
operations and system impact (p. 89). It also describes retaining actual
inspection locations with estimates and recordings (pp. 88-89), including
analysis after successful reclosure. Proposed report/schema additions should
build on `report/`, `groundtruth/` and the incident workbench.

- **Patrol interval:** map the estimated range through cumulative tower-span
  chainage to a set of towers, with terrain/access context (pp. 79-80, 90).
  Actual tower coordinates and chainage are prerequisites; synthetic tower
  schedules cannot support a patrol instruction.
- **Lightning corroboration:** retain impact ellipse/probability, stroke
  time, clock uncertainty and distance to the line (pp. 80-82). A strike may
  be missed or occur several spans from the flashover. Coincidence does not
  prove cause; do not snap the physics estimate to a lightning coordinate.
- **Vegetation-fire corroboration:** retain acquisition time, resolution
  and distance to the corridor (pp. 82-86). Sensor examples in this 2021
  document are not current specifications for a future data provider.
- **Recurring temporary faults:** retain successful-reclose incidents and
  search for recurring location intervals (pp. 88-89, 109). This can direct
  preventive inspection while preserving the distinction between suspected
  and patrol-confirmed cause.
- **Distribution of results:** Table 23 (p. 88) is an example recipient/timing
  policy, not a universal dispatch procedure. The analyser can prepare
  evidence for human decisions; it should not infer re-energisation approval
  from a calculated location.

## 7. Source cautions and apparent inconsistencies

These are observations from the supplied copy, not published CIGRE errata.

1. **Ground-current factor, Table 1 p. 10 / equation 8 p. 12:** Table 1
   prints `I_phase + k0*I0` while defining `k0=(Z0-Z1)/(3*Z1)` and I0 as
   zero-sequence current. Under the repository's conventional I0 definition,
   the loop needs `3*k0*I0`. The printed Table 1 was visually checked.
   Do not copy the inconsistent convention into the code.
2. **Complex distance, equation 7 p. 11:** the source prints magnitude bars.
   Keep the reviewed E4 real-part result and imaginary diagnostic; taking a
   magnitude conceals sign and imaginary inconsistency. This is a deliberate
   implementation distinction, not a claim of published erratum.
3. **Parameter example, Table 5 p. 25:** the first DFR table-parameter row
   lists 65.8 km estimated and 60.8 km actual but prints 6.0 km error; direct
   subtraction is 5.0 km. Treat aggregates as source-reported and recompute
   metrics before reusing tabulated observations.
4. **Current-ratio example, Table 6 p. 32:** step 2 lists 5994/1496 with ratio
   3.080; the ratio is about 4.007. Prose uses 1946 instead, consistent with
   about 3.080. Its midpoint-halving sequence is bisection-style despite the
   table's golden-search label. On p. 33, 115.35 km versus 115.9 km on a
   256.8 km line is about 0.214% of line length; the reported 0.475% instead
   corresponds to normalising by the actual fault distance. Do not mix
   those denominators in the accuracy dashboard.
5. **Mixed-line terminal, p. 49:** the prose says the junction is 19.0 miles
   from Y, while Table 8 ordering and Figure 48 place it at 19.0 from X on a
   26.3 mile line. The figures and table were visually checked. Obtain the
   underlying reference/data before using it as a numerical oracle.
6. **Algorithm completeness:** Table 2 is an overview. The E5 quadratic,
   CT saturation reconstruction, complete long-line solver and calibrated
   confidence model are not supplied as implementation recipes. Equations
   extracted as text can lose operators; inspect the PDF and re-derive any
   equation before implementation.

## 8. Concrete follow-on work and acceptance evidence

This is a proposed backlog, not a claim that these changes were implemented.

| Work item | Code area / input requirement | Evidence needed before accepting it |
|---|---|---|
| Same-stage record pairing | `workbench/`, `registry/assets.py`; electrical identity, reclose sequence, time uncertainty and filter provenance. | True pairs and deliberately wrong pairs; minutes of clock skew; multiple shots; unequal sampling; blocked inputs stay visible. |
| Section-aware scalar solver | `faultloc/`, `registry/model.py`; verified section Z and lengths. | Independent synthetic section network; uniform-line equivalence; differing R/X and Z0/Z1; faults at either side of every junction; S/R reversal. |
| Coupling applicability and model | Registry plus independent coupled-network generator; geometry/phase matrix or verified sequence coupling, circuit status, available adjacent currents. | Adjacent circuit in service, open and earthed; phase order; transposition; ground and balanced faults. A scalar-only oracle cannot validate omitted coupling. |
| Shunt/long-line treatment | `LineSection.b1/b0` plus verified units and line model. | Independent distributed/two-port model, charging-current sweeps and short-line limit. TB gives no universal 150 km switch threshold. |
| Better window selection / CT compensation study | `dsp/`; known acquisition chain and eligible unsaturated samples. | Changing fault type/resistance, near-immediate trip, late saturation, unequal end clearing, CVT transients, clipping and off-nominal frequency. TB identifies the problem but does not specify the compensation algorithm. |
| Parameter provenance and calibration | `registry/`, `ml/tier1.py`, `groundtruth/`; independently credible geometry. | Parameter versioning, identifiability and hold-out events; reject fits that merely absorb polarity/scaling/coupling errors. |
| Patrol and recurring-event view | `report/`, `workbench/`, `groundtruth/`; real tower schedule and GIS/environmental inputs. | Interval-to-tower mapping, uncertain clocks, uncertain environmental matches, late remote records and revised reports retaining provenance. |

New electrical models must be evaluated against an independent generator
that represents the new physics, followed by real records with confirmed
line data. Preserve existing synthetic acceptance results for the current
supported domain and report refusals and difficult cases, not just clean
accuracy. TB 854's 40-utility survey (pp. 95-110) is historical practice
evidence, not a current benchmark or a source of universal thresholds.

## 9. Retrieval and further source leads

The existing catalogue now exposes these paraphrased guidance entries:

```powershell
dranalyse standards --show-context --source cigre-tb854
dranalyse standards --show-context --source cigre-tb854 --topic coupling
dranalyse standards --show-context --source cigre-tb854 --topic sections
```

All entries are `catalogued`; none introduces a new compliance check.
Source metadata is in `src/dranalyser/standards/sources.yaml`, with summaries
in `src/dranalyser/standards/catalogue.yaml`.

If the installed `dranalyse` command is unavailable, run from the repository:

```powershell
$env:PYTHONPATH = 'src'
python -m dranalyser.cli standards --show-context --source cigre-tb854
```

Validation of this integration: 22 source-specific entries retrieved, all
`catalogued`, source SHA-256 matched; architecture check passed; 295 tests
passed; 10,000-case Stage-A passed with clean p95 0.4403%. The sweep located
9,929 incidents and declined 71; all-located p95 was 11.470% and CT-saturated
mean error 11.270%. These retain the distinction between the clean acceptance
criterion and difficult-case performance. No estimator, DSP or line-model
implementation was changed by this extraction.

For later implementation research, the brochure's bibliography identifies
these leads (underlying publications were not fetched or independently
reviewed in this extraction):

- [14] Novosel et al., *Unsynchronised two-terminal fault location estimation*,
  1996 (bibliography p. 112): angle-recovery formulations.
- [18] Spoor and Hinley, *Unsynchronised Fault Location on Asymmetrical Lines*,
  2015 (p. 112): asymmetry and positive/negative sequence comparison.
- [19] Tziouvaras, Roberts and Benmouyal, *New multi-ended fault location design
  for two- or three-terminal lines*, 2001 (p. 112): sequence-based location.
- [26] CIGRE TB 768, *Protection Requirements on Transient Response of Voltage
  and Current Digital Acquisition Chain*, 2019 (p. 113): acquisition-chain
  effects; not itself reviewed here.
- [32] Gong et al., *Automated Fault Location System for Nonhomogeneous
  Transmission Networks*, 2012 (p. 113): section-aware location.
