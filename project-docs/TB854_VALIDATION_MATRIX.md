# TB 854 validation matrix

Updated 2026-09-11. The current follow-up results and remaining field blockers are in
[TB854_FIELD_VALIDATION_2026-09-11.md](TB854_FIELD_VALIDATION_2026-09-11.md).
The detailed baseline tables below retain the 2026-09-08 assessment except where updated. **Implemented does not mean validated, and passing the
repository suite does not establish TB 854 validation.** This is a traceable,
bounded assessment of the existing analyser, not certification or reproduction
of the brochure's method inventory. The initial matrix-only milestone changed no production behavior. The 2026-09-11
follow-up adds estimator, model-domain and external-output refusals; line constants
and original records remain unchanged.

Source: CIGRE WG B5.52, *Analysis and comparison of fault location systems in
AC power networks*, TB 854, December 2021, local `E:/cigre/854.pdf` (137 pages).
SHA-256: `0406508feb3154dff584a5818823ea6be01b0dd1e82f523d0d7ac2d8797a7886`.
Page locators below are printed pages (also one-based PDF positions from p. 3).
The source extraction and its cautions are in [CIGRE_TB854_METHODS.md](CIGRE_TB854_METHODS.md).
Pages 10 and 11 were visually rechecked for this change using existing local
renders. Other source locators inherit that earlier extraction; no published
field example was newly reproduced. The PDF and relay recordings remain local.

## Reading the evidence

- **Implemented / bounded validation:** a code path exists and the stated
  fixture verifies specific behavior under its assumptions. This is not broad
  electrical or field accuracy validation.
- **Diagnostic evidence / open gap:** a test can demonstrate a limitation,
  including a misleadingly small residual. Its pass is evidence of the limit,
  not evidence that the method safely handles that case.
- **Unsupported:** the required electrical model or integration is absent.
  Some unsupported inputs are explicitly refused; others cannot be detected
  from current registry/record data. Do not assume universal automatic refusal.
- **Retrieval/integration only:** source indexing, application operation and
  report construction do not independently validate electrical equations.

Shared assumptions for scalar electrical rows: one two-terminal, transposed,
uncoupled, series-only line; known impedances and units; bus-to-line currents at
both ends; correct phase/scaling/polarity; compatible settled fault stages.
`I0=(IA+IB+IC)/3`; residual current is `3*I0`. `m` is the positive-sequence
series-reactance fraction from S. On a uniform line it also equals length
fraction. A section conversion alone does not extend the electrical model.
E5 needs no GPS; E4 additionally needs a common phasor reference.

All tolerances below are **project-derived regression criteria**, never CIGRE
accuracy requirements. Algebraic fixture tolerances of 1e-12 to 1e-10 pu check
floating-point consistency on small, deterministic systems, not measurement
accuracy. The 0.5% clean p95 threshold comes from `PROJECT_CONTEXT.md` section 13.

## Capability and source matrix

Join the IDs to the evidence/acceptance table below. Together the two tables
provide source, problem, assumptions, implementation, oracle, tests, remaining
work, expected behavior, criterion and status for each topic. Paths are under
`src/dranalyser/` unless prefixed with `tests/`.

