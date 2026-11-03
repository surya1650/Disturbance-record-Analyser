# Clear incident report and simple portal — acceptance

Goal: [INCIDENT_REPORT_PORTAL_GOAL_v1.md](INCIDENT_REPORT_PORTAL_GOAL_v1.md).
Review branch: `codex/operator-ui-review`. Qualification uses synthetic records;
no private disturbance records, user screenshot data or settings are committed.
Delivery publication remains **PUSH_PENDING_AUTH**; all implementation is local.

## Result and use

The main portal is **Upload & parse → Analyse → Compare (optional) → Report**.
Upload one COMTRADE capture or ZIP, inspect the parsed waveforms, then select
**Report → Generate report**. Line/end/instrument inputs are requested only by
calculations that need them. One recording can generate an observation report.
Advanced input review, engineering studies and technical exports are secondary.

The primary report has four A4 sheets:

1. Plain summary, classification, method-labelled distance from its named
   reference or a named refusal, source selection and next actions.
2. Per-source R/Y/B phase currents before/during/after, waveform envelopes with
   gaps, region bounds and separately labelled stored fault-window sample RMS.
3. Equivalent per-phase voltage evidence, preserving missing baselines.
4. Recorded signal observations, plain interpretation, uncertainty and glossary.

Each generation saves immutable JSON and self-contained HTML. **Open report**,
**Print / Save PDF**, HTML/JSON downloads and **Saved reports** expose the same
generation. Native browser printing supplies PDF; no server PDF engine is claimed.
The latest20 generations are listed; every generation remains stored. Existing
revision history, original downloads and the old technical report remain available.

For a local checkout with application dependencies installed:

```bash
python -m dranalyser.application serve --port 8091
```

Open `http://127.0.0.1:8091`. Existing application roots may be supplied through
`--root`; do not point a test instance at an active writer's root.

## Evidence and preservation

The adapter reuses existing decoding, automatic/manual source regions, complete
one-cycle RMS, digital observation logic and structured location eligibility.
It does not change DSP, estimators, operational windows or source bytes. Complete
one-cycle RMS medians include DC/harmonics and differ from native fault-window
sample RMS. A whole-record peak is never substituted for fault current. Counts,
real zeros, missing observations and unverified scaling remain explicit. Known
physical units receive readable display prefixes without changing canonical values.

Report selections are recordings, not inferred physical ends. Defaults use the
stored accepted primaries, otherwise up to two recoverable representative sources.
Frozen reviewed-copy relations prevent counting one physical capture twice.
Explicit selections retain exact filenames. Additional recordings/supporting files
and bounded display omissions remain identified in the JSON and incident evidence.

Saved manual timing/mapping/polarity choices require matching CFG/DAT hashes.
Location requires the existing eligible method, incident/revision/model/source
cohort and compatible operational mappings. Legacy prose, stale sources and
provisional models cannot supply a new distance. The known42km E5 case remains
**41.98828243177587km**, with no Z0/source-impedance/time-sync dependency added.
No new field-accuracy or calibrated confidence claim is made.

Signal labels do not prove mechanical breaker movement. Assumed high-active
polarity is labelled; state differences across gaps retain an interval and unknown
transition time. Source clocks remain independent. Saturation/clipping flags are
conditional and do not claim a universal direction of measurement/location error.

The additive API binds metadata, result, bundle, source hashes and saved observation
choices. A write token is required; changed/running revisions cannot publish a stale
generation. Artifact digests are verified on read. New generations do not overwrite
old reports, stored engineering results or recordings.

## Qualification

Qualified runtime: **dcab1ecd8f7b6e888720ac476770ff96099426fc**. The43 runtime
file hashes match the captured browser/PDF source. The final result supersedes
the earlier2238-test run and intermediate print logs. Compact, source-hashed
results are committed in [the evidence JSON](INCIDENT_REPORT_PORTAL_EVIDENCE_2026-11-04.json).

