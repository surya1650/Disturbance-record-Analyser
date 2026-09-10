# Reviewed ground-loop and zone-boundary inspection

Completed 2026-09-10. Implemented locally; no commit or push. Reviewer declarations,
software validation and independently verified field inputs are separate states.

## Implemented scope

The per-record navigator now supports AG/BG/CG alongside AB/BC/CA. It uses the
existing filtered phasors and loop definition, `Vphase / (Iphase + k0*3*I0)`,
with `I0 = (IA + IB + IC)/3`. A recorded neutral channel is not substituted.
The first initialized DFT window, missing/gapped/multi-rate acquisition,
undeclared primary scaling and compensated currents below the existing
1e-6 A numerical display floor remain excluded. This floor is not relay pickup.
Display thinning and interval selection do not change analysis windows or location.

Ground display requires an exact-record input review, uniquely associated
supported settings, explicit relay identity/event-time validity declarations,
phase/scaling/bus-to-line polarity confirmation and phase-to-earth VT channels
that pass zero sequence. k0 is derived from native settings; missing native
parameters, missing required line angle, nonfinite values, direct complex-k0
entry and enabled unsupported impedance correction withhold the ground view.
The application association path still imports RIO only; accepting the neutral
model's existing native conventions does not add new vendor-file importers.

Zone boundaries additionally require positive finite CT and VT ratios referring
to the export's secondary-ohm base. The conversion is `VT_ratio / CT_ratio`,
through the existing settings model. These values only scale displayed outlines;
they do not rescale recorded samples or update the line registry. Main-1/Main-2
and terminal settings are never borrowed for this display. Phase and earth
characteristics are selected separately, without the legacy model's fallback.
Missing/invalid outlines are listed; at most 32 zones and 512 points per outline
are supported. Dashed exported boundaries do not establish active/enabled zones,
pickup, operation, timing or the relay's proprietary measurement algorithm.

## Review and provenance contract

Assignment review exposes the per-record settings association and exact byte
hashes before analysis. The optional `rx_review` assignment field is accepted
by both collector intake and browser review:

```json
{
  "record_hash": "<exact lowercase SHA-256 of CFG+DAT or CFF>",
  "settings_hash": "<exact lowercase SHA-256 of associated export bytes>",
  "channel_mapping": {},
  "reviewer": "Reviewer name or identity reference",
  "reason": "Supporting document, effective version and instrument evidence",
  "settings_identity": true,
  "effective_at_event": true,
  "phase_scaling_polarity": true,
  "zero_sequence_voltage": true,
  "ct_ratio": 1000,
  "vt_ratio": 2500
}
```

The ratios above are illustrative, not field defaults. Unknown ratios may be
omitted/null; confirmations default to false. `channel_mapping` must equal the
record's current complete reviewed mapping, including its hash and rationale,
or `{}` for automatic interpretation. The browser requires channel corrections
to be saved before the R-X review. Source/mapping mismatch, ambiguous settings
versions or incomplete prerequisites withhold affected views and retain reasons.
Ordinary phase-phase inspection remains available when its own inputs permit it.

Reviewer identity is a declaration, not an authenticated signature. Source hashes
bind the declaration to bytes; they do not prove that the supplied document was
actually effective at the event. The navigator, current-view export, all-relay
evidence and saved HTML annex expose the review, native compensation inputs,
derived k0, conversion and refusal reasons. Existing philosophy `SET-VALIDITY`
and coordination checks remain not evaluable; this display review does not modify
the existing estimator/rule path or the legacy report's analytical plots.

## Validation evidence

`tests/test_rx_review.py` and `tests/test_rx_application.py` add **29 passing
tests**. An independently specified unbalanced phase-domain network has
`Zself=10+j18` and `Zmutual=5+j6` ohm. All three ground trajectories recover
`Z1=5+j12` within 1e-7 ohm at two common phase rotations, through the waveform
DSP. An intentionally unrelated neutral channel does not change the result.
This tolerance is a project numerical regression criterion, not a TB 854 limit.

Other fixtures check individual prerequisite refusals, stale hashes/mappings,
zero compensation, missing/nonfinite native inputs, invalid geometry, VT/CT
conversion direction, phase/earth separation, per-relay isolation, escaped
review text, immutable previous reports and refusal after a second settings
version makes association ambiguous. No electrical estimator equations changed.

Headless Edge verified review submission and missing-reviewer refusal,
ground/phase selection, withheld zero-sequence evidence, per-record isolation,
mapping-change refusal/re-review across four revisions, current-view export,
desktop/mobile layout and preservation of revision 1. QA artifacts are local in
`out/qa/rx-*`. The synthetic preview is at
http://127.0.0.1:8100/#incident/b81c038543ca4aefa3ddc1fd9f707fe6, revision 4,
using isolated `out/application-rx-preview`. Earlier application roots remain intact.

The 10,000-case Stage-A regression passes: clean p95 **0.4403%**, all-located
p95 **11.470%**, 9,929 located and 71 refused; CT-saturated mean **11.270%**,
p95 **53.902%**. This confirms the existing bounded regression, not field accuracy.

Full regression: **509 passed**, one upstream Starlette TestClient deprecation
warning. Architecture guard and self-tests, focused Ruff, JavaScript syntax,
16 navigation-model and 10 native-cursor assertions passed.

## Unsupported or unvalidated

No actual field input has been verified in this milestone. There is no new
settings API/document connector, SAP/GIS join, effective-version selector,
settings authentication, relay-algorithm emulation or confirmed cross-record
fault-stage/clock association. R-X intersections are not a protection verdict.
The TB 854 matrix's ambiguous E5-root, external tower-clamping, section/coupled/
distributed-model and field-oracle gaps remain open. Passing repository tests
does not establish TB 854 validation.
