# Channel comparison acceptance

Local draft on published base `f52911e`. No environment configuration updates,
commits, pushes or publication were performed. Plan: CHANNEL_COMPARISON_PLAN_v1.md.

## Behavior

Compare independent source recordings now displays all analogs in shared rows,
voltage first, other analog quantities next, current last. Unique quantity/phase
identities pair; unknowns, duplicates, contradictory metadata and absent counterparts
retain their source IDs in one-sided rows. IN, I0, 3I0, ordered phase pairs and RMS
qualifiers stay distinct. Source-analysis meanings cannot silently collapse those
identities. A/B/C versus R/Y/B conventions are scoped separately for current and
voltage; numeric IEC phases retain their identity.

Every plot has its own labelled amplitude scale, 160 px waveform height and 12 px
HTML axis labels. Both captures use the larger horizontal span, measured from each
recording's first observation. The shorter source is not stretched. If usable time
is absent in either source, both use sample indices. Hover and the accessible range
control move the common display cursor. This is an envelope overview; exact values
remain in the primary workbench. Recording starts do not establish synchronized
physical events, common incident or terminal assignment.

The primary workbench defaults to the same quantity order. Its existing paging,
hide/reorder controls and exact eight-channel cursor batches remain supported.
Cross-quantity overlays remain separate even when both sources use raw counts.
Phase colours also scope header conventions by quantity. Editing analysis choices
aborts and clears a comparison, preventing stale pairings.

## Verification

| Gate | Result |
| --- | --- |
| Architecture self-test and direct architecture check | PASS |
| Changed JavaScript syntax and pure model/transport tests | PASS |
| Full pytest suite | 1790 passed, 28 skipped, one existing Starlette warning |
| Stage-A 10,000, seed 0 | PASS; clean p95 0.4361% |
| Synthetic known-m CLI exercise | Actual m 0.42 / 42 km; E5 m 0.41988 / 41.988 km; E4 clock gate retained |
| Full Ruff | 40 existing findings in 22 files, every affected file unchanged from HEAD |
| New Python test-wrapper Ruff | PASS |
| Desktop/mobile Chromium, reordered real intake/API path | PASS; 16 analogs, VA/IA paired across different CFG positions, unmatched residuals, equal desktop row geometry, shorter capture retained, choice invalidation, no mobile overflow or page errors |
| Chromium renderer qualification, 64 analogs per source | PASS; 128 plots/rows, 160 px plots, 12 px labels, desktop/mobile; observed mount 42.1 ms in this environment |

The absent private-corpus cases account for the 28 pytest skips. Public synthetic
data was used here; this does not qualify arbitrary field captures or production
concurrency. The 128-channel browser case directly supplies metadata to the renderer;
the reordered 16-channel case goes through actual upload, worker and inspection API.

Local evidence: ignored `out/qa/channel-comparison-2026-10-29/`, including desktop/
mobile screenshots, stress screenshot, synthetic source fixtures, browser scripts,
pytest logs, Ruff JSON, CLI output and Stage-A report. No private captures added.

## Same-defect sweep and limits

| Surface | Finding and disposition |
| --- | --- |
| Source comparison | Independent first-CFG-channel defaults removed; all matching rows shown |
| Primary default order | Shared plan orders analogs; source inventory and IDs unchanged |
| Overlay grouping | Quantity added to group key, preventing V/I raw-count mixing |
| Phase colours | Header convention scoped to quantity; ambiguous B remains unknown |
| Exact cursor transport | Existing bounded native/point transport retained; Node transport tests pass |
| Numerical diagnostics and exported reports | No numerical/model changes; existing suite and synthetic oracle checks retained |

No parser, estimator, scaling default, physical end assignment, database or report
mathematics changed. No new R-X/playback algorithm or merged-COMTRADE workflow is
claimed by this change. Existing TAKEOVER and operator acceptance limitations remain.
Browser coverage is Chromium at 1520/1100 and 390 CSS px; broad device/accessibility,
public hosting and multiuser production qualification remain separate work.
