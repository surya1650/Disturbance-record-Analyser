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
