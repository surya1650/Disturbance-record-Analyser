# Real-source input workflow — plan v1

2026-11-04 Asia/Calcutta. Branch `codex/operator-ui-review`, baseline `e76bd6e`.
The user supplies two actual COMTRADE captures and requests real-data validation,
automatic editable names, and saving blocker answers on the same recording rather
than creating another visible corrected file. Private recordings/names/ratings
remain under ignored `work/qa-real-source-inputs-2026-11-04/` and are never committed.

## Outcome and constraints

Keep Upload/parse→Analyse→Compare(optional)→Report. Auto-fill incident/source/end
display labels from useful CFG/CFF filenames (or meaningful header/folder fallback),
preserving explicit edits. Labels do not establish physical S/R, circuit identity,
same-event association or clock alignment. A single recording remains inspectable.

Save reviewed missing CT/VT ratings as source-hash-bound input metadata for the
same logical incident/record and exact visible filename. An immutable input
revision preserves earlier results/history; original CFG/DAT/CFF bytes and file
hashes remain intact. Reopen/edit existing answers. Corrected-file export remains
secondary and optional. Keep explicit-copy compatibility for engineering clients.

Normalize reviewed ratings once at the existing parser/source boundary, before
conformance and primary normalization. Preserve original/effective provenance,
reject stale/forged/malformed reviews and include review identity in caches.
Primary-valued sources are not multiplied again. All operational rereads, viewer,
RMS, source analysis, report and native sample endpoints consume the same inputs.
No estimator/DSP/window policy or numerical gate is weakened.

Offer contextual per-incident line facts instead of requiring a pre-existing
global registry entry: explicit length and impedance units, method-specific
sequence constants, selected physical ends and editable auto-filled names.
Missing facts may remain a draft and cause named refusals. Do not invent voltage,
zero-sequence/source impedances, topology, polarity, ratios or clock evidence.
E5 does not require Z0/source impedances/GPS. A physical single-end calculation
may require additional method-specific data; inspection/report does not.

## Phases

1. Privately inspect the supplied real captures and record exact missing facts;
   ask only those needed for the requested physical result. Keep raw/declared
   primary observations available while engineering answers are pending.
2. Implement same-record source-bound ratio reviews and one shared normalization
   path, retaining review metadata across assignment changes and cache isolation.
3. Add automatic editable display names and contextual incident line inputs,
   preserving revision/source guards and the four-page report.
4. Validate the real pair locally, old/new revisions/bytes, stale reviews, editing,
   source changes, missing facts and real report PDF. Retain synthetic oracle
   tests as numerical regressions; no private data enters tests or public evidence.
5. Run direct architecture/self-test, changed Ruff/JS syntax, full pytest and
   Stage-A10000; checkpoint phase commits and final qualified source. Review-branch
   publication follows actual authorization/tool approval; never bypass a rejection.

## Baseline and expected changes

Protected baseline:2279PASS/28private skips, Stage-A10000PASS cleanp95 .4361%,
known42km E5 unchanged at41.98828243177587km; line diagram report qualified.
Expected changes are better source labels, persistent in-place logical review,
and physical values only after actual missing ratings are entered. Unknowns
stay unknown. Native operational-window eligibility may still refuse location
even when one-cycle observation RMS is available.

The real-pair audit is complete in private scratch: both sources decode; one
needs secondary instrument ratings, the other declares primary data and existing
ratios. Neither supplies verified cross-record clock evidence. Engineering facts
have been requested asynchronously. Work that does not need those answers proceeds.