| Check | Result |
| --- | --- |
| Direct architecture self-test and guard | PASS |
| Changed Python Ruff / Node syntax / diff | PASS (9 Python,11 JavaScript files) |
| Whole-repository Ruff |26 inherited findings in untouched files; not a clean gate |
| Stage-A10000 | PASS, cleanp95 .4361%,0 impossible distances without caveat,33.8s |
| Final full pytest | **2239PASS**,28 private-data skips,1 inherited warning,89.97s |
| Actual Chromium13-fixture matrix | **13/13PASS**, exactly4A4 pages each, no clipping/footer/scroll/text overflow |
| Actual API-generation PDFs | **5/5PASS**, exactly4A4 pages each; source-only, paired, reverse order, single, raw counts |
| Final desktop/mobile portal | **PASS**, all workflow/history/immutability/stale-response checks;0page errors |
| Independent wording and visual review | **PASS**, final known42/signals, short-fault and raw-count pages |

Scratch evidence is under `work/qa-incident-report-night-2026-11-03/` (ignored).
Initial rendering defects included five-page baseline output/mobile overflow,
page4 BC/BG footer overlap, and short-fault page2/3 footer overlap. All were
corrected and rechecked. Final18PDFs total72pages; all satisfy bounds. Minimum
visible print text is12px (9pt), table text13.33px (10pt). No font reduction was
used to repair the final short-fault footer overlap.

The matrix includes known42 paired/single recordings, BC/BG/ABCG classifications,
missing ratios/counts, unavailable first-source current, one-cycle short fault,
sample gaps, saturation, absent/unknown signals, and many records/long labels.
Browser checks include upload/parse, cursor analysis, optional comparison,
source-only refusal, physical calculation, generation/open/print/download/history,
source switches, stale saved timings, rejected revision mismatch, held response
after route departure, late attachments and old-report/source-hash preservation.

No authenticated field-patrol truth or absent private corpus is claimed as tested.
No main merge, deployment or environment publication was performed.


## Phase commits and handoff

| Phase | Local commit |
| --- | --- |
| P0 goal/continuation protection |5ab8595 |
| P1 canonical model and measurements |141bbc7 |
| P2 four-page renderer |c497cd7 |
| P3 simple portal and immutable generation API |a65d856 |
| P4 actual-print spacing correction, qualified runtime |dcab1ec |

Final gate commands: `.venv/bin/python scripts/check_architecture.py --self-test`,
`.venv/bin/python scripts/check_architecture.py`, changed-file Ruff, Node syntax,
`git diff --check`, `OPENBLAS_NUM_THREADS=1 .venv/bin/python -m pytest -q`, and
`OPENBLAS_NUM_THREADS=1 .venv/bin/dranalyse stage-a --cases 10000 --workers 4`.
HTTP tests were run with loopback access; no tests were bypassed to avoid the
sandbox's loopback restriction. Full Ruff's26 inherited issues remain explicit.

Final scratch logs: `frozen-pytest.log`, `final-stage-a.log`, `qualified-print.log`,
`qualified-api-print.log`, `qualified-portal.log`, `qualified-portal-extras.log`,
`qualified-runtime-manifest.json` and `QUALIFICATION_RESULTS.md` under the goal's
ignored work folder. Intermediate `final-print-qa.log` is superseded by
`qualified-print.log`. The standalone synthetic example PDF/HTML is under that
folder's `deliverables/`; it is not a private incident or field-accuracy result.

Engineering implementation and qualification are COMPLETE. All owned QA servers
are stopped. This goal's owned continuation was paused and its disabled state
confirmed; no continuing background work is claimed. Remote review HEAD was
read back as52256d102269e6929d69a07081cd828f038688a6. Automatic approval review
rejected public publication twice and requires an actual explicit answer; no
push or alternate publishing path was attempted during this continuation.
Local phase commits are preserved until that publication permission is received.
