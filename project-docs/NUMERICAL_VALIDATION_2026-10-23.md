# Numerical robustness and bounded mixed-section study

Continuation from `56e2674`. The user delegated sequencing and execution without
further design questions. Superpowers planning, test-first fixes, full-suite
verification and one independent whole-branch review govern this milestone.
This extends numerical evidence; field acceptance remains unavailable.

## Shipped corrections

`stable_quadratic` now normalizes finite coefficients before discriminant
arithmetic. Roots of `(m-1)(m-2)` survive common scales from 1e-300 to 1e300.
E5 normalizes its complex constraint terms before squaring them. A negative
discriminant returns no real roots: a quadratic vertex is not a solution.
Nonfinite and identically-zero constraints remain unusable.

E5 refuses an entire paired window if even one observation has no real
magnitude solution, instead of hiding that observation with a median. The
recovered phase is withheld when fault-point voltage is at cancellation scale
(sqrt(machine epsilon) times the contributing voltage scale, with the existing
absolute floor). Undefined phase, invalid samples and nonfinite inputs now
propagate to incident refusal. A separately usable clock-authorized E4 may
still supply a result; a single-ended fallback cannot conceal these failures.
E4 also refuses nonfinite input rather than returning an `ok` NaN estimate.
Its exception to a structural E5 refusal requires an in-line position and
enough weight to qualify for actual two-ended reconciliation. A low residual
or positive weight alone cannot admit an impossible/external E4 and then blend
it with single-ended estimates into a plausible protected-line distance.

The original corpus-free baseline exposed a Windows duplicate-upload race:
an existence check followed by replacement could overwrite a published hash
blob while a reader had it open. A deterministic stale-check/open-reader
test reproduced WinError 5. Complete staged files are now atomically linked
within the same filesystem; an existing hash is not replaced. Other I/O errors
remain errors. The app root must support hard links (tested on local Windows
NTFS); unsupported filesystem deployment needs a separately validated strategy.

## Independent scalar envelope

`validation/sequence_envelope.py` specifies a passive negative-sequence network
from branch Ohm laws, with zero source EMFs and prescribed nonzero fault-node
voltage. Tests independently verify source and line drops. This is not a full
phase fault, CT/CVT transfer function, EMT simulation or recorded-field replay.

Seed 854, 20 repetitions per grid/scenario and 24 phasor pairs per window:
locations .05/.25/.5/.75/.95; remote source-impedance multipliers .1/1/10/1000;
remote rotations -1.13/0/pi. Complex Gaussian measurement-noise RMS is relative
to the stronger terminal V or I, so weak-current noise is not scaled away.
The ratio is a negative-sequence source-impedance multiplier, not a complete
positive-sequence system-strength or weak-infeed model.

| Synthetic scenario | Planned | Located | Refused | Located p95 error (% line length) | Maximum |
|---|---:|---:|---:|---:|---:|
| Ideal | 1,200 | 1,200 | 0 | 3.33e-14 | 8.88e-14 |
| 0.1% phasor noise | 1,200 | 1,200 | 0 | 0.0385 | 0.1010 |
| 1% phasor noise | 1,200 | 1,200 | 0 | 0.3950 | 0.8844 |
| 5% phasor noise | 1,200 | 1,199 | 1 | 1.9605 | 4.9270 |
| Common line impedance +20% | 1,200 | 1,200 | 0 | 13.0246 | 15.7973 |
| Remote current ratio +10% | 1,200 | 1,200 | 0 | 2.8191 | 2.9807 |

All 7,200 planned cases remain in the denominator: 7,199 located, one refused.
The mix is an artificial experiment grid, not an estimate of fleet frequency.
All biased cases still returned a location. Small solver residuals do not
establish correct parameters or scaling. Diagnostic intervals contained truth
in none of the two biased groups. Noise-only containment in this experiment
does not calibrate confidence on correlated waveform samples or field data.
The interval comparison permits 32 machine eps in position solely to avoid
counting floating-point roundoff as an ideal zero-width-interval miss; no
production interval or field-truth tolerance was changed.

The [machine-readable aggregate](validation/NUMERICAL_ENVELOPE_2026-10-23.json)
includes every scenario/ratio denominator, refusal reasons, limits and source
hashes after UTF-8/LF normalization. Detailed cases remain ignored under
`out/qa/sequence-envelope-v2.json`. The earlier unsuffixed report is historical:
its interval containment omitted the disclosed roundoff allowance.

## Mixed sections: feasibility only

`validation/section_study.py:aligned_section_candidates` propagates voltages
through each healthy prefix/suffix and evaluates a section-local candidate.
It retains distinct fitting sections as ambiguous and merges only duplicate
representations of the same physical junction. Its default relative voltage
mismatch bound is 1e-8, a project numerical tolerance, not measurement uncertainty.

