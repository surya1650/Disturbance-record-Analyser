# STATUS LEDGER — DR Analyser

Newest entry at the top. One entry per milestone (plan approved, phase merged, audit,
big fix). State plainly what was done, what was run, and what is outstanding. "Built",
"merged" and "verified on real records" are three different states — use the true one.

---

## 2026-09-07 (handoff) - Session closed; requirements written down

**State: committed on `main`, working tree clean, 5 commits ahead of
`origin/main`, NOT PUSHED.** The four feature commits below plus `403d9cd`,
which is this handoff. All authored by R. Surya alone, no AI attribution
trailers.

```
bc759d7  Resolve a record to a line and a terminal from evidence, and pre-fill the form
b0947ed  Make the analyser depend on vendor-neutral settings, and guard the rule
a60d6d9  Cross-check two relays that watched the same fault from the same bus
501f9d7  Add the local analysis workbench, and fix two defects the Sphoorthi records exposed
```

**Gates actually run at `bc759d7`,** not remembered from earlier:

| Gate | Result |
|---|---|
| `check_architecture.py --self-test` | pass |
| `check_architecture.py` (run directly, not piped) | pass |
| `pytest -q` | **295 passed** (229 at session start) |
| `dranalyse stage-a --cases 10000` | **PASS**, clean p95 = **0.4403 %** |
| `ruff check` | 44 findings, all pre-existing, none on a changed line - **not fixed** |

Stage-A came back at 0.4403 % after every one of the four commits. That is the
point: nothing this session was allowed near the estimators, the DSP chain or
the parser maths.

**Documents written this session:**

- `project-docs/OPEN_REQUIREMENTS.md` - **new.** Seven items the analyser needs
  and cannot derive, written as one page so it can be sent to the protection
  wing as it stands. Items 1 to 3 each block finished work.
- `project-docs/NEXT_SESSION.md` - rewritten from scratch. It had become a
  patchwork of in-place edits with stale counts in it.
- `project-docs/LESSONS.md` - three new entries: the OpenBLAS root cause, the
  CFG station name that is not the station, and the relay model that looks
  like an identifier.
- `project-docs/LOCAL_WORKBENCH_PLAN_v1.md` - marked complete, P1 to P4, with
  its two deliberate divergences recorded.

**Deliberately left untouched, so the next session does not "fix" them:** the
`ps=S` block (needs a registry override, never a heuristic); the one-record-
per-terminal signature of `incident_features` / `report.build`; the 44 ruff
findings; the Maradam CT polarity, which is reported and not corrected in
software; and the provisional lengths in every `data/registry/*.yaml`.

**Nothing is ON HOLD or deferred** beyond what `OPEN_REQUIREMENTS.md` lists.

**Other agent:** the `standards/` work was theirs and finished during this
session; it is inside `501f9d7`, whose message says so. Their `RioSettings`
import was repointed in `b0947ed`.

**Next:** pairing (§5.2). Needs nothing from anyone.

---

## 2026-09-07 (resolver) - Records resolve themselves to a line and a terminal

`NEXT_SESSION.md` §6 done, and P4 of the workbench plan with it. The workbench
plan is now complete, P1 to P4.

`registry/assets.py`: `RecordFacts`, `AssetHint`, `Assignment`, `Ambiguous`,
`AssetResolver.resolve(facts, manifest)`, `load_registry(dir)`.
`workbench/resolve.py` pre-fills the assignment form; the operator confirms or
overrides, and both values stay in the manifest so an override is visible.

**Divergence from §6, on purpose:** `resolve()` takes primitives, not a
`Record`. `registry/` imports nothing from the rest of the package and the
guard enforces it; taking a `Record` would reverse the allowed direction. It
also means a manifest alone resolves with no record open.

Weights (**project policy, not standards-derived**): manifest 1.00, path rule
0.60, header 0.50, sibling settings 0.50, electrical 0.30. A candidate needs
0.50 and must beat the runner-up by 0.20. Only a manifest decides alone.

