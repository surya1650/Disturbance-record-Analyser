# Guarded stage locations — 2026-09-10

Implemented an independently validated, explicitly selected stage-location path.
This extends the stage/clock milestone; TB 854 and field validation remain incomplete.

## Behavior and boundaries

The default location ensemble refuses a nonstationary analysis window when at
least two of six phase channels exhibit a supported change between settled
complex-phasor blocks. Thresholds are 20% relative change and 8% plateau scatter,
with two blocks on each side and one intervening transition block. This is a
nonstationarity screen, not proof of fault evolution. Short windows and changes
below these thresholds can be missed; absence of a detected change is not stage
certification. Original records, local timestamps, analysis windows and digital
timelines remain recorded. Location-dependent rules naturally receive a refused
location where the new gate applies.

Separate stage E5 requires matching, current source-bound stage-group reviews
at both selected terminal primaries, including explicit `location_requested: true`
at both ends. Existing identity declarations without that field authorize no
stage estimate. Corroborating relays cannot substitute for the selected primaries.
Missing line definitions, counterpart groups or current reviews withhold results.
Identity reviews remain possible for a clean original observation even if its
interior is too short for E5; location quality is checked independently.

Candidate interiors start 1.5 cycles beyond the uncertain start support and end
half a cycle before the uncertain end support. They require at least two raw
cycles and one cycle of complete DFT supports. Local clipping/saturation, missing
or nonfinite samples, nonuniform grids, blocked inputs, nonstationary phasors and
further settled-state changes withhold estimation. Relative phasor scatter is
limited to 5%. Whole-record quality flags remain visible; a clean local interior
does not erase a transition-induced whole-window saturation flag.

The stage path uses negative-sequence E5 only, up to 24 independently selected
relative-position samples per local window. It applies no clock shift or
inception alignment. It refuses weak negative sequence (below 1% of I1 or 1e-6),
series compensation, multiple distinct in-line roots, out-of-line solutions,
nonfinite diagnostics, residual above 5% or recovered phase spread above 5 degrees.
It uses declared current polarity and section-based reactance-to-km conversion.
It does not repair ratios, polarities or clocks, blend stage distances into the
incident headline, assign towers or publish a calibrated confidence interval.

The API, browser and saved incident HTML display the separate results, local
windows, review provenance and refusal reasons. The navigator's script-free
current-view export carries the stage interior evidence. Capability flags keep
the new selection control off on older backends.

## Independent oracle and validation

`tests/staged_network_oracle.py` solves 15 complex phase-domain branch unknowns:
both bus voltages, fault-node voltage and both inward line currents. Source and
line Ohm laws plus fault-node KCL are independent of generator and locator
helpers. Known sinusoidal steady states are spliced into AG, ABG, open-breaker
gap and AG reclose records. This is not an EMT, CT/CVT transient or acquisition
model and establishes no field accuracy claim.

The default generator was graded before any real-record tests after changing
the window gate. Final evidence:

- **603 pytest tests passed**; 30 new stage-location tests. One upstream
  Starlette TestClient deprecation warning. Final full suite: 49.98 seconds.
- Architecture guard run directly and its self-tests passed. Focused Ruff and
  JavaScript syntax checks passed. The final report-layout change additionally
  passed all 30 stage-location tests.
- **Stage-A 10,000 PASS**: clean n=4,283, p95 **0.4403%**; located 9,926,
  refused 74; all-located p95 11.383%; CT-saturated p95 53.902%. No impossible
  distance without a caveat. The three additional refusals are saturated seeds
  2266 (CA), 6691 (CA) and 9964 (ABC). They are single-stage generator cases;
  this screen must not label their nonstationarity as proven evolving faults.
- Independent network tests recover m=0.32/0.32/0.73, and a changed evolving
  point m=0.61, across 1000/1200/2400 Hz, fractional-cycle sample phases and a
  1,418-second header offset. Tests verify branch equations, complete local DFT
  support, unchanged waveforms/windows, review/staleness/selection refusal,
  weak sequence, ambiguous roots, nonfinite diagnostics and no outside-line clamp.
- Intake/worker/report integration verifies both-end selection, withdrawal,
  escaped reviewer text and byte-identical historical reports.
- Headless Edge desktop/mobile checks passed for real review controls, separate
  32/32/73 km results, saved HTML and script-free navigator export; no page errors.
  Screenshots were inspected and provenance wrapping corrected.
- All ten preceding application roots, revision rows and saved report/navigator
  artifacts were fingerprint-verified unchanged.

## Runtime and next work

Current complete synthetic preview: http://127.0.0.1:8102, isolated root
`out/application-stage-location-preview`, registry `out/stage-location-registry`,
one worker. Incident `3833fb155e04488da2c1764a828035b2` retains its original
revision and later reviewed revisions. QA evidence is local under `out/qa/`:
`stage-location-preview-results.json`, screenshots, export and preservation
snapshot. The newly created 8102 process was restarted to load final guards;
none of the earlier application processes was stopped.

Next work requires broader physical transient and adversarial stage validation,
including CT/CVT transients, weak infeed, short or unchanged-pattern evolution,
and clock-source uncertainty evidence before any UTC alignment. Stage E5 does
not close existing full-estimator/tower uncertainty, TB 854 or field gaps.
Real substation records, settings exports, event PDFs, application databases and
generated QA artifacts remain local and excluded from the public repository.
