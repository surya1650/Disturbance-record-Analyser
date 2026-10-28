# Recording-first viewer layout

The waveform viewer now places channel controls above the recording. Every analog
channel remains displayed, independently of the selected digital channels. Analog
lanes have a minimum readable height rather than sharing a clipped, resizable pane.
Digital lanes sit below analog lanes. Channels with observed state transitions are
selected first; constant signals can be added from the top controls. Digital-only
pagination never hides analog channels. Exact cursor requests remain batched to the
existing eight-channel API limit.

The right panel contains cursor values and separate voltage/current vector diagrams.
Waveform and fitted-RMS trend modes share the viewport and cursors. RMS trend points
come from existing model-consistent four-cycle fits; unavailable windows break the
line. No new phasor estimator, numerical policy, or fault-location behavior is enabled.
Vector placeholders remain visible and explain missing channels, refused windows,
zero magnitudes, or invalid references instead of drawing invented vectors.

Time ticks show actual source-sample times relative to the CFG-recorded trigger,
alongside relay-local timestamps. Cursor timestamps retain microsecond display
precision. Zero is the recorder trigger, not inferred fault inception. Horizontal
positions remain source sample positions, including when the timestamps are
nonuniform; the labels do not claim a uniform acquisition grid or synchronized clocks.
Zoom, pan, full-recording reset, keyboard/numeric cursors, and a viewport slider support
the full recording. The slider becomes available after zooming into a shorter span.

Digital summaries show recorded high-state spans and observed durations. Boundaries
that precede the recording, extend beyond it, or meet unknown samples remain marked
unknown. State 1 does not establish physical assertion polarity. Details are bounded
to 32 spans per channel / 512 per recording, with explicit omitted counts.

## Validation

- Architecture guard, changed Python Ruff checks, JavaScript syntax, and diff checks pass.
- Full suite: 1,793 passed, 28 absent-private-corpus skips, one upstream warning.
- Focused timing, digital-state, and JavaScript tests cover nonuniform times, midnight
  rollover, unknown gaps, bounded metadata, RMS gaps, changed-channel defaults, and
  multi-batch cursors with more than eight displayed channels.
- Stage-A: 10,000 cases PASS; clean located p95 0.4361%; 9,242 located / 758 refused.
- Chromium replay of the user-supplied DR1/DR2 files verifies all eight analog lanes,
  six/three changed digital signals respectively, top-control addition of an unchanged
  digital signal without hiding analogs, waveform/RMS modes, cursor movement and
  off-screen following, record switching, and mobile overflow. No JavaScript errors.
- Logs and screenshots are local under ignored `out/qa/viewer-redesign`. Private
  recordings and screenshots are not committed.

Requested reference products are Wavewin and GE Vernova S1 Agile. Vendor documentation
could not be reviewed in this environment: the Wavewin vendor HTTPS request was denied
by the configured network policy. This change implements the supplied screenshot and
requested interactions; it makes no verified feature-parity claim for either product.

Restart the Python server to load the added inspection metadata, then reload the
browser for the JavaScript/CSS changes. Changes in this workspace have not been
pushed to GitHub or deployed to a public host.