Two rules that came straight out of the real records:

- **A relay MODEL is not an identifier.** Matching `7SA522` would be a
  confident end signal meaning nothing on a fleet where half the relays are
  7SA522. Only the relay id and its configured aliases count.
- **Evidence naming the line but not the end lifts both ends equally**, so it
  can decide the line and never the terminal.

**Verified on the real folder tree**, `drs sphoorthi/`:

| record | resolved | on what |
|---|---|---|
| `garividi-maradam-1/Main-1 D60` | GRV-MRD-1 / R, 0.90 | path rule + ratios; its CFG station name is the useless `Relay-1` |
| `garividi-maradam-1/Main-2 P444` | GRV-MRD-1 / R, 1.10 | header `garividi` + path rule |
| `maradam-garividi-1/Main-1` | GRV-MRD-1 / S, 1.90 | header names MARADAM and LINE 205, plus the ratios |
| `maradam-garividi-1/Main-2` | refused | blocked by the conformance gate |

**And it refuses when it should.** Flatten those into one `garividi/` folder
and the two Garividi records come back "two candidates are too close to call
(GRV-MRD-1/R at 0.90 against GRV-MRD-2/R at 0.90)" - nothing in the path or
header says which of the two parallel circuits they are. The double-circuit
hazard, made concrete instead of guessed past.

New: `data/registry/grv-mrd-1.yaml` and `grv-mrd-2.yaml`. **PROVISIONAL for
distance** - lengths and impedances are typical ACSR Panther, not surveyed.
They exist so the resolver has something to resolve against; the kV and the
CT/VT ratios in them are real, read out of the records.

**Gates:** guard + self-test pass, **295 tests** pass, Stage-A 10,000 cases
PASS at clean p95 = **0.4403 %**, unchanged for the fifth time.

Next: **pairing** (§5.2), now genuinely possible - every record has a line and
a terminal. Remember §7.5: 13 min 24 s of clock spread on one event, so
electrical corroboration comes before any time filter.

---

## 2026-09-07 (settings) - The vendor lock-in is gone; a guard rule keeps it gone

`NEXT_SESSION.md` §4, done. `RioSettings` was imported directly by nine call
sites across `backtest`, `report`, `rules`, `cli`, `standards` and `workbench`,
so a second vendor could not be added without touching all of them.

Now: `registry/settings.py` is the vendor-neutral model, `registry/settings_io/`
holds the importers, and the RIO reader lives in `settings_io/rio.py` behind
`load_settings(path)`. `registry/rio.py` is gone (git mv, history preserved).

**The rule has teeth.** `check_architecture.py` fails the build if anything
outside `registry/settings_io/` imports a module inside it. Structural, not a
list of banned names, so a future `scl.py` or `sel.py` is covered without
editing the guard. Six cases pinned in `--self-test`.

- `Characteristic` is an interface with `contains(z)`. `PolygonChar` (Siemens),
  `MhoChar` (ABB/SEL - standard circle-through-origin maths, `|D|cos(a-theta)`,
  not inferred from any file), and `quad_char()` as a **builder returning a
  PolygonChar** because a quad is a polygon; separate maths would only add a
  way to be wrong.
- k0 dispatches on a recorded convention (siemens_re_xe / abb_kn / sel_k0 /
  impedances / complex_k0) through the converters already in `registry/model.py`.
  An incomplete convention returns None, never a guess.
- `provenance` (path, format, importer, sha256, parsed_at, warnings), `raw`
  (every key seen, untouched) and `unknown` (what could not be determined).
- `load_settings` sniffs by content, and **refuses when two importers tie**
  rather than picking one.

**Verified on the real file**, not only in tests: `DR-1.rio` through the new
path gives k0 = 0.8061 angle -2.417 deg, matching what `dhn-nnr.yaml` records.

**Deliberately not built:** the CSV, XML and TXT importers. §5 still applies -
there is no real sample of any of them, and one written speculatively will look
finished, be wrong, and be believed because it has tests.