| ID / topic | TB locator and problem | Assumptions / implementation path | Evidence status |
|---|---|---|---|
| V01 Ground loops | pp. 9-10, eqs. 3-4, Table 1: residual compensation convention | Scalar ground loop; `registry/model.py:k0_from_impedances`, `faultloc/estimators.py:loop_quantities`; retain `3*k0*I0` despite printed inconsistency | Implemented; independent phase-network fixture validated for AG/BG/CG |
| V02 E1/E2 | p. 10, Table 2: load and resistance affect single-ended location | E1 reactance, E2 compensated loop denominator and usable superimposed current; homogeneous source-angle assumptions for resistance cancellation | Implemented; bolted-loop accuracy and missing-current refusal validated; resistive evidence remains synthetic |
| V03 E3 | p. 10, Table 2: partial homogeneity correction | `e3_modified_takagi`, known source Z0, ground faults only; iterative beta sign is a project derivation | Implemented; existing synthetic improvement and new zero-sequence refusal tests; no independent resistive field validation |
| V04 E4 | pp. 11-12, eqs. 5-8: equal fault-point voltage | `e4_synchronised`; returns Re(q), signed Im(q) diagnostic and abs(Im(q)) residual; not eq. 7's printed magnitude. Eq. 8's reduced measurement variant is not separately implemented | Implemented variant; signed/imaginary behavior and passive scalar circuit validated |
| V05 E5 invariance/reversal | pp. 12-13, section 2.1.2.2: unknown remote angle | `e5_unsynchronised`; exact quadratic is project-derived; arbitrary common rotation of remote V/I, unchanged fault stage | Implemented; independent passive sequence fixture and existing waveform/synthetic tests |
| V06 E5 branches/identifiability | pp. 12-13 discuss unsynchronised methods; branch policy is project-specific | `e5_roots`, angle stability, in-line preference; distinguish variable competing branches from identical repeated samples | Stable competing branch and numerical-tie refusal validated; noisy near-tie discrimination remains uncalibrated |
| V07 Weak/absent sequence | p. 12: balanced faults need an alternative to negative sequence | E1-E5 current gates; `ensemble._two_ended` uses superimposed positive sequence for ABC/ABCG | Exact absent-current refusal validated; weak noisy sequence identifiability not established |
| V08 Clock and same-stage gates | p. 12; pp. 26-27, Fig. 12: synchronization cannot repair incompatible circuit stages | `ensemble._two_ended`, `dsp/detect.py:overlap_window`; E4 requires both clock flags; E5 still needs same stage | Clock Boolean gate validated; evolving-stage alignment only partially supported |
| V09 Impossible distance refusal | p. 11 error sources; numerical bounds are project policy | `ensemble.locate` final guard outside [-0.5,1.5]; after actual weighting/reconciliation | Repaired test proves refusal, NaN km/interval km, no towers; mutation detected |
| V10 External indication / orientation | pp. 11-12, eqs. 5-6; report safeguards are project policy | `locate`: R-only `m_S=1-m_R`; all m outside [0,1] are non-location external indications, beyond [-0.5,1.5] remain impossible | Orientation validated; external km, intervals and towers suppressed in outputs and rule inputs; bypass detected |
| V11 Parameters and shared bias | pp. 24-28, Table 5: erroneous line constants | `registry/model.py`, `ml/tier1.py`; measured versus provisional provenance matters; small residual cannot prove correct Z1 | Conversion/fitting implemented; independent E4 parameter-bias counterexample validated; field constants unverified |
| V12 Mixed sections | pp. 47-51, eq. 24, Tables 8-9 | `Line.m_to_km` walks section X; estimators still use summed Z; differing R/X, Z0/Z1 and boundaries need electrical propagation | Independent section nodal oracle and proportional-section limit tested; nonproportional sections explicitly refused; general section solver **unsupported** |
| V13 Parallel/asymmetric coupling | pp. 53-56, eqs. 25-27, Table 11; Annex F p. 124 | Requires phase/self/mutual matrices and adjacent circuit state; scalar sequence E5 does not establish immunity | Declared double circuits explicitly refused; coupled-network solver and six-conductor oracle **unsupported** |
| V14 Charging / long lines | p. 11; pp. 47-48: capacitance invalidates constant-current propagation | `LineSection.b1/b0` fields exist; scalar estimators omit shunt terms | Declared shunt parameters explicitly refused; pi-oracle counterexample tested; distributed solve **unsupported**, no validated length threshold |
| V15 CT/CVT/acquisition/windows | p. 11; p. 24 Table 4; pp. 26-27 Fig. 12; p. 105 | `dsp/core.py`, `detect.py`, `pipeline.py`, ensemble weighting; saturation detection, CVT window exclusion, sample-rate handling | Detection and synthetic stresses implemented/tested; saturation reconstruction and vendor filter compensation **unsupported** |
| V16 Series compensation | pp. 51-53, Fig. 50, Table 10 | `Line.series_compensated`, `ensemble.locate`; requires truthful registry flag | Electrical solve **unsupported**; explicit suppression implemented/tested |
| V17 Pairing and field validation | pp. 28-31: collection, unreliable clocks and reclose | `workbench/`, `registry/assets.py`, `application/`; explicit identities, incident revisions, late records; no order-based terminal inference | Intake/assignment integration implemented/tested; autonomous cross-delivery pairing unsupported; confirmed-distance two-ended field validation absent |
| V18 Confidence and accuracy metrics | p. 6 eqs. 1-2; p. 111; no TB interval algorithm | `ensemble.locate` spread/disagreement interval; `stagea.py`; `groundtruth/` metrics | Metrics and intervals implemented; empirical held-out interval coverage **unvalidated** |
| V19 Other impedance methods | p. 10 Table 2 (Eriksson); pp. 13-15, 31-33 Table 6; Annex A pp. 117-118 | Separate Eriksson, current-ratio network matching, distributed monitor voltage-drop need their own models/data | These methods **unsupported**; catalogue descriptions only |
| V20 Excluded/other topology | pp. 15-23, 56-78, 91-93 | Travelling wave excluded by binding section 2.2; three-/multi-terminal, FCI/PMU and distribution extensions outside current two-terminal scope | **Unsupported/excluded**, no new GPS dependency or TW backlog |
| V21 Patrol/GIS/environment | pp. 79-86, Figs. 84-92; p. 90 | `Line.towers_near`, report SVG; real tower chainage prerequisite. Lightning/fire matches need timestamps/uncertainty | Basic tower mapping implemented; GIS/lightning/fire integrations **unsupported**; synthetic tower tests do not authorize patrol |
| V22 Operations and feedback | pp. 87-90, Tables 23-24; p. 109 recurring temporary faults | `report/`, `groundtruth/`, `application/`; one incident, multiple immutable report revisions; confirmed truth distinct from estimate | Storage/report/intake integration tested; capture remains separate from app, recurrent-event field benefit unvalidated |
| V23 Model-based learning | pp. 93-94, Fig. 94: model/data combination | `ml/tier1.py`, `tier2.py`, `tier3.py`; parameter estimation, fleet pooling, capped correction, physics first | Implemented project methods with synthetic tests; not a reproduction of TB learning method; field benefit unvalidated |
| V24 Catalogue / source cautions | All 22 C854 chunks; Table 1 p. 10, eq. 7 p. 11, Table 5 p. 25, Table 6 pp. 32-33, Figs. 45/48 pp. 49-50 | `standards/sources.yaml`, `catalogue.yaml`, `catalogue.py`, audit/CLI; source cautions are observations, not CIGRE errata | Retrieval/integration validated; **all 22 remain catalogued**, no automatic TB compliance checks |

