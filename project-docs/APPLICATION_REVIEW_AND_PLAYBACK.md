# Application review and event playback

Reviewed on 28 October 2026. This is a hardened local engineering workbench,
not a certification of fault-location accuracy or unrestricted production scale.

## Delivered workflow

Open **Playback**, choose the original sending/receiving recordings, and select
the actual trip command, breaker open/closed contacts and available AR signals.
Explicitly select active state 0 or 1, confirm the meanings/polarity and provide
reviewer/evidence. Unrecorded signals can remain unknown. Save and build, then
use Play/Pause, Reset, speed, Repeat, the full-span slider or event stepping.

The animation connects:

- the named sending/receiving line diagram and contact indications;
- full line length and the stored operational fault estimate, when eligible,
  with distances from both ends and the report's method/basis;
- both ends' R–X trajectories, loop selection and moving observation markers;
- voltage/current waveform overviews and reviewed digital active spans;
- trip-to-open timing, opening/reclose sequences, AR close commands, lockout and
  retrip observations, including source sample brackets;
- a downloadable JSON evidence snapshot and a link back through the main
  Waveforms & report menu for exact samples and all analog channels.

A fault location stays fixed through playback. It is a stored estimate for the
event; the animation does not move a physical fault along the line or recompute
location from cursor position. Missing/withheld locations produce no marker.
The overview shows up to six analog signals per capture; the main viewer retains
all analog channels. Unselected opposite ends remain explicitly unknown.

## What the review found and changed

| Finding | Resolution |
| --- | --- |
| Separate cursors, R–X views and event evidence had no common playback controller | Added a revision/source-bound, bounded playback model and browser clock. |
| Opposite ends could be confused with successive recordings | Explicit S/R selection, common-event review, distinct recordings, existing end-label/operational-assignment checks and conservative same-declared-relay refusal. DR1 and DR2 remain same-relay captures. |
| Inactive contacts could be misread as opposite positions | Open requires an asserted reviewed open indication; closed requires an asserted reviewed closed indication. Neither active means unknown; both active means conflict. A trip/AR command never substitutes for contact evidence. |
| Initial-active, missing and gapped signals could give misleading times | Initial assertions have unknown onset. Gaps/boundaries terminate support, and only adjacent observed transitions produce timed edges. |
| Trigger zeros could imply clock synchronization | Default mode uses independent relay-trigger references and labels this. Shared display offsets require reviewer/evidence; they never authorize synchronized estimators or cross-end durations. |
| All native waveform channels fetched at once | Limited concurrent native requests to four, retaining existing exact-cursor and abort/error-isolation behavior. |
| Old incident results could race a navigation change | Added cancellation and stale-response guards around incident loading and playback disposal. Playback pauses on menu changes and hidden tabs. |
| Reusing playback after saving different source/diagram choices could retain old R–X | A save invalidates playback and requires rebuilding against its new input version. |
| Very large revision integers could reach SQLite unchecked | Added a central database revision bound; invalid values return input errors. |
| Invalid manual zone boundaries could be saved | Reject degenerate/self-intersecting polygons, repeated intermediate vertices, duplicate names and out-of-range/overflowing values. An optional closing vertex is retained as supplied. |

## R–X availability and interpretation

Playback first uses the frozen operational navigator for its selected recording
when available. This supports phase loops and ground loops under the existing
per-record settings review, native compensation, scaling and zero-sequence VT
requirements. It also uses the eligible exported zone outlines; one
characteristic kind is never substituted for another.

Otherwise it uses conditional source-window fits with that recording/revision's
saved source choices. These retain the four-cycle support and stationarity
requirements. Source ground loops remain withheld. Manual phase boundaries need
matching reviewed primary scaling and any settings-ohm conversion ratios.
The R–X basis and reasons stay visible, and export includes source choices,
input version and source hashes. Point markers refer to display/model centres;
no interpolated instantaneous impedance is claimed. Isolated valid points remain
visible, and missing points break trajectories.
The build reads saved source choices and diagram versions in one database read
snapshot, so an input edit in another tab cannot mix a newly loaded R–X basis
with the build's earlier declared line model. Rebuild to adopt later choices.

Short/transient source windows can still lack valid fits, particularly in a
blocked field recording. Animation does not solve that numerical limitation.
An independently validated short-support/transient method remains future work.
Operational gates, estimators and source-file bytes are unchanged.

## Timing contracts

The first-sequence summary and up to 64 opening/reclose sequences retain their
local event times. Digital timelines/events retain other supported observations.
The exact observed sample time accompanies each adjacent-sample bracket.
Duration ranges are differences of those brackets, not confidence intervals;
clock, wiring and mechanical uncertainties are not bounded by them.
Fault reference is an explicit operator input in milliseconds from that relay's
trigger, or the existing operational inception when available. A trigger itself
is not automatically fault inception. Positions are reviewed contact
indications, not independent mechanical verification or an AR success verdict.

Offsets have the explicit convention:

```text
display_ms = (source_local_s - recorded_trigger_offset_s) × 1000 + declared_offset_ms
```

Independent mode requires zero offsets. Reviewed-offset mode is a display
declaration only. Both modes keep intra-record timing calculations unchanged.

## Resource and deployment limits

Playback uses at most two original captures and seven distinct reviewed digital
roles per capture. Each selected signal is bounded to 2,048 state runs/edges;
excess complexity makes that signal unavailable instead of silently truncating
continuous state. Source decoding retains the existing sample/channel/cell/file
budgets. R–X paths use up to 1,200 display points. Rendering is throttled to about
15 updates/second, updates existing paths/cursors and makes no per-frame sample
requests. Saved playback is loaded lazily when its menu opens. Configuration
saves are versioned, source-bound and do not inherit into a new incident revision.

This remains a local SQLite/filesystem application with bounded caches and
diagnostic workers. A fleet service still requires:

1. Authenticated deployment, permissions and tenant/site isolation. The local
   write token and origin/host checks are not a multi-user login system. Keep
   Codespaces ports private for real recordings.
2. Asset/line/substation identifiers, versioned settings and bulk-import review;
   these can drive substation-filtered line dropdowns.
3. A production database/object store and distributed job execution, plus
   quotas, monitoring, backup/restore and operational ownership.
4. Representative concurrent-user, queue, large-corpus and recovery/load tests.
   This review did not qualify thousands of simultaneous users or certify
   cross-relay field accuracy.

## Verification

- Full regression: **1,860 passed, 28 private-corpus skips**, one existing
  Starlette/httpx warning. Architecture, Ruff and browser-script syntax pass.
- Stage-A: 10,000 synthetic incidents, PASS; clean located p95 0.4361%.
  Existing refusal counts and difficult-case tails remain explicit.
- New tests cover source/revision binding, stale saves, malformed/huge inputs,
  duplicate and same-relay end misuse, contacts, unknowns, gaps, active-low
  states, adjacent-sample timing, invalid geometry and bounded concurrency.
  A 200,000-sample constant indication compresses to one run without an
  invented opening time.
- Chromium desktop/mobile: phase source fallback and operational phase/ground
  R–X, reviewed public synthetic RIO settings, named ends, location/line length,
  contact movements, AR/lockout, playback controls, offsets, persistence,
  export, pause on navigation, zero per-frame requests and original-file
  preservation. No browser errors in the completed end-to-end checks.
- Private supplied DR2: playback used its original nonuniform source times;
  missing contact/location inputs stayed unknown. Presenting DR1/DR2 as
  opposite ends was rejected, and the source-file inventory remained unchanged.

Synthetic and private QA artifacts remain under ignored `out/qa/playback`.
No real recordings, settings or field screenshots are committed.