**Gates:** guard and its self-test pass, **276 tests** pass, Stage-A 10,000
cases PASS at clean p95 = **0.4403 %**, unchanged for the fourth time.

Next: the `AssetResolver` (§6). The workbench manifest is already the shape it
should fill - the operator's `source: operator` becomes the resolver's
`source: resolver`, for the operator to confirm or override.

---

## 2026-09-07 (P3) - Two relays on one bus now cross-check each other

`workbench/corroborate.py`. Every record the operator put at a terminal is now
analysed, not only the primary: the primary drives the estimators through the
unchanged API, the rest are reduced to fault type, pre-fault I1, fault current
(p90 of the fundamental on the worst phase) and the measured negative-sequence
source impedance `Zs2 = -V2/I2`, and compared. Four findings: XR-01 fault type,
XR-02 load current, XR-03 fault current, XR-04 source impedance.

**Verified on the real case it was built for.** Event 15665, Garividi end:

| record | pre-fault I1 | fault I (p90) | measured Zs2 |
|---|---|---|---|
| GE D60 (primary) | 643.6 A | 727.8 A | 155.97 ohm at 9.7 deg |
| MiCOM P444 (corroborating) | 648.1 A | 749.2 A | 21.68 ohm at 84.6 deg |

The currents agree to under 3 %, so XR-02 and XR-03 correctly stay silent and
the disagreement is localised to the **voltage** input: XR-04 fires with "a
factor of 7.2 and 75 degrees". Before P3 this was invisible - it depended
entirely on which of the two files was passed as `--R`. The Maradam end
measures 1750.6 A against Garividi's ~730 A, consistent with the fault sitting
nearer Maradam.

**Divergence from the plan, recorded deliberately.** The plan proposed changing
`incident_features` and `report/build` to key on a list per terminal. Not done:
those are analytical surface and changing them for a presentation feature risks
moving a number. The cross-check lives entirely in `workbench/`.

Every threshold in `corroborate.py` is **project policy, not standards-derived**,
and the module says so. A `Zs2` whose own scatter exceeds 10 % is not compared
at all, so a noisy measurement cannot manufacture a finding.

**Gates:** guard passes, **263 tests** pass, Stage-A 10,000 cases PASS at clean
p95 = **0.4403 %** - unchanged for the third time this session, which is the
whole point.

---

## 2026-09-07 (workbench) - P1 and P2 of the local workbench built and verified

`project-docs/LOCAL_WORKBENCH_PLAN_v1.md`, P1 and P2 done, P3 and P4 not
started. Approved with the recommended defaults: `127.0.0.1` only, bundles
persist under `out/bundles/`.

**Gates:** 256 tests pass (10 new in `tests/test_workbench.py`). Stage-A 10,000
cases PASS at clean p95 = **0.4403 %** -- byte-identical to before the work,
which is the point: P1 and P2 touch no analytical code.

**New:** `src/dranalyser/workbench/` (`bundle.py`, `incident.py`, `pages.py`,
`server.py`), `src/dranalyser/cli/wb.py`, two CLI subcommands:

    dranalyse bundle <folder-or-zip>     describe one incident, write the manifest
    dranalyse workbench --port 8090      upload -> declare ends -> one incident page

**Verified end to end on real records**, not just in tests: a zip of all four
event-15665 records uploaded through the browser produced a bundle listing all
four (three usable, the `ps=S` MARADAM recorder shown blocked with its BLOCK
flag), the assignment was declared, and one incident page came back with the
7SA522 at S, the D60 at R, the P444 listed as corroboration and the blocked
record listed as excluded. Assigning two primaries to one end was refused with
HTTP 400 and the reason, not silently resolved.

**Root cause found for two long-standing environment failures.** The Stage-A
`BrokenProcessPool` and the two `test_ml.py` failures are one thing: OpenBLAS
spawning a thread per core in every worker process and exhausting memory. With
`OPENBLAS_NUM_THREADS=1` everything passes multi-worker and Stage-A takes 30 s
instead of 111 s. This supersedes the earlier "use `--workers 1`" advice.

