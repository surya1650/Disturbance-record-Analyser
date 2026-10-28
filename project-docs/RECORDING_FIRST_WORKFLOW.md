# Recording-first incident workflow

Use `codex/recording-first-viewer`. In Codespaces, stop the previous server with
Ctrl+C, then run:

```bash
git pull origin codex/recording-first-viewer
OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/start_codespaces.py
```

Open port 8091 from the **Ports** tab and refresh the browser. Keep real recordings
on a private port. If 8091 is already occupied, open that existing port or stop
your old server first; running a second copy on the same port will fail.

## Page layout

- **Waveforms & report:** the selected recording, mandatory analog lanes, digital
  signals below, shared cursors, values/vectors, then the report. A completed
  operational report is the main report; independent source evidence remains
  available through More tools. A joined timeline has its own inspection report.
- **Inputs:** sending/receiving names, explicit recording-end labels, selected
  recording's data issues, channel meanings, line values and manual zone inputs.
- **Diagrams:** named line schematic and conditional source phase-loop R–X plot.
  A supported window can be sent back to the waveform viewer. Equal R/X scales
  and disconnected unavailable windows are preserved.
- **More tools:** Combine captures, Compare recordings, Detailed evidence,
  Operational study, Files & history. Switching menus keeps the active recording
  and waveform cursor. Switching recordings reloads that recording's workbench.

## Inputs to collect

| Purpose | Required information |
| --- | --- |
| Identify ends | Sending and receiving substation names; explicit end for each recording. Several captures can belong to one end. |
| Line schematic | Line/circuit name and length in km. Missing values stay unavailable. |
| Conditional phase-loop projection | Supported corresponding V/A fits, reviewed phase meanings, assumed AB/BC/CA loop, selected window and positive X1 in primary Ω/km. R1 supports a model mismatch calculation. |
| Line data | Nominal kV; positive-sequence R1/X1 and zero-sequence R0/X0 in primary Ω/km; traceable model provenance. The configured-model dropdown also retains mixed-section models. |
| Invalid secondary scaling | Actual primary and secondary CT ratings in A, VT ratings in V with a consistent voltage convention, reviewer and evidence. The existing guided review creates a marked copy and reruns conformance. |
| Manual R–X boundary | Phase-zone name; mho reach/characteristic angle, or exact ordered polygon R/X vertices; primary/secondary ohm basis. These are declared drawing boundaries, not imported relay algorithms. |
| Secondary-ohm conversion | Settings CT ratio = primary A / secondary A; VT ratio = primary V / secondary V. Primary Ω = secondary Ω × VT ratio / CT ratio. Both ratios must be known. |
| Boundary overlay | Reviewer, evidence and an explicit review of primary phase scaling/polarity. Changed scaling/phase choices clear confirmation. Assumed missing-CT scaling cannot authorize an overlay. |
| Ground loops / exported zones | Matching native settings export, effective settings identity, native compensation convention, CT/VT bases, phase/polarity and zero-sequence VT review through the existing operational settings workflow. Manual source ground loops remain withheld. Never type a guessed k0. |
| Physical breaker/protection verdict | Correct indication meanings/polarities, contact/wiring evidence and effective relay/breaker/AR settings. The line schematic never infers breaker position from an inactive indication. |

Source R–X points are conditional apparent impedances at supported fitted window
centres. They do not identify fault inception or establish field accuracy. Manual
line/zone inputs do not bypass the operational conformance gate.
A model coordinate is not plotted as a sending-end location without an
operational sending-end reference. Display labels alone cannot establish that
reference; receiving-end section reversal is not inferred by the schematic.

## Names, persistence and reports

Names and end labels are saved separately from numerical assignments. Their label
version is printed in reports. A frozen operational line definition supplies its
configured substation names when present. Explicit operational ends cannot be
contradicted by display labels. Upload order never assigns an end.

Manual diagram inputs and source choices persist for the selected original
recording and incident revision. They are not automatically inherited into a new
analysis revision: review them again against its sources. Concurrent stale saves
are rejected. Name labels can inherit into later revisions and can be edited
without changing archived numerical reports. The named-report endpoint adds an
escaped presentation header; `/report` remains the original archived artifact.

DR1 and DR2 supplied for this task are successive captures from one relay. Label
both at the same end. Combine them through More tools, confirm the same physical
relay, and open the joined viewer. The derived COMTRADE ZIP and provenance are in
Combine captures. Its report follows the waveforms. Uploading a derived export
does not authenticate a second end or clear timing/scaling checks.

## Catalogue follow-up

Manual inputs are available now; configured line dropdowns already use declared
line models. A future bulk-import workflow should populate stable substation,
line/circuit and relay IDs, S/R links, section tables, CT/VT cores, settings
versions and evidence. It can then drive substation-filtered line dropdowns.
This change does not implement that fleet bulk importer or invent asset facts.

Verification: full suite 1,834 passed / 28 private-data skips, then focused report
header tests including an additional escaping case; architecture, Ruff and JS
syntax checks passed. Stage-A 10,000 PASS, clean located p95 0.4361%. Chromium
desktop/mobile checks cover saved names, cursor preservation across menus,
line/zone persistence, secondary conversion, ground-loop refusal, waveform focus,
reports and the private DR1/DR2 joined timeline. This is software verification,
not field certification.
Follow-up checks also cover named operational reports/navigation, comparison
headings, scaling-review invalidation, the source-coordinate guard and CT/VT
review creating a new revision without changing its original files.
