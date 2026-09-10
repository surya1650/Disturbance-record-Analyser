# Recording and philosophy checklist evidence

2026-09-09. Implemented locally; not committed or pushed. This is a bounded
reference-pack audit, not a full configuration assessment or TB 854 validation.

## Implemented

Every incident record retains a separate checklist, including corroborating,
excluded and blocked records. Inventory checks do not clear conformance blocks.
The application API, browser and versioned HTML annex expose the same results.
The standalone CLI's existing audits remain separate; this delivery does not
add the new per-relay checklist to its build path.

An optional, explicit `recording_profile` selects the WG-3 base digital table:

| Profile | Reference | Required rows retained |
|---|---|---|
| `wg3-132-distance` | 132 kV Main-1 distance, table 5, pages 28-29 | 32 |
| `wg3-132-backup` | 132 kV Main-2 backup, table 8, page 30 | 14 |
| `wg3-220plus-distance` | 220 kV and above distance, table 11, pages 31-32 | 42 |
| `unconfirmed` | Applicability not declared | No table inferred |

The original local WG-3 source tables were inspected, including the table 11
continuation on page 32. Each requirement carries its source row, matched raw
channels and action. Matching uses existing canonical mappings or the normalized
exact reference label. Unsupported semantics remain not evaluable. General trip
does not replace phase/zone trip; carrier send does not replace receive/failure;
one relay's generic health point does not prove the other relay's health input.
Multiple candidates and invalid digital samples require review. A point passing
means recorded mapped coverage, not operation, wiring or complete configuration.

Recording checks cover representative single-rate sampling, actual pre/post
capture around a valid trigger, and analog presence. Invalid triggers cannot
produce duration judgments. Multi-rate data cannot pass all-segment sampling
requirements from its representative rate. Conditional tables 6/9/12/13,
trigger logic, configured capacity and bay/topology additions remain not evaluable.

RIO exports associate with each record by exact folder/stem, otherwise a unique
record beneath the export folder. Shared ambiguous exports and multiple versions
are not selected. Original file hashes, importer, missing fields and association
warnings are retained. File association does not verify relay identity or the
effective settings version at the event. XML/document/API imports are unsupported
in this path; other attached export filenames remain visible.

The philosophy view screens exposed Z2/Z3 minimum delays, reverse characteristic
and delay, and compensation-parameter availability. Missing timers/angle and
missing reverse characteristics are unknown, not default-zero failures or proof
of disablement. Explicit zero timers remain assessable. Reverse delay's +/-0.03 s
tolerance is project policy. Minimum-delay success does not establish coordination.
Per-terminal registry ratios are not borrowed across Main-1/Main-2 cores to claim
verified primary reach. Full settings identity, effective date, zone coordination,
enablement and load encroachment require additional evidence. Catalogued APTRANSCO
line guidance is visible for review without becoming automated compliance.

The source pack includes four frozen FOLD/APTRANSCO/workbook originals and their
manifest fingerprints. Source currency and site applicability are unconfirmed;
these checks do not claim automatic adoption of subsequent revisions. TB 854
catalogue entries remain separate technical guidance.

## Bounded validation

- **437 tests passed**, including 26 new cases in `test_checklist.py` and
  `test_checklist_application.py`: table coverage, strict point distinctions,
  invalid/ambiguous samples, invalid trigger/duration, multi-rate refusal,
  omitted/malformed fields, four independent settings associations, ambiguity,
  unsupported exports, blocked records, explicit profiles and late revisions.
- Architecture guard (direct) and self-tests passed; focused Python Ruff and
  JavaScript syntax checks passed. Diff whitespace checks passed.
- Stage-A **10,000 cases PASS**, clean p95 **0.4403%**; all-located p95
  **11.470%**, 9,929 located/71 refused. CT-saturated mean **11.270%**, p95
  **53.902%**. This is unchanged location-regression evidence, not a test of
  source interpretation, protection compliance or field accuracy.
- Isolated headless Edge verified four profile selectors, persistence through
  review/rerun, four 42-point checklists, six operation comparisons, separate
  Main-1/Main-2 RIO delays, missing remote exports, late settings and immutable
  earlier HTML. Desktop/mobile/report screenshots were inspected; no JavaScript
  errors or mobile page overflow. Wide tables scroll within their container.

Preview: http://127.0.0.1:8095/#incident/a2d915fe7a3542cdb99f3ce468e7b812,
synthetic data only, `out/application-checklist-preview`. Automatic approval
review rejected stopping/restarting 8094 with "blocked by policy"; it remains
running. Existing 8091/8093/8094 application data and reports were not reset.
Original 8091 revision payloads and both report SHA-256 hashes were checked
against the earlier preservation snapshot and remain identical. The final
mixed-case zone-name missing-timer correction is tested in the working tree;
the already running 8095 backend loads that small correction on its next normal
restart. The displayed synthetic exports use uppercase zone names.

## Still unsupported or unvalidated

Full recorder configuration/trigger verification; all vendor channel semantics;
controlled event-effective settings contracts; SAP/GIS/API/document joins;
site-specific philosophy applicability; full zone/teleprotection/reclose/backup
coordination and field operation adjudication. The original TB 854 matrix gaps
remain open. Repository tests do not establish TB 854 validation.

Next operational milestone is linked channel navigation, R-X inspection and an
SLD-style event sequence using the existing per-relay evidence. Unsynchronized
records must retain local trigger-zero axes; correlation candidates must not
create a falsely precise common event order or invented breaker positions.
