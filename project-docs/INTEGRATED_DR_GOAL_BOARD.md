# Integrated DR application goal board

Latest user steering (2026-10-28): operator-focused pre-fault/fault/post-fault
conditions, cursor-adjacent instantaneous/RMS/angle values, following vector view,
and a practical next-owner guide. Base recovery release `bc6d83a` is pushed;
primary1813PASS/1OSskip/one existing warning109.25s. The operator milestone is in
final verification/review. It reuses existing supported windows and explicit A/B
region selection; no new DSP policy or detected physical fault boundary is claimed.
Read [TAKEOVER.md](../TAKEOVER.md) and the new operator-view plan before continuing.

Updated2026-10-28. Inspection milestone main935d3c9, supported reports mainaae3e2f,
conditional source quantities/line inputs main9d1853a (primary1749passed/1OSskip/one existing warning).
Bounded recovery/cursor milestone is in final verification; review and primary acceptance follow.

| Goal | State | Delivered acceptance / exact remainder |
| --- | --- | --- |
| G1 | Acceptance delivered for supported strict source formats | Needs_review/unassigned/no-result main-app source inspection, exact analog/digital samples, unknowns, header-only inventory and explicit decode errors. Dhone/DR2 copies tested without real revision mutations. Candidate recovery adds explicitly framed CFF, digital-only and1/2sample observations and safe complete binary prefixes. Multirate observations retain indices when timing is unsupported; no guessed timestamps. |
| G2 | Core workbench delivered | Resizable separate panes, IDs/units, selection/order/visibility, same-unit overlays, editable phase colours,8channel paging, hover/A/B/add/remove pins, source-time deltas, numeric/keyboard stepping, zoom/pan/reset, explicit sample-index axis and real-gap handling. Actual browser exercised. Further UI polish is optional; no physical clock alignment is inferred. |
| G3 | Supported diagnostics and conditional quantities delivered | Automatic background actual-time models, coverage/refusal reasons, explicit channel meanings, bounded digital edge evidence, possible trip/AR explanations. CTdefaults132kV600/1 and220kV800/1 only for otherwise-known secondary currents; valid supplied ratios retained. Conditional corresponding-window sequence and AB/BC/CA R-X composition delivered with unique meanings, declared/assumedV/A units, support/centre/cancellation/numeric-range prerequisites and explicit physical limits. Lower-density/short-support alternatives remain Not available under unchanged reviewed policy. |
| G4 | Schematic and honest placeholders integrated | Frozen supplied line length/section constants/terminal names with hash/provenance; stored eligible conditional location annotation only. Missing facts say Not available. Independent configured/custom line selection, selected loop/window and sectioned reactance model projection delivered; outside-line values remain unclipped and no marker is drawn. Physical location/line/terminal authority remains unknown. |
| G5 | Source snapshot/detail/export integrated | Four-part conclusions, recorded start/trigger vs inferred event separation, sample-linked model windows, digital edge brackets, units/assumptions, same-model JSON/printable HTML exports. Actual browser/export checked. Reports remain available independently of operational eligibility. |
| G6 | Bounded recovery/cursor qualification delivered; final review pending | Bounded native intervals, two-source decode cache, per-poll source checksums, background1worker/2jobs, global4096digitaledge detail cap with omitted counts, source/options/revision-context identities, frozen pending job inputs, UI abort/generation guards. Serial release/primary verification and pushed milestone evidence tracked below. Candidate adds one8channel×17index cursor batch, hash/generation-bound exact local reuse and16pin limit. Public64channel×50000sample overview338606bytes;40point batch2255bytes/~14.5ms locally. Final review/primary acceptance pending. |

## Current review disposition

One fresh whole-branch supported-analysis review, no Critical. Two Important findings:
inherited reviewed Ignore was discarded; cache identity omitted inherited meanings and operational
snapshot metadata. Both reproduced and fixed in one TDD pass; analog reviewed Ignore also retained.
One provenance finding was regraded Important because marking automatic suggestions as explicit
user choices can mislead trip/AR interpretation. Fixed in the same pass. RED8 -> GREEN33focused;
full isolated suite1662passed/29skipped/one existing upstream warning. No second review or prior152-case research rerun.

Declined review boundaries remain explicit: earlier reviewed inspection internals, published152study,
operational solver numerical requalification, conditionalR-X/sequence, lower-density/support,
newcontainer/digital-only/multirate/truncated recovery, newdistanceestimation, external physical
validity of line/legacy estimates, common-event/clock/ends claims, broaderperformance, deployment,
independent full/private-corpus/browser verification. Parent owns release/browser evidence;
others are either pending software work above or genuinely external physical evidence.

## User instructions retained

No overall Blocked wall for usable source data or source reports. Explain the actual missing or
unsupported input per method. Keep operational numerical safety gates separate. User-selectable
phase colours and explicit fallbackCT assumptions. Analyse source indications and possible causes;
never invent a trip/ARfailure or kilometre estimate from absent evidence. Preserve all original
captures/Downloads content, workbook, Dash findings, real appDB/revisions and protected previews.
Generated browser export source-analysis-r1.json was newly added to Downloads; no source replaced.

## Latest conditional-quantity milestone

One fresh whole-branch review, no Critical/three Important. Fixed in one TDD pass:
unknown AR_CLOSE polarity/missing observations no longer become a no-close explanation;
projection conversion detects underflow and uses scaled complex residuals with per-quantity
numeric failure containment; printable snapshots include selected-window R-X/sequence values,
source support, native indices, channel mappings/units and unavailable reasons.
RED8 plus one positive control ->65focusedGREEN ->1721fullPASS/29skip/one existingwarning.
Actual fresh-context browser pointer/keyboard verified pre-fix8b939ac: custom50km,
X1.4/R1.1, AB/window0 =>10.000000km and expected conditional marker with24/24fits.
Screenshot was inspected but filesystem artifact could not be saved after runtime expired;
no screenshot file is claimed. Parent API replay also verified X1.4=>10km andX1.8=>5km,
distinct hash-bound jobIDs, and all26originalsourcehashes/realpendingrevision unchanged.
New digital-polarity widget and post-fix print interaction remain for final UI qualification.
No second review or prior152study rerun. Ground compensation and lower-density alternatives
remain explicitly unavailable; physical correctness of ratios/wiring/line/event/clock is external.

## Next bounded milestone

Execute docs/superpowers/plans/2026-10-28-source-recovery-batched-inspection.md:
deliberate digital-only/short/complete-prefix/CFF recovery contracts and bounded point batches,
local native cursor reuse, large-source qualification and final browser checks. Existing studies
remain frozen. G6 is still pending; the entire product vision is not declared complete.

## Bounded recovery and cursor qualification candidate

Task1 RED18 ->20GREEN; digital-only/short/prefix recovery split from file acquisition.
Task2 RED19 plus malformed-separator RED1 ->21GREEN; strict CFF decoding retains original
container identity and declared header facts. Source reports survive unavailable models.
Task3 RED19 ->19GREEN; a Node transport regression additionally exercises local cursor reuse,
one overview batch and obsolete-error isolation. Full release verification1785PASS/29skip/one existing warning275.49s.
Real Dhone/DR2 copies retain40channels and1800/3624samples; all26originalsourcehashes and
the protected real pending revision remain unchanged. Qualification details are in
SOURCE_RECOVERY_CURSOR_ACCEPTANCE_2026-10-28.md. Existing152study is not repeated.
