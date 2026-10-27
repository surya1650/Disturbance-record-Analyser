# Conditional E5/section error-feasible sets

Autonomous inline continuation under the user's standing authorization. This is
an offline mathematical experiment, never a location recommendation or policy.

## Model and signs
Current E4/E5 estimators and sections.py define BOTH currents into the line.
For cumulative series impedance P(m), total T, and a common fault voltage F,
Vs=F+P Is and Vr=exp(-j delta)[F+(T-P) Ir_common]. Thus, after local terminal
rotation, |Vs-P Is|=|Vr-(T-P) Ir|. Existing sections.py subtracts section prefixes
and suffixes in precisely this convention. Assume exact passive uncoupled series
sections, Z2=Z1, no charging, taps, mutual coupling or internal sources. Section
endpoints are physical chainage fractions; section impedance is its TOTAL ohms.
Model provenance is a caller declaration, not independently authenticated evidence.

Each terminal explicitly supplies measured complex voltage/current, nonnegative
absolute error-circle radii and nonblank provenance. Unknown radii/provenance
withhold. Error circles must cover ALL claimed components, including gain, CT,
alias, timing and DSP bias if those are claimed. We do not infer or calibrate caps.
The pure interface is BoundedTerminal(voltage,current,voltage_radius,current_radius,
provenance), PairedObservation(s,r), SeriesSection(end,impedance), and
e5_error_feasible(observations,*,sections,model_provenance,resolution=1/1024,
max_boxes=100000). Real options reject booleans. At most256 supports,64 sections,
200000 boxes; resolution in[1e-6,1]. Invalid shapes/types/nonfinite values and
unrepresentable propagated scales withhold with finite JSON and no intervals.

## Necessary outer set
For each support g(m)=||Vs-P Is|-|Vr-(T-P) Ir||-
[rVs+rVr+|P|rIs+|T-P|rIr]. A feasible physical point has g<=0. For a section
parameter u, a Lipschitz bound is |Zsection|(|Is|+|Ir|+rIs+rIr).
Implement using separately summed normalized section drops. Because all sections
lie in the first quadrant, sum |Zj|*rI is a CONSERVATIVE replacement for
|sum Zj|*rI. This deliberately widens sets across changing impedance angles;
it never shrinks the necessary set. No common phase across supports is enforced.
Discard a box only when SOME support has g(mid)>L*halfwidth+guard. Retain boxes
at requested physical width, or earlier if ALL supports have g(mid)+L*halfwidth
<=guard. Merge touching boxes. On exhaustion retain ALL pending boxes and report
resource_limited, never silently drop unresolved regions. Guard is explicitly
256*machine_epsilon*(number_sections+1), in each support's normalized voltage
units. These are numerical outer sets, NOT formal floating intervals/confidence.

Finite JSON includes intervals_pu, total_width_pu, boxes_evaluated, status/reason,
guard, research_only=true, authorizes_location=false. Status is withheld,
inconsistent (empty conditional necessary set), uninformative (whole[0,1]),
ambiguous (multiple components), outer_set (one component), or resource_limited.
No point/median, clock authority, field acceptance or production integration.
Weak measurements with overlapping circles should remain uninformative.

## Independent pre-frozen experiment
Before outcomes freeze a direct common-fault-voltage oracle independent of the
candidate, using lengths and exact circuit sums, and an existing phase nodal
oracle as a separate check. Do not import candidate helpers into the oracle.
Direct grid: seeds91631(development),92743(validation); physical m values
[0,.137,.37,.731,1]; models uniform and three sections ending[.23,.61,1] with
total section impedances[1+8j,7+12j,2+19j]; uniform total10+39j.
Profiles baseline,weakS,weakR,bothWeak; independent rotations[0,1.713]; cap
families exact,bounded,wide; three supports per case, deterministic disk errors
within declared caps. 2*5*2*4*2*3=480 direct cases. Deliberately violated-cap
coherent gain/polarity controls:16 cases, separate from successful coverage.
Nodal grid:2 source orders*3 phases*5 locations[.01,.23,.42,.61,.99]*2 rotations
=60 cases on the same section geometry, positive resistance7.3ohm. Total556.
Also test analytic two roots .4/.6, impossible data, endpoints/junctions, all-zero,
resource exhaustion, scale invariance and provenance refusals. Preserve every
failure/denominator and every violated-cap counterexample, no tuning after runs.

## Alternatives and limits
Chosen conservative subdivision handles sections/roots/weakness uniformly.
Quadratic roots with inflated bars miss root topology; full interval arithmetic
would require a different verified numeric foundation. This study cannot establish
model correctness, true field caps, cross-support synchronisation, or safe adoption.
No production source consumers, legacy DSP defaults, operational gates, historical
manifests, Dash, captures, workbook, DB or preview processes may change.