## Original 2026-09-08 oracles, tests and acceptance

Historical table: the current V06-V18 changes are recorded in the linked 2026-09-11
validation report. Claims below about unrefused ties and clamped external fields
are retained as the defects that motivated the now-tested corrections.

Test paths use these abbreviations: **N** =
[`tests/test_tb854_validation.py`](../tests/test_tb854_validation.py), **M** =
[`tests/test_maths.py`](../tests/test_maths.py), **P** =
[`tests/test_pipeline.py`](../tests/test_pipeline.py), **A** =
[`tests/test_stagea.py`](../tests/test_stagea.py), **C** =
[`tests/test_tb854_catalogue.py`](../tests/test_tb854_catalogue.py).
Function names below omit `test_` for readability. The retained generator
`synth/generator.py` is independent of estimator code but shares the supported
scalar physics. It cannot validate omitted section/coupled/distributed physics.

| ID | Independent oracle/data and existing/new tests | Expected behavior / project acceptance criterion | Missing validation / next evidence |
|---|---|---|---|
| V01 | N `ground_loop_matches_phase_impedance_network`: direct 3x3 phase impedance drops, specified 0.375 position; M k0 conversion/round-trip | E1/E2 recover 0.375 within 1e-12; omitting residual factor causes >0.05 pu error in this fixture (sensitivity control only) | Independently measured Z0, vendor residual convention and field phase mapping |
| V02 | Same independent bolted phase fixture; M `e1_shows_the_reactance_effect_and_e2_corrects_it`, `e2_denominator_uses_the_compensated_loop_current`; N current-refusal tests | Bolted result exact to tolerance; existing resistive synthetic case E2 improves on E1; absent required current returns not-ok with reason | Independent resistive/load/source-angle sweep; no universal E2 resistance cancellation claim |
| V03 | M `e3_beta_sign_reduces_the_error_rather_than_doubling_it` uses existing source network; N absent-current test | Existing E3 error less than E1 for specified synthetic case; no I0 means explicit refusal | Independent heterogeneous-source resistive oracle, iterative convergence limits and field source impedances |
| V04 | N `e4_preserves_signed_distance_and_imaginary_diagnostic`; `two_ended_passive_network_rotation_and_terminal_reversal`; M aligned sweep | Inject q=-0.3 +/- j0.4: m=-0.3, signed diagnostic +/-0.4, residual=0.4 within 1e-12; preserve sign instead of magnitude 0.5 | Validated clock-error/ratio-error operating envelope; imaginary diagnostic is not guaranteed defect identification |
| V05 | N independent passive negative-sequence branch network: zero source EMFs, prescribed fault-node voltage, branch Ohm's law; M synthetic fault-type/angle sweep | m={0.17,0.5,0.83}, rotations {-pi,-1.13,0,1.13,pi}; E4/E5 recover within 1e-10, terminal reversal gives 1-m, recovered angle checked circularly | Real pair with verified constants/confirmed location; evolving signals and weak-sequence noise |
| V06 | N `e5_selects_stable_angle_when_two_in_line_branches_compete`; `e5_root_separation_exposes_but_does_not_resolve_ambiguity`. Both use magnitude constraints, not estimator root helpers | Varying fixture: candidates .4 and .6 both in line, wrong angle varies >0.5 rad; E5 selects the high root .6 within 1e-12. Bypassing stability selects .4 and fails the test. Constant fixture: root separation 2/15, tiny residual/stability do **not** identify a unique answer | Refuse or explicitly surface statistically indistinguishable candidates; design policy before claiming ambiguity-safe location. Tie test checks diagnostic evidence only, not refusal |
| V07 | N `estimators_refuse_absent_required_current`; M ABC tests and P waveform classification | All five estimators not-ok, NaN m, nonempty reason for their exact zero-current fixture; ABC path retains superimposed positive sequence | Near-zero noisy content, normalized conditioning threshold, truncated/mismatched windows, inconsistent no-real-root cases |
| V08 | N `e4_requires_both_clock_quality_flags` exercises all four combinations; P `e4_is_gated_off_without_clock_quality`; existing Stage-A short-window stress | Only both true enables E4. Duplicate analysed data in new flag test is a gate fixture, never an electrical end-pair oracle | Independent evolving fault, reclose shot, per-pole opening and filter delay fixtures; verify same stage and full-window eligibility at both ends |
| V09 | A repaired `ensemble_refuses_to_report_a_distance_far_outside_the_line` injects E1 before real reconciliation; local process-only bypass experiment | m={-5.7,-.5001,1.5001,6.7}: positive weight reaches guard, mode none/not-ok, original diagnostic m retained, both km and interval km NaN, towers empty, no likely tower, explicit caveat. All four must fail when guard bypassed | Controlled test proves final result guard, not all invalid-input detection or HTML treatment of raw estimate diagnostics |
| V10 | N `external_indication_is_distinct_from_impossible_distance`, `remote_only_estimate_is_mapped_to_s_without_argument_order_inference` | -0.1/1.1 retain signed m, external terminal and no-patrol warning; R-local .2 maps to S .8, 80/20 km on 100 km fixture | External results still have clamped km/tower fields. Suppression/presentation policy needs repair and report regression before calling external output patrol-safe |
| V11 | N `wrong_line_impedance_can_bias_e4_with_zero_residual`: equal infeed, bolted fault at .3, physical voltages held fixed while entered Z scaled .8/1.2; existing M conversions and `tests/test_ml.py` Tier-1 recovery | E4 reports .25 or 1/3 within 1e-12 with residual <1e-12, proving >.03 pu hidden bias in these fixtures; do not equate small residual with accuracy | Z0/source/ratio perturbations, joint identifiability, held-out field calibration; measured parameter versions, units and uncertainty |
| V12 | M `m_to_km_walks_reactance_not_length`: analytical cumulative X conversion only | 25% X = 50 km, 50% X = 66.6667 km in specified two-section example; no electrical accuracy acceptance from conversion | Independently assembled phase nodal section oracle, varying R/X and Z0/Z1, faults either side of boundary, reversal and uniform limit. Freeze numerical/measurement criteria when model domain is defined |
| V13 | No coupled oracle or coupled fault-location test | No validated coupled-distance claim; scalar tests cannot establish it | Independent six-conductor phase network with adjacent circuit energized/open/earthed, cross-sequence terms, verified corridor geometry; acceptance not yet defined |
| V14 | No shunt/distributed oracle; registry fields are data only | No validated long-line accuracy claim or universal 150 km threshold | Independent two-port/distributed oracle, charging sweeps, unit checks and short-line limit; acceptance not yet defined |
| V15 | Existing P inception/frequency tests, Stage-A CT/DC/CVT/rate/window perturbations; `tests/test_real_records.py` zero-sequence VT detection/refusal | Preserve current clean Stage-A acceptance and visible refusals/caveats; report difficult-case errors separately | Validated saturation reconstruction, acquisition-chain transfer functions, transient/evolving network oracle; current generator's detector tests are not reconstruction proof |
| V16 | P `series_compensated_line_is_refused_not_guessed` | Not-ok and explicit series-compensation caveat when registry flag is true | Registry truth and richer report refusal verification; no capacitor solver proposed here |
| V17 | P late-end upgrade; `tests/test_application.py:manual_upload_review_report_late_remote_and_restart`; real parser/scaling/clock tests | Explicit identity, late report revision, blocked records visible; synthetic two-ended integration functions | DHONE Main-1/Main-2 are same-terminal records. Other candidate opposite-end assets mentioned in older notes are not confirmed-distance validation. Need verified S/R evidence, same stage, Z/length/towers and patrol truth |
| V18 | A sweep; `tests/test_groundtruth.py:error_is_signed_and_reported_as_a_fraction_of_the_line`, `accuracy_reports_the_tail_not_only_the_mean`; V11 bias counterexample | Existing Stage-A: clean p95 <0.5% line length and zero unflagged impossible m; report located/refused counts, all-located and difficult-case tails | Held-out interval coverage and bias with parameter/measurement uncertainty; confidence level not calibrated. Do not infer coverage from spread or correlated methods |
| V19 | No implementation or independent oracle for any of the three methods; Table 6 has current-ratio/denominator cautions | No method-specific performance claim; no acceptance threshold assigned | Obtain original derivations, topology, voltage/current data and ground truth before selecting a method; reported TB examples are not reusable COMTRADE benchmarks |
| V20 | Architecture guard enforces no travelling-wave module; no multi-terminal network oracle | Preserve exclusions and two-terminal domain | No TW implementation planned; any topology expansion needs separate scope/model/data and independent acceptance |
| V21 | P `tower_band_is_reported`; `tests/test_report.py` SVG/report tests, synthetic tower schedule | Current mapping displays computed range in supported in-line fixture; no environmental evidence changes physics distance | Verified surveyed tower schedule, GIS uncertainty and association tests for lightning/fire; no snapping to environmental coordinates |
| V22 | `tests/test_groundtruth.py` pending/confirmation/correction tests; `tests/test_application.py` late record/revision tests; `tests/test_report.py:ground_truth_capture_block_is_present_with_a_url` | Confirmation append/history semantics and one-incident revisions work; a rendered URL is not proof of capture integration | App-integrated truth capture, held-out patrol outcomes, recurring successful-reclose incidents; no automatic operational authorization |
| V23 | `tests/test_ml.py` Tier-1 recovery/refusal, Tier-2 100-event gate/cap/leave-line-out, Tier-3 second-opinion tests; synthetic labels | Preserve physics precedence, fleet rather than per-relay correction, raw output and capped residuals | Ground-truth event diversity and identifiability; fitted k0 may absorb omitted physics; no field improvement claim |
| V24 | C manifest/unique locators/status, source filtering, CLI rendering and record/settings audit non-promotion tests; prior source fingerprint; pp. 10-11 visual recheck | Exactly 22 unique chunk IDs/locators, expected source hash (case-insensitive hex), all catalogued; active retrieval excludes them; audit emits no TB checks | Source-to-algorithm evidence review remains separate. No TB example accuracy reproduced; do not copy inconsistent printed factors, magnitudes or error denominators |

