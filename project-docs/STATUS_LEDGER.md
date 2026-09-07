# STATUS LEDGER — DR Analyser

Newest entry at the top. One entry per milestone (plan approved, phase merged, audit,
big fix). State plainly what was done, what was run, and what is outstanding. "Built",
"merged" and "verified on real records" are three different states — use the true one.

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
