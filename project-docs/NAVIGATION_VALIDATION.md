# Local event and channel navigation

2026-09-09. Implemented locally, not committed or pushed. This delivery adds
bounded interactive inspection; it does not change analysis or validate TB 854.

## Implemented behavior

The incident navigator selects one explicit relay record, one mapped analog
channel, digital points and an AB/BC/CA phase loop. Interval controls and one
local cursor drive waveform envelopes, R-X display, digital indications and
active-interval tables. Switching relays resets the interval/cursor. An interval
selection is a view selection; the numerical analysis window remains unchanged
and visible. Unknown or blocked records retain an unavailable explanation.

Each valid trigger is independently 0 ms. Missing triggers use labelled record
local-origin milliseconds, not an invented trigger. Detected inception remains
separate. No advisory correlation lag, recorder-clock comparison or E5 angle is
applied to these views. The SLD is logical bus S / breaker / line / breaker / bus R
connectivity. Both physical breaker positions remain unknown; raw selected-relay
open/pole indications are listed separately. An inactive open indication or trip
command cannot prove a closed/open breaker. Other-end state remains unknown on
the selected local timeline, including when its own record is available.

Digital active intervals come from the existing raw-point observation helper,
including unmapped labels. Initially active points preserve unknown onset;
terminal active intervals preserve the open end. Falling-edge intervals are
half-open; capture-terminal active intervals include the last sample. No state
is inferred outside capture or from unavailable points. Event buttons move the
cursor to the recorded interval start, bounded by the selected view. The digital
overview shows at most eight points; selecting a point exposes others. The table
shows at most 200 matching intervals with a visible limit notice.

Waveforms use at most 1200 extrema bins per mapped analog channel. Every bin
retains original time support, sample count and min/max; nonfinite bins remain
gaps. The cursor reports a bin range, not an interpolated sample or recomputed
RMS. Parser-normalized quantities use A/V; original declared units are retained
in the payload. At most 64 mapped analog and 64 digital channels are included;
omitted/unmapped labels remain visible. Original files are unchanged. Full-resolution
zoom retrieval and arbitrary unmapped analog plotting are not implemented.

R-X uses existing phasors and `loop_quantities`, in declared primary ohm, for
AB/BC/CA. It withholds missing scaling/phasors and multi-rate/gapped acquisition.
The mimic-filter initialization window is omitted from the display. Loop currents
at/below 1e-6 A are unavailable (project numerical display policy). Display points
are thinned to the last phasor of a bin only if the entire bin is finite; invalid
bins break the trajectory. R/X axes have equal scale. The highlight explicitly
names the last displayed point at/before the cursor, not an interpolated value.
This thinning does not preserve every R-X excursion. Ground loops, zone overlays,
zone verdicts and fault-distance inference are not provided by this view.

Digital continuity is withheld for acquisition gaps/multi-rate data or more
than 2000 active intervals per point. These are display limits, not claims that
the original record or its entire analysis is invalid. Existing quality flags,
clipping and saturation findings remain visible; no reconstruction is attempted.

## Persistence and export

Workers save display data under their revision/attempt report directory in
`navigator.json`. The result stores `navigator_path`; the browser lazily requests
`GET /api/incidents/{id}/navigator?revision={number}`. Revision is required.
Unbuilt/older revisions return 404 and a rerun explanation. The endpoint only
serves the saved artifact inside the application's runs directory. It does not
reparse original files on demand or replace earlier revision artifacts.

**Export current view** saves a standalone, script-free HTML snapshot containing
the selected local interval/cursor, source record hash, revision, SLD, plots,
digital observations and caveats. It is an additional inspection export; the
existing incident report and stored analysis revision are unchanged. Labels are
escaped in browser and export. Wide plots/tables scroll within their containers.

## Evidence and remaining scope

- **452 Python tests pass**, including 15 new cases: extrema/impulse preservation,
  nonfinite bins, invalid lengths, an independent balanced sine circuit with
  known 5+j12-ohm impedance, startup-window handling, missing scaling/channels,
  multi-rate/gap refusal, zero-current gaps, trigger/boundary behavior, clock
  independence, unchanged analysis arrays, unit labels and frozen revision/API paths.
- The Node presentation-model check passes 16 boundary/time-basis/selection
  assertions. Architecture direct/self-tests, focused Ruff and JS syntax pass.
- Stage-A **10,000 cases PASS**, clean p95 **0.4403%**, all-located p95 **11.470%**,
  9,929 located/71 refused; CT-saturated mean **11.270%**, p95 **53.902%**. This
  remains location-regression evidence, not validation of navigation or TB 854.
- Headless Edge verified single-end, two-end and four-relay incidents, record/
  channel/loop switching, valid/invalid ranges, cursor/event linkage, unknown
  trigger/unavailable record presentation, escaped labels and standalone export.
  Desktop/mobile/export screenshots were inspected; no JavaScript errors or
  mobile page overflow. The original app's two revision payloads and report
  hashes still match the preservation snapshot.

Current complete preview: http://127.0.0.1:8097/#incident/a67f761bc9234d8283472fdd00d84d27,
synthetic data, root `out/application-navigation-final`, empty isolated registry.
Earlier applications remain running with their data preserved; the intermediate
8096 preview predates the kV unit-label correction. 8097 includes that correction
and the preceding checklist's mixed-case timer fix. No earlier server was stopped.

Further work: reviewed channel mapping overrides, full-resolution zoom, verified
ground-loop/zone prerequisites, common-stage association and clock contracts,
physical contact-state interpretation and field validation. SAP/GIS/settings API
integration still needs its external identity, source and validity contracts.
The TB 854 matrix gaps remain open; passing repository tests does not close them.