**Not done and deliberately so:** `check_architecture.py` still reports two
ratchet errors, both on `src/dranalyser/standards/` -- the concurrent agent's
in-flight work, not touched. Every budget for a file this session changed was
bumped; none of theirs were.

---

## 2026-09-07 (plan parked) - Local analysis workbench, v1 plan

`project-docs/LOCAL_WORKBENCH_PLAN_v1.md`. Requested: a localhost page where DR
files are uploaded and analysed by hand.

Shape: §2.4 forbids one report per file, so the unit is a *bundle* (a set of
files declared by the operator to be one incident), not a file. Four phases -
P1 bundle+manifest with no web, P2 the stdlib HTTP workbench, P3 more than one
record per terminal, P4 the AssetResolver hand-off (not built here).

Deliberate deviation from §12 recorded in the plan: stdlib HTTP and
server-rendered HTML instead of FastAPI + React + Docker, because §12's stack
assumes Postgres/MinIO/Celery which do not exist, and §12 also requires
air-gap capability. No new runtime dependency. Analysis code stays free of any
web framework so FastAPI can sit on the same objects later.

Four open questions in §9 of the plan; the one that changes the build is
whether the server must be reachable from the substation LAN (it would then
need authentication) or stays on 127.0.0.1.

---

## 2026-09-07 (latest) - Sphoorthi records verified; two parser/CLI defects fixed

**State:** 231 tests pass, architecture guard passes, Stage-A 10,000 cases PASS
(clean p95 = 0.4403 % against 0.5 %). Still NOT verified against a real two-ended
pair - but the records to do it with now exist locally, and what blocks it is the
line constants, not the data. Full detail in `NEXT_SESSION.md` §2b.

**What arrived:** `drs sphoorthi/` (local only, gitignored), 11 distinct records
covering 3 events at 2 ends each, across 4 vendors new to the evidence base -
GE D60, MiCOM P444, ABB REL670, Siemens 7SA522. All 11 parse; all 11 now map.

**Verified, not merely built:**
- Pairing by electrical corroboration works on real records. Event 15665: three
  relays measure 725.9 / 732.1 / 719.5 A pre-fault and all call it CG. Event
  15662: 331 A and 329 A at the two ends. Trigger times spread **13 min 24 s**
  across event 15665's four relays, so time-first pairing would have lost it.
- The measurement chain agrees across vendors. Measured `Zs2 = -V2/I2` at the
  Garividi bus on event 15662: `1.67 + j10.28` ohm (P444) against
  `2.61 + j10.27` ohm (REL670). Needs no line constants.
- The `ps=S` block on five records is correct AND the data behind it is
  provably primary: pre-fault RMS 127,005.6 V against 220 kV / sqrt(3) =
  127,017 V, and the identical relay at the far end declares `ps=P` with the
  same `a` constants. Evidence is in `NEXT_SESSION.md` §2c. Do not "fix" this
  with a heuristic.

**Fixed:**
1. `inspect` and `verdict` called `analyse()` on a record the conformance gate
   had blocked and died with `KeyError: 'I1'` on the REL670. Both now refuse.
   Swept the siblings: `locate`, `report` and `backtest` already gated
   correctly - the earlier reading of `backtest.py:308` as ungated was wrong,
   it checks `o.blocked` and continues at line 303.
2. `map_channel` / `detect_phase_naming` anchored the phase match at the start
   of the channel id, so ABB's `LINE1_A_IL1` and `LINE1_UL1` mapped to nothing
   and the whole record blocked as `CH-MISSING`. Now falls back to the last
   separator-delimited token, tried after the whole id and the `ph` field so no
   existing mapping can change, and only the *last* token so the D60's RMS
   channel `SRC 1  Ia Mag` still stays unmapped. Two regression tests added.
