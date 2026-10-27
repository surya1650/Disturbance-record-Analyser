# Conditional E5/section error-feasible sets —2026-10-27

Offline research now propagates explicit terminal voltage/current error circles
through uniform or piecewise series E5 constraints. It returns every retained
necessary distance component, never a selected point. Production legacy DSP,
location consumers, operational gates and clock eligibility are unchanged.

## Derivation and scope
Both terminal currents enter the line, matching estimators.py and sections.py.
For cumulative section impedance P(m), local common-fault phasors satisfy
|Vs-P Is|=|Vr-(T-P) Ir|, even with an unknown terminal phase offset. Declared
complex input error circles inflate both fault-voltage magnitudes. Current-error
contributions use triangle sums of section magnitudes, deliberately conservative
when section impedance angles differ. Each paired support contributes a necessary
inequality; their intersection does NOT establish a shared phase across supports.

Normalized section subdivision discards only boxes ruled out by a Lipschitz bound
plus the explicit guard256*epsilon*(sections+1). Endpoint/junction boxes survive;
pending boxes survive resource exhaustion. Unknown caps/provenance, invalid model
geometry and unrepresentable numerical scales withhold. Weak negative-sequence
signals with overlapping error circles provide no distance information.

These are numerical outer sets, not formally rounded interval certificates or
calibrated confidence. Passive uncoupled exact Z2=Z1 sections, no charging/taps/
internal sources and genuinely covering total error caps are assumptions. Caller
provenance strings are explicitly unauthenticated declarations. The utility does
not infer CT/gain/alias/DSP/model/clock truth or authenticate completed analyses.

## Frozen independent validation
Code/protocol freeze514f55a72c99bdbcc0c114912ce6e03dfadfe114 preceded outcomes.
[Evidence](validation/E5_ERROR_SETS_2026-10-27.json) retains all556 cases, actual
phasors/truth/caps, every failure denominator,8 UTF8/LF source hashes and runtime.
The manifest includes full_record_signals.py (its RATIOS dependency omission in
an older selected manifest is not repeated; historical manifests remain intact).
The separately preserved [reviewed evidence](validation/E5_ERROR_SETS_2026-10-27_REVIEWED.json)
binds the numerical-domain/exit-status fixes atab09e032be36f2c5736295b74c7909dc613f08af.
All556 original/reviewed numerical rows are identical; all16 frozen bindings
verify against their recorded Git revisions, and the8 reviewed hashes match
current sources. The original evidence is not rebound to newer files.

| Cohort | Cases | Result |
|---|---:|---|
| New direct circuit grid |480|280 single components;200 whole-line sets|
| Independent phase nodal network |60|60 single components; physical truth retained|
| Deliberately invalid coherent caps |16|12 inconsistent/excluded truth;4 single components retaining truth|

All540 within-cap cases retain physical truth; zero numerical failures. All556
rows evaluated,9884 boxes total, at most47 per case. Of the within-cap cases,
340 have one component and200 span the whole line. Widest single within-cap
component0.0062890625pu; median width across all540 is0.00228515625pu. These are
conditional set widths, not empirical error bars or chosen locations.

The direct grid uses two new seeds91631/92743, endpoint/interior positions, two
section models, four source-current profiles, two rotations and exact/bounded/
wide cap families. All160 wide-cap rows and all40 both-weak bounded-cap rows
remain uninformative. Both-weak exact caps can mathematically constrain distance;
this presumes perfectly known zero total measurement error and is not an
operational weak-infeed availability claim. Nodal60 checks use three SLG phases,
two source orders, physical junctions/interiors and rotations; they are phasor
networks, not parsed-record/DSP or EMT tests. The direct oracle uses explicit
common-fault circuit sums and imports no candidate helpers.

Violating supplied caps can exclude the actual fault:12/16 coherent controls do
so. Four retained-truth controls do not rehabilitate false bounds. A nonempty
necessary set cannot establish valid provenance. This blocks field adoption even
though conditional numerical coverage passes. No new accepted field cases.

## Verification and review
Baseline1431pass/28 missing-corpus skips/1existing upstream warning243.66s.
TDD48 core failures before implementation,7 runner/oracle failures before their
implementation;55 focused pass. Analytic tests preserve both distinct roots.4/.6,
intersect every support, cover local rotations/section junctions/endpoints, weak
inputs, resource exhaustion, scales1e-120..1e120, and explicit refusal controls.
Architecture and changed-file Ruff pass. Release1486pass/28missing-corpus skips/
1existing warning1734.50s. One fresh whole-branch astra-high review independently
reran55 focused tests and verified all8 source hashes. It found three Important
issues, no Critical/Minor findings and no declined judgments:

- Partial subnormal rounding could exclude exact physical truth. With minsubnormal
  t, Vs=Vr=t, Is=t, Ir=2t, Z=.6+1j and zero caps, true m=2/3 was excluded by
  an erroneous[.9658203125,1] set. The utility now withholds every nonzero
  subnormal input/product component, including propagation from normal inputs.
- Huge Python integers and finite-component complex values whose magnitude
  overflows could escape as exceptions. Numeric predicates now withhold safely.
- Failed truth-coverage/protocol/source gates could publish a zero exit code
  without exception rows. Publication now exits2 for any failed overall gate,
  preserving its evidence file.

Single TDD fix pass:14 new failures observed RED, plus1 already-green success
control;70 focused GREEN2.67s. The subnormal physical counterexample is preserved
in regression, not erased from the record. Numeric refusal deliberately costs
extreme-scale/component-disparity availability. Full fix/primary verification
is1501pass/28missing-corpus skips/1existing warning204.01s for the review-fix
worktree. No unresolved Important findings; no deferred Minor. Primary
integration1529pass/no skips/1existing upstream warning182.29s. No repeat review.

Combined primary log: out/qa/e5-combined-primary-full.txt. The read-only delivery
helper verifies16 frozen bindings,8 current bindings, identical556-case rows,
unchanged existing production sources/historical evidence and both protected
Dash hashes. Research is integrated under the standing commit/push authorization;
the final Git/remote head records delivery. All22 ignored QA/ledger files were
copied and hash-verified under out/qa/e5-error-sets-2026-10-27/ before the native
worktree archive was verified. Its merged branch was removed after archival.

## Decisions and remaining evidence
Triangle radius sums trade tightness for conservative geometry; extreme
unrepresentable and subnormal scales withhold rather than invent data; caps/model provenance
remain caller assumptions. These decisions can reduce availability and false
declarations can exclude truth. They confer no operational authority.

Next supported software research is an independently derived optional shared
terminal-phase necessary condition across explicitly paired supports, with a new
disjoint freeze and unknown pairing/phase-stability assumptions withheld. It
must retain all necessary distance/phase boxes on budget exhaustion and keep
historical grids untouched. Actual field accuracy, total phasor-error caps, CT/
gain/alias provenance, physical line models and operational enablement still
require external evidence. Scalar/DSP adoption remains FAILED/HELD.