## Historical 2026-09-08 findings that motivated the corrections

The repaired refusal test supplies controlled estimates **before** `_weigh` and
the final guard. It no longer edits an unused result after `locate` returns.
Synthetic towers make the empty-tower assertion meaningful. A separate Python
process compiled only `locate` with its final guard bypassed; all four cases
failed on `mode == 'none'`. The original function was restored in `finally`.
No source file or running application was mutated. Reproduction helper:
[`tests/tb854_guard_mutation.py`](../tests/tb854_guard_mutation.py), invoked with
`distance` or `branch` in a separate process. It exits 0 when the selected
pytest tests detect the bypass by failing; it is not part of normal collection.

The old M test named as stable-root selection was renamed to describe what it
actually verifies: a constant recovered angle at midpoint on repeated phasors.
The new competing-branch fixture checks that **both** candidate magnitudes fit
and that the wrong candidate's angle varies before asserting the chosen root.
Its correct root is the high candidate, so always selecting the first/low
candidate cannot accidentally pass. A process-local bypass of angle stability
produced the wrong .4 result instead of .6 and failed the test as expected.

For constant observations VS=VR=.6, IS=2, IR=1, Z=1, both m=.2 and m=1/3
satisfy the magnitude constraint with a constant recovered angle. These are
algebraic identifiability fixtures, not claims of a passive power-system fault.
The current E5 exposes root separation but returns an estimate; it does not
explicitly warn/refuse a tie. This tests an input-validation limit, not unique
fault-location accuracy. Weak/noisy and no-real-root policies also remain open.

