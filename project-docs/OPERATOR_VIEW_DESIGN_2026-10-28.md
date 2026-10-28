# Operator view and takeover design

Latest user request: finish the work and hand over the repository to another owner.
The main view must explain pre-fault/fault/post-fault voltage/current conditions, put
cursor values beside their waveforms, display instantaneous/RMS/angles and a vector
view that follows the cursor. Sample/model bookkeeping belongs in expandable detail.

Build on existing FastAPI/vanillaJS and reviewed source models; no new DSP/model policy.
The currently open CT/AR example has only4samples/2.6ms and cannot support four-cycle
RMS/phase fits. Use the real copied incident to demonstrate meaningful supported models.

Add pure presentation helpers: select one existing window covering the exact cursor,
show conditional fitted RMS and relative phase only for model-consistent fits at the
same centre, with an explicit source-channel reference. Zero/missing/incompatible
phasors retain a specific unavailable reason. Voltage/current vectors use separate
scales and follow hover or a moved pin; never interpolate/extrapolate a phasor or
invent a physical phase/clock/CT ratio. Instantaneous values retain source units;
assumption-scaled analysis RMS carries its separate declared units.

Put readings beside each waveform/overlay, keep a sticky vector panel, and pan the
waveform view when keyboard/numeric cursor movement leaves the visible interval.
Keep the full cursor matrix and technical source/model evidence under details.

Provide pre-fault/fault/post-fault comparison for an explicitly selected A/B fault
interval. These are user-selected regions, never automatic physical fault detection.
Only model windows wholly contained in each region contribute to its typical fitted
RMS; compare matched channel units and show higher/lower numeric changes without
inferring fault type. Missing/pre-capture/post-capture support remains explicit.
Before interval selection show available whole-record current/voltage ranges and
supported cursor readings, with a short instruction to select A/B. No point-count wall.
Exports include the same selected-region summary with selection provenance.

Takeover guide covers clone/install/run, public demo vs real records, mapping/CT/line
inputs, interpretation, verification, exact support/coverage limits and prioritized
next tasks. Preserve all original protected state and existing ignoredQA/ledgers.
