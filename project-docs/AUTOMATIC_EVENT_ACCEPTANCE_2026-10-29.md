# Automatic timings, four digital tracks and robust notation

Implemented on the authorized `codex/operator-ui-review` branch, preserving
the one-cycle viewer, original files and existing operational algorithms.

## Behavior

- Choosing an end recording selects supported pre-fault/fault/post-fault
  observation intervals automatically. The summary gives times relative to
  the recorded trigger when available, otherwise source-local milliseconds.
  Manual sample editing is optional; cursor A/B selection switches that end
  to manual. Nonempty historical manual selections remain manual.
- Sustained current RMS rise is preferred, with voltage drop as an alternative.
  Thresholds reuse the existing stage-screen relative policies, with explicit
  baseline-noise and persistence display policies. Complete actual-time
  one-cycle supports, gaps, boundary support and coverage remain in evidence.
  A supported recorded START may provide a limited observation window when
  analog baseline detection is unavailable. Trigger timestamps are not used
  as fault inception; trip commands are not breaker opening.
- Missing, too-short, ongoing or later events remain explicit. Post-fault
  stops before a supported later event. A trigger inside the initial baseline
  prevents that reference being labelled healthy pre-fault. Auto suggestions
  are recomputed server-side on save/report, ignoring forged detection evidence.
- Auto requests retain record/revision/hash and choice checks, cancellation
  and stale-response rejection. Saved inputs retain optimistic concurrency.
  A bounded four-choice cache lives on the existing two-source decode LRU.
- At least four digital channels are initially selected when available,
  changed signals first. Four compact tracks fit in the digital pane on both
  desktop and mobile, with aligned analog/digital plotting widths. Original
  activity spans and additional channel choices remain available.
- Display/report normalization reuses the parser's canonical mapping for case,
  separators, supported numeric phases and vendor-tail names. Ia/IA/I_A and
  Ua/VA/U_A share roles; actual source IDs/labels and duplicate observations
  remain separate. Residual, line-line, derived, mixed/conflicting phase and
  ambiguous automatic roles are not silently converted into phase waveforms.
  Explicit reviewed choices remain available. Operational DSP is unchanged.

## Verification

Final full pytest: **1,957 passed, 28 private-corpus skips**, one existing
Starlette deprecation warning, 132.52 seconds. Direct architecture/self-tests,
changed-Python Ruff and changed-JavaScript checks pass. Stage-A10,000: **PASS**,
clean two-ended p95 0.4361% of line; zero impossible unflagged distances.

Synthetic-generator tests cover known m, several fault types/rates/resistances.
Tests also cover steady/short/ongoing/gapped/later-event data, START polarity,
source/choice binding, forged evidence, persisted auto/manual modes, naming
conflicts and duplicate identities. Browser checks against the running app pass
both-end auto selections, all12phase values with pre/fault/post data, manual
override, auto resumption, stale recording responses, persisted reload, four
digital tracks, source notation variants and390px mobile width; no page errors.

Local private replay: DR1 selects all three intervals. DR2 retains partial event
support and withholds healthy pre-fault values because its recorded trigger lies
inside the reference baseline. These are source observations, not independent
validation of physical fault times or recorded scaling. Private originals and
QA outputs remain ignored under `out/qa/auto-event-2026-10-29`.

Automatic timing is a display screen: switching, evolving/weak-infeed events,
noise or unsuitable capture coverage may require manual refinement. No physical
classification, clock synchronization, protection setting or fault-location
eligibility is conferred. Existing reviewed line/ratio/end requirements still
govern operational distance calculations.