3. `.gitignore` covered `*.cfg` / `*.dat` but not the nine `.zip` files that came
   with the records. They were stageable on a public repo. Now `drs */`, `*.zip`,
   `*.ZIP`.

Budgets bumped deliberately in the same commit: `cli/commands.py` 550 -> 557,
`comtrade/parser.py` 467 -> 485. No `--reseed`.

**Outstanding, and all of it needs an answer from the wing, not code:**
1. Line constants for Garividi-Maradam LINE 205 / LINE 206 - length, conductor,
   Z1, Z0, and the zero-sequence mutual coupling. **This is the single item
   blocking the first real two-ended validation.** E5 cannot recover the line
   reactance from the two-ended data alone; the algebra is in §2b.
2. The CT star-point convention at Maradam. The 7SA522's negative-sequence
   polarity is inverted relative to the Garividi relays (`Zs2` at -167.1 and
   -173.3 deg against +75.7 to +84.6 deg). A flipped CT is silent and mirrors
   the answer.
3. The relays' own fault-locator output for events 15662 and 15665.
4. The corridor is double-circuit and both events are ground faults. Zero-
   sequence mutual coupling is unmodelled and `Line` has no field for it.
5. The GE D60 disagrees with the P444 at the same bus on event 15665 (`Zs2`
   155.97 ohm at 9.7 deg against 21.68 ohm at 84.6 deg) on the same 305-310 A
   of I2, so the disagreement is in V2. Not diagnosed.
6. The 400 kV event 15251 is parked: both ends block on `RATIO-PS`, and the
   two ends disagree on fault type.

**Also noted:** Stage-A's process pool dies with `BrokenProcessPool` at the
default worker count on this machine. Reproduces on a clean `git stash` of
`src/`, and does not happen at `--workers 2` or `--workers 4`. Environmental,
not a defect in `stagea.py`. Use `--workers 1` (111 s for 10,000 cases).

Ruff reports 44 findings under a freshly installed newer ruff, all pre-existing
and none on a changed line. Deliberately not touched.

---

## 2026-09-07 (later) - Items 1-6 built, tested and pushed

**State:** pushed through commit `0a42087`. 229 tests pass, architecture guard passes.
Still NOT verified against a real two-ended pair - none exists in the corpus.

Built this session, in order:
1. `.rio` settings reader - zone polygons, line angle, RE/RL and XE/XL, source
   impedance, and the backup O/C / E/F stages. Removes most of the registry's
   longest-lead-time item, and carries what the relay is ACTUALLY running.
2. Conclusions engine - 25 rules as YAML data, whitelisted AST evaluation, and a
   `requires` clause so a rule whose channel was never mapped reports NOT EVALUABLE
   instead of passing.
3. Zone-decision back-test - grades the analyser against the relays' own trip
   decisions. Needs no line length, no far end, no patrol result.
4. Two-page incident report - self-contained HTML, inline SVG, real zone polygons.
5. Ground-truth capture - SQLite store, stdlib capture form, accuracy dashboard,
   Tier-2 gate counter.
6. Stage-A acceptance sweep - 10^4 to 10^5 cases.

**Stage-A result, 100,000 cases: PASS, clean p95 = 0.465 % against 0.5 %.** Thin
margin, not comfortable; stable across seeds (0.419-0.468). Zero impossible results
reached the output without a caveat.

**Biggest known weakness: CT saturation.** Saturated cases average 10.7 % error
against 0.12 % clean. Detected and down-weighted, NOT compensated. This is the next
real piece of physics to do.

Defects found and fixed by widening the sweep (none findable at 40 cases):
- `classify_fault` crashed on non-finite phasors - 6 % of cases.
- E5 returned roots like m = 6.7 as locations; now declines outside +/-0.5 pu.
- The ensemble reported those as distances; now refuses, and warns rather than
  naming a tower for the 1.0-1.5 pu band.
- A two-ended estimate now needs a better WEIGHT, not just a better residual, to
  override single-ended ones - a saturated CT satisfies E5's magnitude equality at
  a wrong m with a small residual.

