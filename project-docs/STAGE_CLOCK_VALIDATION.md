# Fault-stage association and clock-quality contracts

Implemented locally in September 2026; not committed or pushed. This milestone
adds advisory observations and source-bound reviewer associations to the all-relay
evidence, browser, frozen navigator and revisioned HTML report. It does not change
estimator equations, DSP windows, rule inputs or recording samples. E5 remains the
unsynchronized primary path; E4 receives no new authorization from these fields.

## Local stage observations

`dsp/stages.py` screens cycle blocks of the existing phase-current fundamental
magnitudes against the existing pre-inception reference. The method reports
elevated phase patterns, not an independently classified physical fault type.
Initial, evolving and renewed-current candidates remain distinct. A renewed
candidate is labelled reclose only with a mapped observed AR_CLOSE edge between
the prior elevated interval and the new boundary support. An initially active
close indication does not supply that edge. No elevated current does not prove
clearing or breaker state.

Each interval retains its original local bounds, native sample start/stop,
trigger-relative bounds (or unavailable), phase pattern, uncertain boundary
support and open capture edges. Raw digital markers, including repeated trips,
retain source labels, mapping states and original active intervals separately.
Short or nonfinite blocks remain uncertain; the partial final cycle is retained
as an uncertain observation rather than appended to a stable stage.

Project screening policy (not a protection pickup or standard criterion):
two captured pre-inception cycles; cycle-block median fundamental magnitudes;
rise greater than the largest of 20% of largest pre-inception phase magnitude,
25% of largest phase rise and a 1e-6 A numerical floor; two consecutive complete
blocks for a stable pattern. At most 512 intervals and 256 pair combinations are
published; exceeding either limit withholds the entire affected inventory/matrix.
Single-rate, finite, uniform sample times and all three current references are
required. Unavailable analog stage evidence does not erase raw digital evidence.

The boundary ranges are sample/DFT support, **not calibrated physical-inception
uncertainty**. Subcycle stages, unchanged-magnitude phase-angle evolution, weak
infeed, changing source contribution and stages without elevated current can be
missed. Saturation/clipping findings retain observations but withhold association.
The existing saturation screen may flag an evolving-fault transition; this
milestone does not distinguish every such transition from actual CT saturation.

## Same-stage association

Same-terminal pairs appear before cross-terminal pairs. Stage candidates bind
to exact recording hashes and current mapping snapshots, retaining all candidate
alternatives. Repeated phase patterns are ambiguous and are never paired by shot
number or ordinal position. A unique initial pattern with the existing advisory
onset-shape candidate is still only a candidate. Other matching patterns require
review; different patterns do not identify a defective relay.

Optional assignment `stage_review` fields:

```json
{
  "inventory_hash": "<64 lowercase hexadecimal characters from stages.inventory_hash>",
  "reviewer": "Reviewer's declared name",
  "reason": "Supporting incident/circuit/stage evidence",
  "same_incident": true,
  "same_circuit": true,
  "stage_identity": true,
  "groups": {"stage-1": "initial-fault", "stage-4": "reclose-1"}
}
```

Group labels are case-sensitive letters/digits/underscores/hyphens, 1-80
characters, unique within a record. Only stable elevated-pattern intervals can
be declared. The inventory hash binds the record hash, incident, line ID,
terminal, protection system, mapping, policy, boundaries and signal provenance.
Analytical primary/corroborating role is deliberately excluded. Any changed
bound input invalidates the review; missing confirmations and quality failures
also withhold it. Malformed reviews fail shared intake validation.

Corresponding valid groups at two relays produce `reviewed association` and
`confirmed: true` **under reviewer declarations only**. Different reviewed groups
remain separate. Partial reviews leave other candidates unresolved. Withdrawal
removes the declaration in a new revision. Same-terminal association requires
declared Main-1/Main-2 identity. No authenticity of the reviewer, independently
verified field identity, common clock or event order follows from this review.
All associations keep `applied: false`; neither location nor operating-time
rules consume the groups. The UI obtains the preceding completed analysis for
review and recomputes/validates its fingerprint in the new worker run.

## Clock evidence

The parser now retains all four CFG timing fields: `time_code`, `local_code`,
`tmq_code`, `leapsec`. Previously local_code was dropped and leapsec was lost
when constructing the Record. Original sample timestamps and datetime objects
are unchanged. CFG/DAT and CFF use the same assembly path.

`dsp/clock_quality.py` distinguishes absent/unsupported codes, source-reported
locked status, source-reported unlocked error bounds, and clock failure. Code 0
does not supply a numeric accuracy; F reports failure; C/D/E and malformed
multi-character values are not interpreted. Supported 1-B bounds range from
1 ns to 10 s relative to the synchronizing source. Leap-state declarations
remain separate. Source clock accuracy, continuous lock through the capture,
UTC conversion and event/stage identity are not verified by these codes.

