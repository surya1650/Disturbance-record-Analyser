# Guarded section-aware negative-sequence location

The user authorizes autonomous continuation, no design questions and no new field
data. Implement inline under Superpowers with one independent final review.

## Scope and electrical contract

Add an explicitly enabled series-section model, `section_solver_enabled: true`
(strict boolean, default false). It accepts reviewed, contiguous, finite passive
sections with positive X1, unique section identifiers, no shunts, no declared
coupling and no series compensation. It does not clear `model_review_required`.
No operational registry file is enabled by this work.

Both currents enter the line from their buses. For each candidate section,
propagate the S voltage through the preceding sections and the R voltage through
the following sections. Solve continuity inside that section using its own Z1.
Return global physical chainage and cumulative positive-sequence reactance
fraction, never the local section fraction as the incident distance.

Aligned mode requires established common-reference measurements. Unsynchronised
mode equates the two recovered fault-voltage magnitudes and recovers the relative
angle. Retain all in-line roots across all sections; distinct locations cause
refusal. Deduplicate only adjacent descriptions of the same physical junction.
Undefined fault-voltage angle, nonfinite/short/mismatched windows, an unusable
sample, recovered-angle standard deviation above 5 degrees or distance spread
above 0.02 of total reactance cause refusal. Aligned complex-continuity mismatch
is bounded at 0.01 of terminal/line-drop voltage scale. These engineering screens
are not field-calibrated accuracy or confidence limits.

## Integration

Dispatch enabled models through a separate two-ended negative-sequence path in
main and reviewed-stage location. Require usable sequence strength at both ends,
explicit current polarity, stationary overlapping local windows and no CT
saturation for the incident path. Never blend with scalar single-ended methods
or fall back to them. Balanced faults, missing ends and cross-country evidence
withhold. Main output contains descriptive sample spread, no automatic tower
assignment; stage output retains existing review/window gates. Other models use
the unchanged scalar path.

## Independent evidence

Use the existing phase nodal admittance oracle (no locator imports) at physical
fault nodes. Test mixed and proportional sections, fault phases/resistances,
junctions, reversal, remote rotation, scale, ambiguous roots, corrupted samples,
weak sequence and model gates. A reproducible seeded sweep reports planned,
located and refused counts separately, errors only for located cases, and
measurement/model perturbations without claiming field acceptance. Keep oracle
code under tests; the offline script may consume it, production may not.

## Completion and limits

Python >=3.10, no new dependencies. Full suite, architecture direct/self-test,
focused Ruff, existing 10,000-case Stage-A and fresh whole-branch review precede
integration. Preserve QA, report all refusals and deferred limitations, update
standards matrix/status, commit and push the analyser. Keep Dash, field records,
workbook, active app database and preview processes unchanged. Project remains
pre-pilot with zero accepted field cases; coupling, charging, balanced section
faults, instrument reconstruction and calibrated uncertainty remain pending.
