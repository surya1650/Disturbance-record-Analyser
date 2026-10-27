# Conservative scalar negative-sequence observability study

The corrected-DSP adoption trial newly located a detected-saturatedABC input
with6.21% error. Existing scalar location downweights saturation rather than
refusing; section location already rejects saturation/weakI2. This milestone
studies a conservative scalar negative-sequence screen separately, without
changing production defaults, thresholds, clocks or operational enablement.

Create pure `scalar_observability(terminals, *, fault)` accepting the existing
TerminalInput map and measured consensus fault. Return finite JSON with
candidate_pass/withheld, reasons and per-terminal diagnostics, always
authorizes_location=false. This is a necessary-condition candidate, not proof
of measurement accuracy or location validity. Require exactlyS/R and a known
unbalanced fault from AG/BG/CG/AB/BC/CA/ABG/BCG/CAG. ABC/ABCG/NONE refuse because
this study does not validate a positive-sequence substitute. No truth fault
label may enter candidate decisions.

For EACH terminal refuse blocked/multi-rate acquisition, nonboolean invalid
saturation state, detected saturation, clipping, polarity other than integer
-1/+1 (bool invalid), nonfinite/nonpositive rate/frequency, frequency at/above
Nyquist, nonfinite/non-increasing/nonuniform time (rtol.01,atol1e-7), or missing
six primary phase andI1/I2/V2 streams. Require a usable full/half selected window,
at least two complete support indices, finite values across EVERY selected
support and consistent stream lengths. Refuse detected transitions. Use the
existing section policy floor max(.01*median(abs(I1)),1e-6 primary A); every
selected I2 must meet it. Record minI2, referenceI1, floor and supports. A missing
or nonfinite value cannot disappear through median/downsampling. No gain,
polarity, alias, clock, frequency-error or total-noise guarantee follows.

Review clarification: clipping assessment must be an explicit list/tuple, not
None/False/0 or another false-like object. Phasor time must be real, one-dimensional,
finite and exactly match record time before support selection; n_window and
valid_from must be finite integers in their valid ranges. Completed-analysis
provenance is assumed: this utility does not independently recompute phasors from
raw ADC samples or authenticate a caller's cached analysis.

Freeze disjoint uniform physical-network120km geometry (.055+.33j and.22+.91j
ohm/km), development37km/Rf3 and validation83km/Rf7. Eleven fault connections,
two profiles per split and fourteen scenarios yield616 paired incidents.
Development:47.5Hz,fs3000/1800,pre.155/.207,duration.34,rotation.79,
DC.8,tau.063,burden.8,bias.2,seed6854,baseline/weak_R_100.
Validation:51.5Hz,fs3600/2200,pre.175/.223,duration.37,rotation1.41,
DC1.1,tau.079,burden1.1,bias-.25,seed7854,baseline/weak_S_10000.
Scenarios clean,white_small(.0005 familyRMS),colored_small(.002 familyRMS),
ct_single,ct_all,ct_noise(.002 familyRMS),clip_i,clip_v,gain_i(1.15),gain_v(1.12),
polarity(S/IA),alias(S/IA,fs-f,.12 familyRMS),gap,clock_skew(1418s).

Independent phase nodal oracle supplies physical phasors; splice sinusoids and
toy nonlinear CT onto secondary samples, serialize20bit integer ASCII with the
existing independent writer and public parser. No production synth/locator
creates truth. No editing historical grids or their defaults. The candidate
uses actual legacy analyse outputs and measured scalar consensus; unguarded
legacy locate is retained beside the candidate overlay. The overlay only
suppresses, never creates or alters a location. Truth errors use independent
quadrature separately and never become candidate inputs.

Evidence must retain all616 records, numerical failures, candidate passes,
withheld reasons, legacy/overlay locations and errors, harmful CT/measurement
passes and balanced-control outcomes, clock eligibility and source hashes.
Bounded-study adoption requires0numerical failures, harmfulCT coverage in both
splits,0harmful measurement passes,0overlay errors>1km,0balanced locations and
at least one clean unbalanced pass in each split. Fail honestly if any condition
fails; do not tune. CLI finite/exclusive JSON, exit2 on numerical failures.
Production adoption remains HELD regardless of candidate outcome pending fuller
validation and defensible measurement assumptions. The source-asymmetry/field
and formal interval guarantees remain excluded. Preserve Dash, inputs and DB.