Thus `reported_error_bound_s` can be numeric while `uncertainty_s` remains null,
`verified`, `alignment_eligible` and `applied` remain false. No trigger-zero
alignment, lag application, carrier delay or cross-record causal order is
inferred. The original clock time-basis declaration and recording hash remain
visible. Nanosecond code bounds do not establish nanosecond timestamp parsing.

Primary references checked 2026-09-10:

- [IEEE PSRC WG H4, 2013 COMTRADE summary](https://www.pes-psrc.org/kb/report/1014.pdf),
  slides 9-12: timing fields, quality examples and leap indicators.
- [Grid Protection Alliance GSF COMTRADE Schema](https://github.com/GridProtectionAlliance/gsf/blob/master/Source/Libraries/GSF.COMTRADE/Schema.cs),
  `TimeQualityIndicatorCode`: cross-check of the complete numeric code mapping.
  The application imports no third-party COMTRADE parser.

## Validation and remaining work

Independent piecewise sinusoidal waveform fixtures define A, AB, quiet and
renewed-A states, with separate raw reclose/trip channels, unequal sample rates
and large free-running clock offsets. They validate the observation contract,
not a complete evolving-fault network model. Combinatorial review tests explicitly
isolate quality gating; other tests exercise saturation/clipping refusal.
Integration tests cover four relays, source persistence, reviewed grouping,
identity-change invalidation, role independence, HTML escaping and immutable
previous reports/navigator evidence.

- Full pytest: **573 passed**, one upstream Starlette TestClient deprecation
  warning, 173.19 seconds. **64 tests added** across stage observations, clock
  quality, review contracts and application revision integration.
- Architecture guard and self-tests passed; focused Ruff and JavaScript syntax
  checks passed; existing 16 navigation-model and 10 native-cursor assertions pass.
  `git diff --check` passes with existing Windows LF/CRLF notices.
- Stage-A **10,000 PASS**, 87.9 seconds: clean p95 **0.4403%**;
  9,929 located / 71 refused; all-located p95 **11.470%**; CT-saturated
  mean **11.270%**, p95 **53.902%**; no impossible m without a caveat.
  This remains the existing scalar regression, not a stage-aware electrical oracle.
- Headless Edge passed four-relay stage-review entry, missing-input refusal,
  confirmation withdrawal/restoration across four revisions, independent relay
  navigation, escaped source/reviewer text, script-free HTML export and preservation
  of revision 1. Evolving/reclose intervals and quality-based association refusal
  were checked in a second four-relay synthetic incident. No JavaScript errors or
  mobile page overflow. Desktop/mobile screenshots were visually inspected.
  A first QA-helper run toggled an already-open panel closed; the helper was fixed
  and the same incident resumed successfully. No application change was needed.
- Read-only fingerprints of all revision rows and saved report/navigator artifacts
  in **nine pre-existing application roots** match the pre-preview snapshot.

## Current application and local QA

Updated backend: http://127.0.0.1:8101, root `out/application-stage-preview`,
registry `out/evidence-qa-registry`, one embedded worker. All earlier servers and
original data remain untouched. No process was stopped, and nothing was committed,
pushed, reset or stashed. Static browser assets are shared across servers; old
backends do not advertise stage review and show the missing-evidence fallback.

- Reviewed initial-stage/clock preview, revision **4**, four synthetic relays:
  http://127.0.0.1:8101/#incident/bdb558585eb04fc9a026501964d0ebd2
- Evolving/reclose observation preview, revision **1**, four synthetic relays:
  http://127.0.0.1:8101/#incident/f1ad466912fa430b84b97adc02d91b0e
  The existing saturation screen flags the evolving transition, so its association
  is deliberately withheld while all observed stages remain visible.

Open **Event and channel navigator**, then **Fault stages and clock quality**.
Use **Review & rerun** and **Review corresponding fault stages** to declare groups
against the preceding completed inventory. Save identity/mapping changes before
reviewing the recomputed stages. Input changes invalidate old reviews.

Local evidence: `out/qa/stage-preview-results.json`, `stage-preservation-before.json`,
`stage-review-desktop.png`, `stage-review-mobile.png`, `stage-clock-desktop.png`,
`stage-clock-mobile.png`, `stage-evolving-desktop.png`, `stage-export.html`.
The browser helper `out/qa/check_stage_preview.py` **creates synthetic incidents**;
use `stage_preservation.py` for the read-only preservation check. Logs:
`out/stage-preview.log` and `out/stage-preview.err`. At launch the wrapper PID was
19728 and server PID 51312; recheck runtime state instead of relying on saved PIDs.

## Next bounded work

Still required before feeding this contract into electrical estimation: an
independent evolving/reclose network oracle, reliable physical-stage boundaries,
per-stage quality and analysis-window eligibility, and validated estimator gating.
Verified UTC/source uncertainty, clock drift and stage-aware correlation remain
future work. Existing legacy analytical windows can span incompatible stages;
the new evidence flags multiple/uncertain interval overlap but does not repair or
certify those windows. Full physical breaker interpretation, field settings,
TB 854 validation and field fault-location oracles remain incomplete.