Field findings from the real records, for APTRANSCO action rather than code:
- **Main-1 VT cannot pass zero sequence** (575 V of V0 against 1670 A of I0, where
  Main-2 saw 34 kV). Explains Main-1 tripping Z2 while Main-2 tripped Z1. CHECK THE
  VT SECONDARY CONNECTION AT DHONE.
- **IE>> carries the not-set sentinel** - the earth-fault backup is disabled.
- **7.1 kA fault against a 1600 A I>> pickup produced no O/C pickup** - is that
  stage in service? Settings export and recorded behaviour disagree.
- **Main-1 has no carrier-send channel mapped**, so CR-01, the highest-value rule,
  cannot be evaluated from it anywhere in the corpus.
- Relay clocks in one bay differ by 1418 s.

Outstanding, in priority order:
1. A genuine two-ended pair from the Nandyal end. Nothing substitutes for it.
2. Real Z1/Z0/length/tower schedule. `data/registry/dhn-nnr.yaml` is PROVISIONAL.
   Open question for Surya: is Dhone-Nandyal about 27 km? The Z1 reach of 8.75 ohm
   primary implies it. If the line is 50 km, that relay is set to ~44 % and
   underreaching badly.
3. CT saturation compensation.
4. Not built: pairing, transport, edge collector.
5. Not handled: distributed-parameter model for long lines, three-terminal lines.
   Series-compensated lines are detected and refused, not approximated.

Process note: three separate times a patch script wrote broken escapes into source
(literal backspace bytes for ``, a literal CR for ``). They are invisible in an
editor and in grep. Do not patch source with shell heredoc + Python string
replacement; use the editor tools.

---

## 2026-09-07 - First PR built, tested and pushed

**State:** committed and pushed to https://github.com/surya1650/Disturbance-record-Analyser
(branch `main`, commit `a4897d1`). 141 tests pass. `scripts/check_architecture.py` passes.
**Not yet verified against a real two-ended pair** - none exists in the corpus.

Built (`src/dranalyser/`): own COMTRADE parser (1991/1999/2013, ASCII/BINARY/BINARY32/
FLOAT32, .CFF, nrates 0/1/n, P/S scaling); conformance gate (13 checks); DSP chain
(frequency tracking, mimic filter, sliding full/half-cycle DFT, sequence, superimposed,
inception, fault-type classification, CT saturation, ADC clipping, window selection);
estimators E1-E5 and the E6 ensemble; synthetic two-source phase-domain fault generator
(the oracle); registry with vendor k0 conversions; CLI (`locate`/`inspect`/`selftest`/
`template`); ML tiers 1/2/3.

Verified: Stage-A (§13) PASS - mean 0.030 %, p95 0.092 %, max 0.152 % of line length,
through the full DSP chain with 1418 s clock skew, CVT transient, decaying DC, ADC
quantisation, 1000 Hz vs 1200 Hz. Parser verified on all four real DHONE records.

**Field finding from the real records - needs action, not code.** Main-1 measures 575 V
of V0 during an A-G fault carrying 1670 A of I0; Main-2, same bay, same fault, measures
34 kV. Main-1's VT secondary cannot pass zero sequence, so its ground-loop voltage is
missing V0 and it reports the fault ~13 % of the line too far out - consistent with
Main-1 tripping in Zone 2 while Main-2 tripped in Zone 1. The analyser now detects this
(`VT-NO-ZERO`) and refuses the single-ended ground-loop calculation at that terminal
rather than answering wrongly. **Check the Main-1 VT connection at DHONE.**

Also confirmed on real records: relay clocks in one bay differ by 1418 s; pre-fault load
sits in 11 (Main-1) and 7 (Main-2) ADC counts; no clock-quality code anywhere, so E4 is
permanently gated off in this fleet; Main-1 has no carrier-send digital channel mapped,
so rule CR-01 cannot be evaluated from it.

