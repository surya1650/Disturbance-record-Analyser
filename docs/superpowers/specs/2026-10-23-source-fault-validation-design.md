# Weak infeed, source asymmetry and fault connections

The user authorizes autonomous continuation without design questions or new
field data. Implement inline with Superpowers and one fresh final reviewer.

Create a separate independent phase-nodal oracle so existing oracles, source
hashes and historical artifacts remain untouched. Solve explicit passive
phase-matrix branches, two Thevenin sources and physical fault connections;
never import locator/registry/synthetic-generator math into the oracle.
Expose source impedance scale, source voltage angle/magnitude/unbalance, and
passive phase-asymmetric source impedances independently. Source asymmetry is
at terminal boundaries; coupled/asymmetric line models remain unsupported.

Connections: AG/BG/CG (one resistor to earth), AB/BC/CA (one resistor between
phases), ABG/BCG/CAG (two contact legs R/2 to a common node and R to earth),
ABC/ABCG (three R contact legs to a floating/grounded common node; earth R
for ABCG). Document this circuit-specific resistance convention. NONE is the
healthy network. KCL, source Ohm laws, contact/earth laws, physical reversal,
balanced-sequence symmetry and the prior SLG limit must independently verify
the oracle. Reject invalid geometry, source and fault specifications explicitly.

Publish a deterministic seeded phasor sweep with 2 line geometries, chainages
10/40/75 km, 11 connections, R=1/50 ohms, physical reversal, 8 source profiles,
3 references (aligned, unsynchronised 0/1.1 radians) and ideal/.1%/1% complex
noise: 38,016 raw numerical windows of 8 pairs. Profiles: baseline; weak S/R
source impedance scales 100 and 10,000; remote voltage magnitude .85 and angle
-.35 rad; negative/zero sequence source EMF; passive phase-asymmetric source Z.
Do not use truth to select a root. Report located/refused/error/denominators
by scenario, source profile, fault type, reference and measured infeed ratio,
with worst witnesses, KCL residuals, descriptive spread coverage and hashes.
Separate raw solver outcomes from measured negative-sequence strength screening
and from balanced connection controls. Balanced controls never count as a
new operational location capability, even if the low-level solver returns one.
Noise is relative to the stronger terminal V2/I2 with a positive-sequence
floor, so absent negative sequence does not imply zero measurement noise.

Add actual-DSP sinusoidal state-splice cases for additional unbalanced faults,
weak/unequal/asymmetric sources and balanced controls. These are not EMT or
instrument-transient evidence. Main/stage gates must not be relaxed to improve
coverage. Reproduce any newly found numerical/guard bug RED before a minimal
fix; otherwise production behavior stays unchanged. Guarded workflow results
must be distinguished from low-level phasor results.

Python >=3.10, no new dependencies or operational line enablement. Preserve
Dash findings, workbook, field records, app database and preview processes.
Full tests, architecture direct/self-tests, focused Ruff, reproducible strict
JSON/exclusive output, one read-only whole-branch review and primary-checkout
tests precede the authorized analyser commit/push. Remain pre-pilot: no field
accuracy, calibrated confidence, exhaustive source envelope or new physics claim.
