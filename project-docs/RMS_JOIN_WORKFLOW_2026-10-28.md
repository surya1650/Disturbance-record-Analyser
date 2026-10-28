# RMS viewer, same-relay joining, and operational blocks

## Viewer measurements

Waveforms now have labeled per-channel amplitude axes. RMS plots include zero on the
vertical axis, avoiding exaggerated variations from min/max-only autoscaling. Cursor
cards on each graph show exact instantaneous samples and trailing one-cycle **sample
RMS** in the recording's source units. A sticky overview permits dragging a cursor
through the complete recording, including when the main plots are zoomed. Graph
dragging, keyboard movement, and zoomed panning share one viewport.

Sample RMS is the equal-weight root mean square of recorded samples in
`(t - 1/declared_nominal_frequency, t]`. It includes DC and harmonics and is not the
fundamental phasor magnitude or a continuous-time integral for irregular samples.
Missing samples, incomplete leading windows, large time gaps, and source boundaries
withhold the affected RMS values. A stable two-stack scaled-square aggregate avoids
overflow and cancellation after large-current clearing. The existing two-source cache
retains per-capture RMS series; one additional derived timeline is cached. Each join
is bounded to 200,000 samples/four million cells.

The separate **Fundamental RMS · fitted** mode and vector diagrams retain the existing
four-cycle stationary-model policies. A transient can therefore have valid sample RMS
and no supported fundamental vector. Refusal reasons remain visible; no nearest valid
phasor is substituted for a refused cursor support.

## Joining and export

In **Source waveform inspection**, open **Combine successive captures from one relay**.
Select 2–8 originals and confirm that they came from the same physical relay. Matching
declared relay IDs alone do not authenticate physical identity. The implementation is
vendor-neutral and requires matching channel identities, gains, units, ratios, and
skews, plus usable declared source times. Different layouts require explicit channel
reconciliation; unknown clocks are never guessed.

The joined view retains every original sample in chronological timestamp order. Gaps
and overlaps are reported. Identical/indistinguishable timestamps are rejected rather
than silently deduplicated. Each capture retains its trigger in provenance; the first
chronological capture supplies the displayed zero. Source boundaries break paths and
RMS supports. Digital high-state spans end/open as unknown at those boundaries.
Fundamental and operational studies continue to use the original captures.

**Download joined COMTRADE + provenance ZIP** produces `joined.cfg`, `joined.dat`,
`joined.hdr`, and `provenance.json`. It is a derived COMTRADE 1999 ASCII export, visibly
marked DERIVED JOIN, not a relay-original capture. Compatible integer raw counts retain
their calibration. Fractional source counts use explicitly reported 32-bit quantization;
unknown units/calibration that cannot be represented safely are refused. Timestamp
resolution and maximum amplitude/time export errors are reported. The exporter
re-imports and checks samples, units, amplitudes, and digital states before returning
the ZIP. Original files are unchanged and remain in the incident. Re-importing only
CFG/DAT does not retain the entire provenance; preserve the ZIP and originals.

## What the blocks mean

`TIME-DAT` holds the uniform-grid operational pipeline when raw timestamp recovery
exceeds its policy. It does not establish that monotonic raw source times cannot be
viewed or used for sample RMS. Source analysis remains separate. The UI now explains
this distinction and links directly to independent source analysis.

For the supplied DR2, the operational pre-fault selection leaves only one sample after
its two-cycle backoff: the recorded trigger is 12 ms after capture start. Its crest
factor is necessarily 1 and cannot establish RMS storage. Crest factor is also
invariant under a constant gain change. The legacy SCALE-CF message has been corrected
to state support/waveform review is needed; its severity and numerical gate are
unchanged. DR2's accumulated source-time deviation is approximately 0.190 ms versus
the existing uniform-grid recovery allowance of approximately 0.083 ms. No time repair
or sqrt(2) scaling correction is performed. These captures are successive recordings
from one relay, not two line ends.

## Evidence and limits

- Browser verification with both supplied recordings: amplitude axes, waveform/sample
  RMS/fitted modes, exact cursor readouts, global navigation, record switching, top
  digital selection, joined timeline, COMTRADE download/re-import, and mobile overflow.
- Both vendor captures decode to 1,800 samples and eight analog channels. The joined
  result has 3,600 samples and a declared 0.165 ms overlap. All eight analog channels
  round-trip with zero measured amplitude difference for these files.
- Independent tests cover sinusoid + DC/harmonic RMS, clearing, missing observations,
  irregular timestamps, extreme dynamic range, the synthetic oracle, boundary spans,
  compatible/incompatible joins, duplicates, overlaps, quantization, and round trips.
- Logs and private screenshots/exports remain under ignored `out/qa/rms-join`.
- No field-accuracy claim, blanket support for proprietary relay formats, automatic
  clock authentication, or operational enablement is introduced. The joined view uses
  declared source times. Cross-boundary fundamental estimation is not enabled.

Validation: full suite 1,809 passed / 28 private-corpus skips / one upstream warning;
Stage-A 10,000 PASS, clean p95 0.4361%. Chromium reported no JavaScript errors in the
checks described above. No proprietary or additional physical relay family was tested.

Restart the Python application after pulling this update, then reload the browser.
In GitHub Codespaces the launcher avoids a pasted multiline command:

```bash
OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/start_codespaces.py
```

Stop the old app in its own terminal with Ctrl+C first. Use `--port 8092` if another
process needs 8091. The launcher permits only the exact Codespaces forwarding hostname,
retains `out/browser-test`, and does not provide public-user authentication.
