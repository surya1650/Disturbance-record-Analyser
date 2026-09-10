# Operation comparisons and onset-correlation evidence

2026-09-09. Implemented locally, not committed. This is a bounded delivery of
milestone 2 in [DR_OPERATIONAL_WORKFLOW_PLAN.md](DR_OPERATIONAL_WORKFLOW_PLAN.md).
It does not complete event/stage association or establish TB 854 validation.

## Delivered behavior

`rules/operation_compare.py` compares all pairs of declared-terminal records,
independent of upload order and analytical primary selection. Four relays produce
two same-terminal pairs and four cross-terminal pairs. Main-1/Main-2 identity is
explicit; unknown/repeated/other labels carry an identity-review note. Records
remain in one operator/collector-declared incident; this does not automatically
group incoming files into incidents.

For mapped start, trip, zone, carrier, breaker-indication and reclose points, the
result retains both observations and first eligible local inception-to-edge
durations. Missing, ambiguous and initially active evidence cannot become a
negative operation finding or a fabricated onset. Same-terminal local-duration
differences are displayed only with compatible classifications and an onset
candidate. These differences are descriptive, with no standards-derived timing
tolerance. Cross-terminal duration differences and causal ordering are withheld.

Different fault/operation observations produce a prominent **Review relay
differences** warning in the browser and report. The existing rule assessment
remains based on selected records and is now labelled accordingly. Comparison
does not choose which relay is correct, prove breaker opening or evaluate the
full protection philosophy. Existing XR wording no longer asserts that a fault
classification disagreement proves wrong channels.

## Correlation contract and project policy

`dsp/correlation.py` compares normalized fundamental-magnitude onset shapes from
existing DSP results. It never changes recorded samples, timestamps, E4/E5 inputs,
fault-location estimates, selected analysis windows or rule verdicts.

- Template: one nominal cycle before to half a cycle after detected inception.
  Search: plus/minus one-quarter cycle relative to the other detected inception.
  At 50 Hz these are [-20, +10] ms and a +/-5 ms residual search. Actual local
  window bounds and effective search width are retained in the result.
- Fixed full overlap at every lag, entirely before the earliest raw trip-like
  assertion. Search grid is the slower native interval, with a 0.5 ms floor.
  Multi-rate/irregular grids, insufficient capture and blocked/saturated/clipped
  records are withheld. Very fast trips may leave insufficient support.
- At least two common changing phase channels are required. Relative excursion
  must reach 15%; mean normalized correlation must reach 0.95, with every used
  channel at least 0.90. All thresholds are project screening choices.
- Lags within 0.01 of the best score define a sensitivity span. Boundary peaks,
  disconnected near-peaks or spans wider than half a cycle are ambiguous.
  This span is **not** a confidence interval, clock error bound or field timing
  accuracy. Score is **not** a probability of correct pairing.
- Known fault classifications must agree. Repeated start/trip edges or recorded
  reclose evidence withhold a candidate. A conservative phase-current pattern
  screen examines complete cycles after inception settling, before trip and
  within the first ten cycles. It is not a full evolving-fault detector.

Candidate lag means **right local time = left local time + lag**. Recorder
trigger zeros stay independent and detected inception stays separate. Absolute
clock metadata is not used; verified clock-quality ingestion is still pending.
A candidate is never applied automatically and cannot prove that two otherwise
similar recordings belong to the same physical event or stage. Later stages,
reclose shots, transit delay and global event ordering remain unassociated.

## Bounded validation matrix

| Capability | Evidence / acceptance | Status |
|---|---|---|
| Local-coordinate lag | Independent continuous step envelopes at 1000/1200 Hz, residual shifts and amplitude scaling; recover prescribed lag within one search sample; reversal changes sign | Validated on bounded fixtures |
| Full DSP timing path | Analytic three-phase sine waveforms with known phase-A amplitude change and voltage sag; recover 40 ms local-coordinate shift within 2 ms despite a 1418 s clock offset; missing timestamps leave result unchanged | Validated on this waveform fixture, not field accuracy |
| Unidentifiable correlation | Flat, periodic, broad, boundary, conflicting phase shapes, missing/nonfinite channels and short coverage produce no lag | Validated refusal fixtures |
| Quality/stage fallback | Saturation/clipping flags, irregular/multi-rate grids, changing phase patterns, repeated operations, reclose, absent or differing fault calls prevent candidate timing | Validated screening fixtures; full stage segmentation unsupported |
| Operation observations | Missing/nonasserted/initially active evidence and independent trigger references remain distinct; cross-end event-time differences are absent | Bounded unit coverage plus prior per-relay tests |
| Identity and revisions | Four-relay API intake produces six pairs; primary changes retain comparisons; old reports are unchanged; report escaping and review warning exercised | Integration validated |
| Browser/export | Synthetic four-relay demo exposes candidate lags and conflicting trip observations; desktop/mobile and HTML report checked; no JS errors or mobile page overflow | Browser QA passed |
| Confirmed event association | No reviewed field pairs or persisted manual alignment decisions; identical unrelated onset shapes remain possible | Not validated / not implemented as automatic confirmation |
| Clock accuracy and protection philosophy | No trustworthy clock-quality contract, calibrated uncertainty, full cross-relay rule adjudication or causal SLD timeline | Pending |

Repository verification: **411 tests passed**, one upstream TestClient warning;
architecture direct/self-tests, new-code Ruff, JS syntax and diff checks pass.
Stage-A **10,000 cases PASS**, clean p95 **0.4403%**; all-located p95 **11.470%**,
9,929 located and 71 refused. Stage-A grades fault location, **not this new
correlation path**. Its pass does not validate operation philosophy, clock
alignment, TB 854 coverage or field distance accuracy.

Local preview: http://127.0.0.1:8094, isolated
`out/application-operation-preview` data and an empty field registry. The preview
was restarted without reload after the Windows reloader failed to replace its
backend; the active policy was then checked through a new analysis revision.
Earlier services/data remain intact.
The original 8091 process still needs a normal restart to load updated Python;
its restart was blocked by automatic approval review in the preceding milestone.
