# Reviewed zone-boundary comparison — 2026-11-03

Contract: [plan v1](ZONE_BOUNDARY_COMPARISON_PLAN_v1.md). Branch
`codex/operator-ui-review`, starting `b91e65a`. The user requested the next task
and authorized continuation. This delivery adds the bounded settings-backed
comparison left unavailable by the preceding evidence audit.

## Behavior and provenance

The existing per-record R–X review form supplies settings identity/event-time,
phase/scaling/polarity, settings-base CT/VT ratios and ground-specific facts.
No new form or menu is added. Each record gets its own comparison, including
corroborating relays; no other relay's settings are borrowed.

`zone_comparison.version=1` reports the classified fault loop, exact phase/earth
characteristic kind, fixed operational window, complete overlapping phasor
support counts and each exported boundary's **inside**, **outside**, **mixed**
or **not evaluable** relation. Native `Characteristic.contains` evaluates
settings-base points; an inscribed display polygon does not replace mho
containment. Native k0 is derived only when the supported ground loop needs it.
Declared primary V/I impedance is divided once by the reviewed VT/CT ratio.

The existing navigator computes the model once and the matching relay evidence
stores the same object. Main technical R–X, all-relay annex and navigator views
render that stored data. Simple report and its HTML/JSON exports get a short
availability/refusal note for matching selected source hashes. Cursor, display
loop, zoom and manually chosen observation regions do not recalculate it.

Recording/settings/mapping hashes and reviewer evidence are checked again.
Missing/stale/ambiguous exports, unavailable compensation or zero-sequence
transfer, wrong characteristic kind, invalid geometry, gaps/multi-rate,
nonfinite values, saturation/clipping, unsupported/short/half-cycle windows and
detected mixed-state transitions retain named reasons. Unsupported optional
comparison does not hide recoverable waveforms or block eligible E5 location.
Unknown candidate support counts remain unknown; zero evaluated supports means
no geometric evaluation was performed.

Containment is a conditional model projection. It does not establish zone
enablement, pickup, timer expiry, scheme behavior or correct protection
operation. `zone_expected`, FL-01–03 and the neutral rule-summary policy from
the preceding delivery retain their meaning. No confidence coverage or new
standards-conformity claim is made.

## Implementation and verification

- `57b7e43`: plan and baseline ledger.
- `b9300a1`: preserve RIO original-byte hashes across LF/CRLF/CR/mixed endings,
  retaining the parsed values and Latin-1 bytes. Three hash cases reproduced
  failures before the fix; all four then passed. Settings/RIO group: 31 passed,
  two private skips. CRLF HTTP review is also exercised.
- `d9ddce1`: exact-loop/native-geometry backend and independent circuit oracles.
- `d83359a`: existing-view integration, source guards and short report note.
- `d6af8a8`: final review found an actual 80 Hz/50 Hz source could reach the new
  comparison above Nyquist through the existing parser/conformance/DSP path.
  The comparison now requires frequency strictly below half the sampling rate.
  That source and the exact-Nyquist boundary reproduced two failures before
  the fix and now refuse with a named reason. No DSP/estimator gate changed.

The 83 backend tests cover all supported fault loops, two common rotations and
settings-base ratios, independent phase-domain circuit results, exact mho
containment versus its display outline, every-support mixed results, zero k0,
unknown/invalid geometry, source/review/quality/window/refusal bounds and
unchanged synthetic E5. Integration checks cover per-corroborator isolation,
primary swaps, no line/remote requirement solely for geometry, LF/CRLF exports,
stale/late/ambiguous settings, source-hash matching, single computation and
immutable old HTML/navigator results. Shared presentation tests check escaping,
legacy versions, null/zero counts and source switching.

Before the final Nyquist correction, full pytest passed **2,190 tests**, with
28 private-data skips and one inherited warning; Stage-A10,000 passed clean
p95 **0.4361%**, zero impossible distances without caveats. Corrected final
source is `d6af8a8`; complete final verification is recorded below.

## Work bounds and limits

The software permits at most 4,096 operational supports and 32 zones, with
bounded supported characteristic outlines up to 512 vertices. Over-limit input
is explicitly unavailable; it is never silently sampled or truncated. The
existing 1e-6 A current floor is numerical policy, not relay pickup. Support
counts overlap and are not independent observations.

A single-process synthetic run at 4,096 supports × 32 polygon zones × 512 vertices
returned the expected relations in **7.30 seconds**. This is one bounded local
observation of the eligible path on `d83359a`, not a production time guarantee,
total-memory limit or multiuser qualification. The later Nyquist gate leaves
that 1,000 Hz/50 Hz path eligible. QA is ignored under
`work/qa-zone-comparison-2026-11-03/`; no real substation data was supplied or
added to Git.

Previous reports/source bytes are not rewritten. New revisions freeze their
own inputs; old results without comparison version1 remain legacy evidence.
For CRLF/CR/mixed RIO files only, newly imported provenance now names the actual
raw-byte SHA-256 rather than a newline-normalized text hash. Parsed numerical
settings and LF identities are unchanged. Site settings applicability and field
accuracy still require authenticated external evidence.

## Final qualification and delivery

Frozen source `d6af8a8b8c8d9f0550e7cccc77c1de5c1af18561`:

| Check | Result |
| --- | --- |
| Direct architecture guard and self-tests | PASS |
| Complete pytest | **2,192 passed, 28 skipped**, one inherited Starlette warning; 107.21 s |
| Stage-A 10,000 | **PASS**, clean p95 **0.4361%**; zero impossible distances without a caveat; 54.1 s |
| All changed Python Ruff / JavaScript Node syntax | PASS |
| Whole-repository Ruff | **26 inherited findings remain in untouched files** |
| Diff whitespace | PASS |
| Independent final plan review | PASS; Nyquist finding closed by both exact regressions |

Chromium desktop and 390px mobile review→comparison passed on final source:
S/AG has 21 evaluated supports inside the broad exported earth boundary and 21
outside the distant boundary; an exported phase-only boundary is explicitly
not evaluable for AG. The other relay remains isolated. Navigator and evidence
contain the same values, and display-loop/cursor/interval changes leave the
comparison fixed. Short Simple report notes and HTML/JSON exports agree.
The known 42 km demo still returns **E5=41.98828243177587 km from S**.

The full desktop/mobile flow on `d83359a` additionally passed late ambiguous
settings, preserved old HTML/navigator bytes through revision 3, unchanged source
hashes, raw eight-analog visibility, no-settings E5, rapid record changes and
route cancellation. Ambiguous exports correctly produce an attention state
with a named comparison refusal while eligible E5 remains available. Final
core smoke on `d6af8a8` confirmed the reviewed path after the sampling gate.
No page errors or mobile document overflow were observed. Browser-owned port 8138
was stopped; all synthetic QA/harnesses remain ignored under the stated work
directory. Browser timing is not presented as a capacity or production claim.

Root owned plan, RIO byte-identity fix, short report integration, code review,
gates, commits and delivery. engine_report_audit owned the backend and numerical
tests; readiness_audit owned navigator/report integration and independent
backend review; browser_qualification owned shared JS presentation and browser
checks. All agents finished before delivery; no competing writer remains.

The plan's P1–P3 are complete within software/synthetic scope. The final
documentation commit records these results and the next-session/goal ledger;
authorized review-branch push and exact remote HEAD verification follow it and
are reported in the delivery response. No main merge, environment publication
or production deployment is included.
