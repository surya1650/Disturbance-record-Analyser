# Reviewed channel mapping and native sample inspection

2026-09-09. Implemented locally, not committed or pushed. These are bounded
software capabilities; they do not establish field correctness or TB 854 validation.

## Reviewed identities

Assignment review now retains every original CFG analog/digital position, label,
declared analog quantity/phase, P/S flag and ratios. A1/A2 and D1/D2 identify
positions in CFG order, independently of free-text labels and declared channel
numbers. Duplicate digital labels remain distinct points with disambiguated keys;
their original labels remain in the inventory. Analog channels previously dropped
by automatic mapping can be explicitly selected before conformance runs.

An assignment may contain:

```json
"channel_mapping": {
  "record_hash": "<exact lowercase SHA-256 of this CFG+DAT or CFF recording>",
  "reason": "Reviewed source and rationale for the correction",
  "analog": {"A1": "IA"},
  "digital": {"D1": "TRIP_A"}
}
```

Analog targets are IA/IB/IC/IN/VA/VB/VC/VN; A/B/C corresponds to R/Y/B.
Digital targets are the current canonical signal vocabulary from `/api/config`.
Either kind also accepts `ignore`. Omitted entries use automatic mapping.
Mapping requires the exact original recording hash and a nonempty reason.
Unknown positions/targets, stale hashes, analog collisions and incompatible or
unknown declared analog units are refused. Correcting units/ratios, polarity or
digital inversion is unsupported. Source files and sample values are not edited.

Mappings are per record and per revision, not inherited from Main-1 to Main-2.
A reviewed digital meaning overrides name matching for that raw point only;
other candidates remain visible. An ignored point cannot satisfy an exact-label
recording check. Digital overrides reach rules, evidence, DSP timing, reports,
audits and navigation. A raw label remains the displayed origin of the evidence.

A parseable blocked record can be reviewed, but it only becomes usable after
fresh conformance passes. Missing required phases, invalid quantities and truncated
records remain blocked. Earlier automatic flags, mapping reason, source hash and
reviewed rows remain visible in the result/browser/HTML. Restoring automatic mapping
creates another revision; it does not change earlier reports. If restoration
reintroduces a missing phase, that record is blocked again. Stale saved mappings
are cleared from the editor rather than silently attached to a different hash.

The review note is an operator/collector declaration, not an authenticated signature
or proof of wiring correctness. Automatic mappings are not thereby field-validated.
Unsupported digital meanings still need a defined semantic contract; arbitrary
free-text aliases do not create new protection functions.

## Native sample inspection

The navigator's **Load native samples** button reads the selected mapped analog
channel over the selected local interval. It returns exact parser-normalized
samples with their zero-based sample indices and local times, without thinning,
resampling or interpolation. Previous/Next sample moves the shared cursor to
recorded points. Otherwise the readout explicitly identifies the nearest recorded
sample and its time offset from the cursor; it does not claim an interpolated value.

Inspection RMS and measured absolute peak use all native samples inside the
**inclusive display bounds**. They are sample-weighted, including for unequal
time steps, and are separate from the pipeline's half-open fault-analysis window.
Empty selections and nonfinite samples produce unavailable metrics. Parser-normalized
A/V labels are retained even when the CFG declared kA/kV. Peaks are not converted
to RMS. Existing quality flags remain visible; no CT reconstruction is performed.

`GET /api/incidents/{id}/samples` requires `revision`, `record`, `channel`, `start_s`
and `end_s` (local seconds). It verifies the path is within that revision's run,
checks the unchanged recording hash and matches the source position/label to the
frozen channel inventory. Unanalysed/unavailable records, old revisions without
channel inventory, changed sources, invalid bounds or mismatched replay identities
are refused. Requests above **20,000 samples** require a narrower interval and are
never silently decimated. The current implementation reparses the local recording
on each request; this is bounded response size, not indexed acquisition storage.

Native data clears when record/channel/interval changes. Delayed responses cannot
replace a subsequent selection. Current-view HTML export includes native sample
readouts and interval metrics when loaded; existing results and reports remain
unchanged. Phase-loop R-X still uses its separately labelled thinned phasor display;
native waveform loading does not add full-resolution R-X or ground/zone overlays.

## Validation and limits

- Mapping milestone: **468 tests passed**, 16 added cases. CFG and CFF recovery,
  unchanged sample/ratio/hash behavior, explicit phase swaps, collisions/stale
  hashes/quantity refusal, truncation blocks, digital evidence/DSP/audit agreement,
  duplicate raw labels, exact-label ignore and revision restoration are covered.
- Native-sample milestone: **480 tests passed**, 12 further cases. Inclusive
  boundaries, original values and interval metrics, source/path/identity refusal,
  tampering, revision-specific API behavior, empty/single-sample/nonfinite selections,
  sample-count refusal and unchanged reports/results are covered.
- Node checks pass 16 navigation-model and 10 native-cursor assertions. Direct
  architecture guard/self-tests, focused Ruff, JS syntax and diff checks pass.
- Required Stage-A **10,000 PASS** after mapping/DSP routing changes: clean p95
  **0.4403%**, all-located p95 **11.470%**, 9,929 located/71 refused; CT-saturated
  mean **11.270%**, p95 **53.902%**. The later read-only native endpoint does not
  change this numerical path. These gates do not establish field/TB 854 accuracy.
- Headless Edge verified four-relay mapping review, missing-reason refusal,
  blocked-record recovery/recheck, untouched Main-2 mapping, escaped review notes,
  restoration/exclusion/reapplication across three revisions, unchanged earlier
  report bytes, exact sample stepping, interval measurements and export. Additional
  delayed-response checks covered channel, record and interval changes. Desktop/
  mobile screenshots were inspected; no JavaScript errors or page overflow.

Current complete synthetic preview:
http://127.0.0.1:8099/#incident/52b238dedbab480fa43865258215811b,
revision 3, root `out/application-native-preview`, empty isolated registry.
8098 is the mapping-only preview. Earlier applications remain running and their
saved data/reports are preserved. The original 8091 revision/report preservation
snapshot is still applicable; no original inputs were overwritten.

Remaining: verified ground-compensation and per-relay zone-overlay prerequisites,
common fault-stage/clock association, authenticated review identity, raw-unmapped
analog navigation, indexed large-record retrieval, settings APIs/documents and
SAP/GIS joins. The documented E5 root and external-distance/tower presentation
gaps remain open. No completed TB 854 or field validation is claimed.