Outstanding, in priority order:
1. Recover a genuine two-ended pair (Nandyal end). Everything in §7.2, §13 Stage B and
   the §14 proof depends on it. Organisational lead time, start now.
2. Real Z1/Z0/length/tower schedule for DHN-NNR - `data/registry/dhn-nnr.yaml` is
   PROVISIONAL and marked so.
3. Not built: pairing, transport, edge collector, rules engine, two-page PDF report.
4. Not handled: distributed-parameter model for long lines, three-terminal lines.
   Series-compensated lines are detected and refused, not approximated.

Real records, the .rio settings export and event PDFs are NOT committed - the repo is
public. Tests needing them skip cleanly.

---

## 2026-09-06 — Toolchain, guard rails and agent context installed

**State:** repo is NOT a git repository yet; everything below is uncommitted on disk.

Added (this session, by Claude):
- `CLAUDE.md` — project instructions: binding §2 constraints, layout, hard rules,
  definition of done, conventions, and how R. Surya works.
- `.claude/skills/` — 10 skills (+ `README.md` index): `spec-constraints`,
  `fault-location-math`, `comtrade-corpus`, `record-investigation`, `release-check`,
  `same-defect-sweep`, `still-not-showing`, `plan-first`, `plan-review`,
  `session-handoff`.
- `pyproject.toml` (setuptools src-layout, `dranalyse` entry point, ruff py311/120/E4-E7-E9-F-B,
  pytest with `pythonpath=["src"]`, `corpus`/`slow` markers, RuntimeWarning-as-error),
  `requirements.txt`, `requirements-dev.txt`, `.gitignore` (records excluded except
  `tests/corpus/`).
- `scripts/check_architecture.py` + `scripts/architecture_budgets.json` — purity of the
  maths core, no third-party COMTRADE parser, no ML in the fault-location path, no
  traveling-wave module, import-direction layering, estimators must return `Estimate`,
  file-growth ratchet seeded at exact current line counts (23 files).
- `project-docs/STATUS_LEDGER.md`, `project-docs/LESSONS.md`.

Not touched: `src/`, `tests/`, `data/`, `PROJECT_CONTEXT.md`, `HANDOFF_PROMPT.md`, and the
legacy prototypes (`dr/`, `DR1/`, `DR 9-4-2026`, `DR & Events 9-4-2026`) — another agent
(Qodo) is actively writing `src/` and `tests/`.

**Gates as of this session:**

| Gate | Result |
|---|---|
| `python scripts\check_architecture.py --self-test` | pass |
| `python scripts\check_architecture.py` | pass (after allowing `comtrade -> dsp` and `ml -> dsp/synth`, which the existing code legitimately uses) |
| `python -m ruff check .` | **18 errors** in `src/` and `tests/` (pre-existing, deliberately not fixed — mostly unused imports). `scripts/` is clean. |
| `python -m pytest -q` | **141 passed** at 21:5x. Earlier in the same session two `tests/test_real_records.py` tests failed (the two relays located the same fault 13.07 % of line / 8.102 km apart, and their inception instants disagreed); the other agent fixed them mid-session. |

Budgets were reseeded twice while the other agent's files grew under the gate — the
ratchet works, but with zero headroom it will keep firing while `src/` is under active
construction. During the §14 first-PR build, `--reseed` after intentional growth is the
right move; the ratchet becomes a real constraint once §14 lands.

**Outstanding:**
1. `git init` and a first commit — nothing is under version control yet.
2. The two real-record failures above (owned by the other agent's current work; they are a
   sample-rate / P-S-convention / inception-detection question, see `record-investigation`).
3. 19 ruff errors to clear once the other agent's edits settle.
4. `tests/corpus/` is empty — every corpus-marked test skips, so no claim about real
   vendor files is currently supported.
5. §17 [OPEN] items 1–7 in `PROJECT_CONTEXT.md` are still unanswered; item 8 ("what is in
   E:\dr analyser") is now answered by the working tree itself.
