# Missing-input questions and combined recording reports

## Ask for missing facts instead of offering an invalid assignment

The operational assignment selector now stays disabled for timing, ratio and other
non-mapping blocks. Mapping-only CH-MISSING captures retain the explicit reviewed
mapping workflow. Backend assignment refusals include the actual BLOCK reasons.
The source viewer remains available independently.

For secondary quantities with missing or invalid CT/VT ratings, the application now
provides **Provide missing CT / VT ratings** in the source-inspection notice and the
operational review section. It shows the original declaration and asks for actual
primary/secondary ratings per affected source channel, in A or V, plus reviewer,
evidence and confirmation of the secondary designation and a/b gains. VT inputs must
use the same phase-to-phase or phase-to-neutral basis on both sides. Fields start
blank. Shared fields are applied only by an explicit action and can be edited per
channel; different transformers may require different ratings. A voltage-level
recording profile is not an instrument ratio.

**Check inputs & rerun conformance** validates a temporary copy without saving.
**Create reviewed copy & recheck** adds a marked CFG/DAT or CFF copy, HDR and
`instrument-review.json` to a new incident revision. It preserves original files,
earlier revisions and DAT sample payload bytes. The original capture is excluded
from that new operational assignment without deleting it or its declared identity.
The copy has no inferred end assignment and is not automatically analysed.

The writer changes reviewed instrument ratings and marks the device as a ratio
review. Header whitespace/case may be normalized for the reviewed fields; a/b gains,
sample values and source timing are unchanged. A/V form values are converted to
kA/kV header ratings where needed. The review is bound to the original recording
hash; evidence is user-declared, not independently authenticated. Unknown, zero,
nonfinite or unrepresentable inputs are refused. All conformance checks run again:
correct ratings do not bypass timing, waveform, completeness or line-data failures.

## Combined report and export/re-upload workflow

After selecting successive captures in **Combine successive captures from one
relay**, cursor A selects the snapshot for **View combined inspection report**.
This printable HTML includes waveform/sample-RMS plots with amplitude scales, exact
instantaneous/RMS values, original capture/sample origin, digital spans, all capture
triggers, overlaps/gaps and source checksums. Unknown or cross-boundary measurements
remain unavailable. It is an inspection report, not a validated fault-location or
protection-performance verdict.

The combined COMTRADE/provenance ZIP can also be uploaded as a new incident. Select
`joined.cfg` in source inspection, allow independent source analysis to finish, then
use its printable snapshot export. Assigning the captures to opposite line ends is
not required for this workflow. Re-uploading a derived file does not clear timing or
other operational constraints. Fundamental fits are conditional and can be withheld.

## Verification

- Full suite: 1,823 passed, 28 absent-private-corpus skips, one upstream warning.
- Stage-A 10,000 PASS, clean p95 0.4361%; numerical gate policies unchanged.
- CFG/DAT and CFF rating reviews tested in A/V and kA/kV. Reconstructed measurements
  match the original synthetic oracle before complete pipeline analysis. Payload
  bytes/old revisions are preserved, and independent timing blocks remain.
- Invalid hashes, missing ratings, nonpositive values, missing evidence/reviewer,
  unchecked confirmation and unsupported request fields are rejected.
- Browser checks cover blank/required questions, shared/per-channel fields, preview,
  save, original-revision preservation and selecting the reviewed capture.
- Real DR1/DR2: joined 3,600 samples, direct report at the chosen cursor, ZIP export,
  re-upload and source-analysis HTML export all passed. Re-upload produced 250
  model-consistent / 342 withheld channel-window fits. No field-accuracy claim.
- Report tests cover cursor origin, source identity, out-of-range inputs and HTML
  escaping. Private screenshots/reports/exports stay in ignored
  `out/qa/input-questions`; they are not committed.

No actual Chandragiri capture or verified CT/VT ratings were supplied for local
numerical validation. Its screenshot identifies missing metadata, not the correct
ratings. The application now requests those facts; it never substitutes guessed
132/220 kV defaults or silently changes a zero secondary rating to one.

After pulling this update, restart the Python app and reload the browser. Codespaces
can use `OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/start_codespaces.py`.