External estimates are distinct from impossible estimates. The current code
warns against patrol for an external m but still returns clamped line-end km
and towers. The new test verifies the warning and signed m only. Neither this
test nor Stage-A's zero-unflagged-impossible counter validates those tower
fields as an external location. This matrix keeps that gap visible instead
of calling all refusal/reporting behavior validated.

## Historical next-work recommendation (2026-09-08)

The V06/V10 numerical/refusal follow-ups and V12 independent section oracle below
are now implemented; general section solving and the listed field evidence remain
outstanding. Refer to the 2026-09-11 report for current next work.

First address V06 ambiguity and V10 external-output policy as bounded safety
follow-ups with controlled counterexamples and report checks. This validation
change establishes their evidence without silently choosing a new electrical
or uncertainty policy. Verified field constants and a confirmed-location pair
remain the highest-value external inputs.

For the **next independent modelling task**, build a series-only section
network oracle before a production section solver (V12). It is the smallest
step that directly tests the current gap between an implemented section
registry and summed-impedance electrical solving. Assemble the phase nodal
network independently of the estimator, freeze physical faults just before,
at and after section junctions, vary R/X and Z0/Z1, check terminal reversal,
KCL/KVL residuals and uniform-line equivalence. Include a deliberately wrong
summed-model result so an oracle omitting section physics cannot pass unnoticed.
Keep CT reconstruction, six-conductor coupling and shunt/distributed solvers
as separate tasks; this oracle must not be used to validate those domains.