The independent phase nodal oracle checks AG/BG/CG, 1/50 ohm fault resistance,
positions 1/39.9/40/40.1/75/99 km, junction ownership, physical terminal reversal,
and proportional-section limits. Mixed-case chainages recover within 1e-7 km
in these exact fixtures. That tolerance checks arithmetic, not physical accuracy.
An intentionally loose algebraic case retains two distinct section candidates.
Coupling, compensation, shunts, malformed sections, missing/cancelling sequence
and source candidates needing model review are withheld.

This study requires already aligned negative-sequence phasors and Z2=Z1 on
transposed, uncoupled, series-only sections. It is never imported by production
main/stage location. Their nonproportional-section refusal remains. No general
unsynchronised section solver, collector, new clock authorization or operational
distance/tower assignment was enabled.

## Stage-A regression and verification

10,000-case DSP sweep PASS: **9,242 located, 758 refused**. Clean total 4,283:
4,258 located, 25 refused; clean located p95 **0.4361%**, unchanged. Previously
9,707 cases located; the additional 465 abstentions must accompany any comparison.
All-located p95 is **6.677%**, maximum **91.361%**. Saturated-CT located cases:
1,203, p95 **39.805%**, compared with 1,667 and 35.2249% previously. The saturation
tail remains unsuitable as a general accuracy claim; fewer estimates are not
proof of better field performance. Zero unflagged impossible outputs were found.

Full worktree suite: **823 passed, 28 corpus-dependent skips**, one upstream
Starlette/httpx deprecation warning, 139.39 seconds. Final whole-branch review
and primary-checkout verification are recorded after completion below and in
the newest handoff entry. Focused section/domain tests
passed 80 cases; envelope/section tests passed 82; architecture direct/self-tests
and focused Ruff passed. Worktree field-corpus tests skip because real records
were not copied into the isolated checkout. The primary checkout's original
baseline passed all 744 tests before this work.

Reproduce from the analyser checkout with its environment:

```powershell
$env:PYTHONPATH='src;.'
$env:OPENBLAS_NUM_THREADS='1'
python scripts/check_architecture.py --self-test
python scripts/check_architecture.py
python -m pytest -q
python scripts/numerical_envelope.py --seed 854 --repetitions 20 --out out/qa/NEW-envelope.json
python -m dranalyser.cli stage-a --cases 10000 --workers 2 --csv out/qa/NEW-stage-a.csv
```

The numerical-envelope command refuses output replacement. Synthetic-only
source and aggregate results may be committed; field recordings, workbooks,
snapshots, candidate registries, app databases and detailed runtime output stay
local. No old preview process was restarted, so existing processes need a normal
restart to load updated numerical code. Dash findings remain unchanged locally.

## Remaining work

General production section solving still needs unsynchronised identifiability,
sample/window/stage integration and its own acceptance policy. Six-conductor
coupling, charging/distributed propagation, CT/CVT reconstruction, statistically
calibrated noisy-root discrimination and confidence coverage remain open. The
present phasor experiment does not close those domains. Verified field identity,
event-effective parameters/wiring, surveyed towers and independent held-out
patrol truth remain prerequisites for field acceptance. No TB catalogue entry
is promoted to certification or automatic compliance by these results.

## Independent review and decisions

The first reviewer invocation returned no findings because that model's usage
was unavailable. A fresh independent reviewer on an available model reviewed
the whole branch and passed 104 focused tests. It reported no Critical or Minor
items and one Important issue: an impossible E4 could bypass structural E5
refusal and blend into an in-line single-ended distance/tower. Real-DSP tests
reproduced the defect for E4 positions -2, 1.2 and 6 pu before the fix. They now
withhold distance, intervals and towers; valid aligned E4 remains supported.
The focused numerical/Stage-A/TB set passed 76 tests after this correction.

Decisions carried from the execution/review ledger:

- A handwritten scaling fixture originally encoded a double root rather than
  the stated two roots. It was corrected by independent polynomial expansion;
  incorrect test data must not dictate production behavior. Otherwise the
  scaling-validation claim itself would be false.
- The existing intake publication race was fixed within this milestone, using
  atomic hard links on the user's C:/E: NTFS filesystems. Portability to filesystems
  without hard links remains a deployment constraint; they fail explicitly and
  need a separately validated strategy.
- Broader unsynchronised sections, coupling, charging and acquisition models
  remain deferred. Their scope is not established by the aligned study, so
  production gates stay in place to prevent overgeneralization.
- Field accuracy and confidence remain outside the available evidence; the
  synthetic study cannot authorize operational acceptance or interval calibration.
- Extreme mixed-exponent/subnormal arithmetic is outside the common-scaling
  envelope tested here. The reviewer reported no material location-scale effect
  in considered examples; this is not full floating-point-domain validation.

No deferred Minor findings were reported. The fix is verified by regression
tests and a full suite, with no second review substituted for those checks.
