# Autonomous analyser execution — 2026-10-30

Contract: [approved phase plan](AUTONOMOUS_ANALYSER_GOAL_AND_PLAN_v1.md).
Branch: `codex/operator-ui-review`. Starting HEAD: `15dcb90cf2dd377fb8a7ff0917ef38dc7d24b02f`.
No field records or independently confirmed fault locations are available here.
All new browser demonstrations use the existing synthetic generator, without changes.

## P0 — baseline established

Fresh direct architecture guard and its self-tests passed. Full suite: **1957
passed, 28 skipped, one upstream Starlette/httpx deprecation warning**, 99.99 s.
Skipped tests require unavailable private corpus/local attachments. Repository-wide
Ruff has **40 inherited errors**; retain the baseline separately and lint changed files.
Stage-A 10,000 passed: clean p95 **0.4361%**; the original refusal accounting remains
in `out/qa/autonomous-2026-10-30/baseline-stage-a.log` (ignored).
Known 42 km demo: E5 **41.988 km from S**, E4 gated without clock evidence.

Baseline desktop (1440×1000) and mobile (390×844) screenshots of Waveforms and
Simple report are saved under that ignored QA directory. Dedicated application
root/port: `out/qa/autonomous-2026-10-30/app`, 8130. No prior app data is used.

Regression matrix to preserve:

| Existing workflow | Baseline/check contract |
| --- | --- |
| Raw inspection before physical assignments | Synthetic upload needs_review; all analog waveforms visible |
| Shared cursor/sample RMS/Fourier | Existing cursor/vector tests plus desktop/mobile inspection |
| Automatic/manual pre/fault/post | Existing event-study/automatic-region tests; no mandatory invented baseline |
| Reviewed universal ratios and optional channel exceptions | Existing instrument-review tests; immutable source/revision binding |
| Four changed-first digital tracks, paired analog plots | Existing layout/channel-comparison tests and browser checks |
| Simple report/HTML/JSON | Existing shared report model tests and synthetic browser downloads |
| Historical revisions and choice/source guards | Existing application/event-study/stage tests; new calculation queue tests |
| E5 and eligible one-end fallbacks/refusals | Existing engine and source validation tests; unchanged Stage-A oracle |

## Phase status

- P0 complete as above.
- P1–P6 in progress; no completion or field-accuracy claim yet.

Configuration application: selected analyser checkout was already provisioned;
switched to requested review branch. Deselected AHI checkout had no uncommitted
or unpushed work after remote refresh. A full byte-compared archive, including
Git metadata and ignored files, was retained outside checkout roots at
`/workspace/preserved-checkouts/AHI-portal-deploy.tar.gz` before removal.
Saved repository selection was not changed.

## P1 — honest capability and input guidance

Help now describes actual one-cycle sample RMS/Fourier support and automatic event
regions, with manual A–B refinement optional. Location prerequisites are scoped by
E1/E2/E3/E5/E4; digital/settings facts are requested only for their interpretations.
Custom zero-sequence fields are optional/collapsed. Selecting a registry line no
longer silently opts into assumed CT defaults; existing explicit choices remain.
The report-pane calculation extension is guarded until the P2 module is loaded.
Targeted capability, real source-analysis mount, input, cursor and layout tests:
**30 passed**. All four changed JavaScript files pass Node syntax checks. The
line-selection regression was reproduced against baseline (132 vs expected 0),
then passed with the fix. No numerical estimator or source bytes changed.

## P2 — calculation and versioned physical result

Simple report now exposes Calculate fault location using the existing durable
review/worker path, explicit line/S/R declarations and preserved accepted mappings.
Other records are explicitly excluded, without deletion. Reruns create a new
revision, check identical frozen sources and keep previous reports. Route changes
cancel client work; server revision checks remain authoritative. Same-relay
successive captures cannot be assigned as opposite-end primaries.

New results add `location_summary.version=1`: exact engine distances, named method,
mode/type, per-method acceptance/weights, supported local windows, public finite
diagnostics and line/source/metadata/revision hashes. Private callable diagnostics
are excluded. Existing prose/history remain readable; invalid new evidence never
falls back to a distance parsed from prose. Section-aware km conversion is retained.

Settings-dependent zone inference now requires that terminal's actual Z2 timer;
a project fallback or the other end's timer cannot prove its zone. Explicit
zone-qualified contacts remain observations. Worker/features ratchet increases
are intentional for binding and per-terminal evidence (no blanket reseed).

Targeted application checks: 31 passed; summary checks: 7 passed; settings checks:
9 passed; prior rules/report group: 42 passed, 8 private skips. Calculation UI
checks verify missing facts, single-end selection, stale sources, revisions and
cancellation. Browser primary action yields E5 **41.98828243177587 km** on desktop
and mobile. HTML/JSON report exports retain E5 and the observation model, without
page errors or mobile overflow. Minimum-input schema follow-up is in progress:
E5 must not require unrelated missing Z0/source impedances.

## P3 — concise observations and qualified interpretation

The shared event report adds a versioned explanation separating source-bound
analog/digital observations, matching operational classification/location, and
uncertainty. Missing healthy baselines stay missing; command assertions cannot
prove physical CB opening/reclosure or settings compliance. Sample/time brackets,
region/source hashes and omitted-transition notes remain in JSON. The UI and
HTML export consume the same explanation. Exact stored record selection is
required before a method-labelled location/classification can be shown.
Fresh focused report/explanation/UI tests: **37 passed**, one upstream warning.
The broader event/navigation/R-X group passed **81 tests**. Private opposite-end
records and patrol truth remain unavailable; this is synthetic/software evidence.

## P4 — existing R–X and full-line view

Simple report renders the shared explanation, a full declared line sketch and
only an eligible method-labelled in-range marker. Its secondary disclosure
loads the existing stored R–X/source navigator for selected records and follows
the same source-local report cursor; no end synchronization is implied. Missing
line/towers/settings are not synthesized. A regression fix prevents the last
valid R–X marker from persisting across an explicit missing-point interval.
Node navigation/event-study tests and the broader **81-test** group passed;
browser report/HTML/JSON render on desktop/mobile without overflow or errors.

## P2 follow-up — genuinely method-specific engineering inputs

The registry now preserves absent R0/X0 and terminal source impedances as unknown,
rather than demanding them for E5 or treating absent sources as zero. Eligible
phase loops do not derive unused ground compensation. Ground single-ended
methods refuse missing line Z0; E3 refuses missing actual source Z0. CLI and
Tier1 explain missing compensation. No estimator equation, synthetic generator,
clock, scaling or ambiguity gate changed. Existing known-Z0 outputs stay the same.
Synthetic cases cover 12 E5 fault/distance combinations, three single-end phase
loops, named refusals, invalid declared values, mixed-section chainage, CLI and
HTTP intake → Worker → immutable structured result. New suite: **23 cases**;
final selected integration group **35 passed**; broader physics/ML **144 passed**.
Stage-A 10,000 remains PASS, clean p95 **0.4361%**, no uncaveated impossible result.
Accepted physical declarations are retained on unchanged reruns; editing the
line or either end clears confirmation. Display selections are never promoted.
Exact intentional module-growth budgets are updated without unrelated reseeding.