## Verification record, 2026-09-08

Commands used `.venv/Scripts/python.exe` with `OPENBLAS_NUM_THREADS=1` and
`PYTHONPATH=src` for CLI commands. Missing dev extras were installed into the
existing app environment with `pip install -e '.[app,dev]'`; runtime numerical
and application dependencies were already satisfied. No application restart,
reset, stash, commit or push was performed. Architecture budgets unchanged.

| Check | Result / what it establishes |
|---|---|
| Corrected refusal test, normal guard | 4 passed; final reconciliation refusal only |
| Process-local guard bypass | 4 expected failures; original function restored; mutation detected |
| Full `pytest -q` | 359 passed, one upstream Starlette TestClient deprecation warning; final run 74.22 s |
| New electrical/diagnostic and catalogue modules | 36 electrical/diagnostic cases plus 4 retrieval/integration cases; all pass in final suite |
| Process-local E5 stability bypass | 1 expected failure (wrong .4 root versus .6); original function restored; mutation detected |
| `python scripts/check_architecture.py --self-test` | PASS |
| `python scripts/check_architecture.py` (direct, no pipe) | PASS |
| Ruff on new validation tests and mutation helper | PASS |
| `stage-a --cases 10000` | PASS; clean n=4,283, p95=0.4403%; located 9,929, unlocated 71 (0.71%); zero unflagged impossible m |
| All located / difficult cases | All-located mean=2.273%, p90=3.182%, p95=11.470%, max=126.942%; CT-saturated n=1,819, mean=11.270%, p95=53.902%; no difficult-case accuracy claim |
| `git diff --check` | PASS |
| Local app health and `/` | HTTP 200 for `/api/health` (status ok, queue 0) and `/` after full tests; existing process preserved |

These checks establish the bounded behavior described above. They do not
establish independent TB field-example reproduction, omitted-physics accuracy,
calibrated confidence coverage or validated operational fault distance.

## 2026-09-10 operational-display evidence, separate from TB validation

The V01 scalar loop convention is also exercised by the independently specified
phase-domain waveform network in `tests/test_rx_review.py` (AG/BG/CG recover
5+j12 ohm). Per-record input reviews and phase/earth exported-boundary conversion
are implemented and tested in the navigator; see
[RX_INPUT_VALIDATION.md](RX_INPUT_VALIDATION.md). These are additional bounded
software fixtures. They do not verify the supplied field k0, CT/VT wiring,
settings effective version, relay zone algorithm or the brochure's full domain.
No matrix gap or catalogued TB entry is promoted by the 509 passing repository tests.
