# Numerical robustness and independent validation

The user requested remaining software/numerical work without new field data,
then explicitly delegated sequencing and opted out of further design questions.
This design records the implementer's choices, not field approval.

## Intent and approaches

Make the existing scalar solver's structural failures explicit, quantify its
remaining noise/parameter sensitivity independently, and study the next section
model without enabling it in operational reports. Keep supported clean behavior
and all refusal/domain gates observable.

Considered: (1) robustness first, then an independent section feasibility study;
(2) immediately replace the location path with a general section solver;
(3) develop six-conductor/distributed/acquisition models together. Choose (1):
it directly checks the shipped path and keeps distinct physical assumptions
separate. (2) requires solving cross-section ambiguity and integration policy;
(3) is several independent research projects and cannot share an acceptance claim.

## Deliverables

1. Real-root numerical contract: normalize finite quadratic coefficients before
   discriminant arithmetic, preserve cancellation-safe roots and existing
   near-linear policy, return no real roots for a negative discriminant, and
   refuse nonfinite or identically-zero polynomials. A vertex is not a root.
   E5 rejects windows containing an inconsistent or degenerate magnitude
   constraint rather than silently omitting those observations. Undefined
   recovered fault-point angles cannot authorize a distance. Record structural
   failure diagnostics; main location must not silently fall back to single-end
   estimates after those failures unless independently usable aligned E4 exists.
2. Reproducible numerical envelope: an independent passive negative-sequence
   branch network with zero source EMFs and a prescribed nonzero fault-node
   voltage, independently checked source/line Ohm laws and KCL where applicable.
   Sweep location, source-strength ratio, remote rotation, deterministic complex
   measurement noise and common parameter bias. Report every planned/located/
   refused case, error tails and diagnostic interval containment, separately by
   scenario. No synthetic-noise threshold is claimed calibrated or field safe.
   Publish the reproducible command and finite JSON summary; raw generated output
   stays under ignored `out/`. This fixture does not model a full phase fault or
   transducer transfer function.
3. Independent mixed-section study: evaluate an explicitly synchronised,
   series-only negative-sequence section-boundary search against the existing
   independent phase nodal network, including AG/BG/CG, section junctions,
   physical reversal, high fault resistance, a proportional/uniform limit and
   deliberately wrong summed-line comparison. Keep the study in validation;
   main/stage production section refusals remain. An aligned phasor feasibility
   result does not authorize unsynchronised E5, coupling, charging or field use.

## Constraints and acceptance

- Python >=3.10; existing NumPy/SciPy only; no new runtime dependency.
- No ML in location, travelling waves, GPS requirement for E5, or field values.
- Preserve source records, active app roots, Dash files and historical reports.
- Tests precede production changes and must fail for the intended defect first.
- Regression fixtures check supported exact networks and refusal output; noise
  sweeps are descriptive and cannot redefine the existing Stage-A criterion.
- Run architecture direct/self-tests, focused Ruff, full pytest, 10,000-case
  Stage-A after estimator changes and a fresh whole-branch independent review.
- Synthetic scenarios, bounds and exceptions remain explicitly documented;
  no TB 854 certification or calibrated-confidence claim.

## Execution

Inline implementation with one fresh whole-branch reviewer. Use the managed
worktree on `codex/numerical-validation`; original main and preview stay intact
until integration. User's existing request to update the analyser repo supplies
the goal; record commit/publication state accurately at completion.
