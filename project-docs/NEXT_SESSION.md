# Context for the next session

Written 2026-09-07 at commit `bc759d7`, on `main`, working tree clean,
**4 commits ahead of `origin/main` and not pushed**.

Read this, then [`PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md) §2 (binding
constraints) and the "What is different from the brief" section of
[`README.md`](../README.md). Everything blocked on the protection wing is in
[`OPEN_REQUIREMENTS.md`](OPEN_REQUIREMENTS.md), written so it can be sent to
them as it stands.

---

## 1. Get running in three minutes

```powershell
cd "E:\dr analyser"
pip install -e ".[dev]"
$env:OPENBLAS_NUM_THREADS=1        # NOT optional, see below

python scripts\check_architecture.py --self-test
python scripts\check_architecture.py     # run it DIRECTLY, never through a pipe
python -m pytest -q                      # 295 tests
dranalyse stage-a --cases 10000          # PASS, clean p95 = 0.4403 %

dranalyse workbench --port 8090          # then open http://127.0.0.1:8090/
```

**`OPENBLAS_NUM_THREADS=1` is not optional on this machine.** Without it,
Stage-A dies with `BrokenProcessPool` at the default worker count and two
`tests/test_ml.py` cases fail with *"OpenBLAS error: Memory allocation still
failed after 10 retries"*. One root cause, not two: every worker process
spawns an OpenBLAS thread per core and memory runs out. Neither is a code
defect — both reproduce on a clean `git stash` of `src/`. With it set,
everything runs multi-worker and 10,000 cases take 30 s instead of 111 s at
`--workers 1`. The p95 is identical either way; the sweep is seeded, not
worker-dependent.

Real records are **not** in the repository (it is public). They live locally
under `DR & Events 9-4-2026/`, `DR 9-4-2026/` and `drs sphoorthi/`. Every test
that needs them skips cleanly, so a fresh clone still runs green.

---

## 2. What is true, and what is merely built

Three different states, never blurred: **built**, **passes the synthetic
oracle**, **verified on a real record**.

### Verified on real records

- The COMTRADE parser reads all fifteen real records across **six vendors** —
  Siemens 7SA522, GE D60 (binary), MiCOM P444, ABB REL670 (binary) and two
  1999-era bay recorders. `rev_year` values of 1997 and 2001 (neither valid),
  `nrates=0` with the rate only in the DAT timestamp column, a trailing DOS
  `0x1A`, `ps=P` against `ps=S`, and vendor-prefixed channel ids.
- The measurement chain is validated against the relays' **own zone
  decisions**: Main-2 computes into Zone 1 and tripped Zone 1; Main-1 computes
  into Zone 2 and tripped Zone 2.
- **Cross-vendor agreement at one bus.** On event 15662 the P444 and the
  REL670 at Garividi measure `Zs2` as `1.67 + j10.28 Ω` and `2.61 + j10.27 Ω`
  — 0.5 Ω and 5° apart, two vendors, no line constants involved.
- Breaker timing agrees between two independent relays on one fault: phase A
  opens at 78.1 ms and 78.5 ms, measured at 1200.5 Hz and 1000 Hz.
- Settings import: the real `DR-1.rio` gives k0 = 0.8061 ∠ −2.417°, matching
  what `dhn-nnr.yaml` records.
- Asset resolution: the table in §4 lists what resolved and what refused.

### Passes the synthetic oracle only

- **Fault location.** Stage-A passes 10,000 cases at clean p95 = **0.4403 %**
  against a 0.5 % criterion. Thin margin, stable across seeds and worker
  counts. Re-run after every change this session; it has not moved a digit.
- **CT saturation is the dominant unhandled error source**: 10.7 % mean error
  against 0.12 % clean. Detected and down-weighted, **not compensated**. The
  largest remaining accuracy gap.

### Not proven at all

- **The two-ended path has still never run on real data.** The records exist
  now — both ends of two faults — and everything around them is built. What is
  missing is the line constants: `OPEN_REQUIREMENTS.md` item 1, which includes
  the algebra showing they cannot be derived from the measurements.
- Every line YAML in `data/registry/` is **PROVISIONAL for distance**.
  `dhn-nnr.yaml` carries typical ACSR Zebra values; `grv-mrd-1.yaml` and
  `grv-mrd-2.yaml` typical ACSR Panther. Their kV and CT/VT ratios are real,
  read out of the records. Absolute distances from any of them are not
  operational.

### Not built

Pairing (§5.2), transport, the edge collector, CT saturation compensation.

### Not handled

Distributed-parameter model for long lines, three-terminal lines, and
**zero-sequence mutual coupling between the two circuits of a double-circuit
corridor** — which the Garividi–Maradam records need. Series-compensated lines
are detected and refused, not approximated.

---

## 3. The Sphoorthi records — the first real two-ended data

`drs sphoorthi/` arrived 2026-09-07 (local only, gitignored). Eleven distinct
records, no byte-duplicates, three events at two ends each:

| Event | End A | End B |
|---|---|---|
| 15665, 20/08/2026 — Maradam LINE 205 | Garividi: GE **D60**, MiCOM **P444** | Maradam: Siemens **7SA522**, "MARADAM" recorder |
| 15662, 20/08/2026 — Maradam LINE 206 | Garividi: **P444**, ABB **REL670** | Maradam: **7SA522**, "MARADAM" recorder |
| 15251, 10/08/2026 — 400 kV Kalpaka–Gajuwaka | Gajuwaka Main-1 | Kalpaka Main-2 (two records, 20 s apart) |

**The pairing was corroborated electrically, not by folder name.** On 15665
three usable relays measure 725.9 / 732.1 / 719.5 A pre-fault and all call it
CG; Maradam feeds 2857 A against Garividi's 2019 A, so the fault is nearer
Maradam. On 15662 the two ends measure 331 A and 329 A pre-fault, with
15,684 A at Garividi against 6871 A at Maradam.

**Trigger times spread 13 min 24 s across event 15665's four relays.** Any
pairing that filters on time before corroborating electrically throws this
event away. Field confirmation of the clock warning in §7.5 of the old notes.

**Garividi–Maradam is a double-circuit corridor** (LINE 205 and LINE 206), and
both recorded events were ground faults nine minutes apart on the same
morning. Zero-sequence mutual coupling is a first-order error source for
single-ended ground-fault location and is not modelled.

The 400 kV event is **parked**: both ends block on `RATIO-PS`, the two Main-2
records are 20 s apart with the second showing no fault, and the two ends
disagree on fault type (ABC against CG).

---

## 4. What was built on 2026-09-07

Four commits on `main`, all gates green after each.

### `501f9d7` — the local workbench, and two defects the records exposed

- `inspect` and `verdict` called `analyse()` on a record the conformance gate
  had blocked and died with `KeyError: 'I1'` on the REL670. Both now refuse.
  `locate`, `report` and `backtest` already gated correctly.
- `map_channel` / `detect_phase_naming` anchored the phase match at the start
  of the channel id, so ABB's `LINE1_A_IL1` mapped to nothing and the record
  blocked as `CH-MISSING`. They now fall back to the **last**
  separator-delimited token, tried after the whole id and the `ph` field, so
  no existing mapping can change — and the D60's RMS channel `SRC 1  Ia Mag`
  still stays unmapped rather than colliding with `F1-IA`.
- `dranalyse workbench --port 8090` and `dranalyse bundle <folder-or-zip>`.
  §2.4 forbids one report per file, so the unit of upload is a **bundle** — a
  set of files the operator declares to be one incident — and there is
  deliberately no route that analyses a single file. Every uploaded file
  appears on the incident page: used, corroborating, blocked, duplicate or
  unreadable. Full plan and its divergences in
  [`LOCAL_WORKBENCH_PLAN_v1.md`](LOCAL_WORKBENCH_PLAN_v1.md).

### `a60d6d9` — two relays on one bus cross-check each other

`workbench/corroborate.py`. Every record at a terminal is analysed; the
primary drives the estimators, the rest corroborate. Four findings: XR-01
fault type, XR-02 load current, XR-03 fault current, XR-04 measured `Zs2`.
Thresholds are **project policy, not standards-derived**, and a `Zs2` whose
own scatter exceeds 10 % is not compared at all, so a noisy measurement cannot
manufacture a finding.

It immediately found a real one: at Garividi on 15665 the D60 and P444 agree
on current to under 3 % but their `Zs2` differs by a factor of 7.2 and 75°.
Before this it depended entirely on which file was passed as `--R`.

### `b0947ed` — vendor-neutral settings

`registry/settings.py` is the model, `registry/settings_io/` holds the
importers, `registry/rio.py` is gone. Nine call sites now name
`ProtectionSettings` and `load_settings`; none names a vendor.

`check_architecture.py` **fails the build** if anything outside
`registry/settings_io/` imports a module inside it. Structural, not a list of
banned names, so a future `scl.py` is covered without editing the guard. Six
cases pinned in `--self-test`.

`Characteristic` is an interface with `contains(z)`: `PolygonChar`, `MhoChar`
(standard circle-through-origin geometry), and `quad_char()` as a **builder
returning a PolygonChar** — a quad is a polygon, and separate maths would only
add a way to be wrong. k0 dispatches on a recorded convention and returns
`None` rather than guessing when the convention is incomplete.

**The CSV, XML and TXT importers are deliberately NOT written.** See §6.

### `bc759d7` — asset resolution, and the form pre-fills from it

`registry/assets.py` and `workbench/resolve.py`. The resolver proposes, the
operator confirms or overrides, and both values stay in the manifest so an
override is visible later. A suggestion is never applied on its own —
`assign()` still has to be called.

Weights, **project policy**: manifest 1.00, path rule 0.60, CFG header 0.50,
sibling settings 0.50, electrical 0.30. A candidate needs 0.50 and must beat
the runner-up by 0.20. Only a manifest decides alone.

Two rules that came out of the real records:

- **A relay MODEL is not an identifier.** Matching `7SA522` would be a
  confident end signal meaning nothing on a fleet where half the relays are
  7SA522. Only the relay id and its configured aliases count.
- **Evidence naming the line but not the end lifts both ends equally**, so it
  decides the line and never the terminal.

Verified against the real folder tree:

| record | resolved | on what |
|---|---|---|
| `garividi-maradam-1/Main-1 D60` | GRV-MRD-1 / R, 0.90 | path rule + ratios; its CFG station name is the factory default `Relay-1` |
| `garividi-maradam-1/Main-2 P444` | GRV-MRD-1 / R, 1.10 | header `garividi` + path rule |
| `maradam-garividi-1/Main-1` | GRV-MRD-1 / S, 1.90 | header names MARADAM and LINE 205, plus the ratios |
| `maradam-garividi-1/Main-2` | refused | blocked by the conformance gate |

**And it refuses when it should.** Flatten both ends into one `garividi/`
folder and the Garividi records come back *"two candidates are too close to
call (GRV-MRD-1/R at 0.90 against GRV-MRD-2/R at 0.90)"*, because nothing in
the path or header says which of the two parallel circuits they are.

---

## 5. Where to start next

**Pairing (`PROJECT_CONTEXT.md` §5.2).** It needs nothing from anyone and is
now genuinely possible: every record resolves to a line and a terminal, so two
records at the two ends of one line are a candidate pair.

Carry one thing into it: **corroborate electrically before filtering on time.**
13 min 24 s of clock spread on one event is measured, not hypothetical.

After that, in order of value:

1. **CT saturation compensation** — the largest remaining accuracy gap
   (10.7 % against 0.12 % clean), and it needs no field answer.
2. **The `SET-01` … `SET-05` rules**, now possible on vendor-neutral settings:
   settings hash changed between two records from one relay; relay CT/VT
   disagrees with the registry; Zone 1 reach implies a line length that
   disagrees with the registry; Z2 and backup grading; the two ends carrying
   inconsistent line angle or k0.
3. Concrete settings importers, **one per format, as real sample files
   arrive** — see §6.

---

## 6. Do not write the CSV / XML / TXT importers speculatively

There is still **no real `.csv`, `.xml` or `.txt` settings file** anywhere in
the corpus — only Siemens `.rio`. An importer written against an imagined
format is a guess that will look finished, be wrong, and be believed because
it has tests.

The interface, the alias machinery, the sniffing and the refusal-on-tie are
all built and tested. Each concrete importer waits for one real sample file.
One genuine SEL `.txt` teaches more than a week of speculation.

---

## 7. Deliberately left untouched — do not "fix" these

- **The `ps=S` block on five records.** The gate is right to refuse, and the
  data behind it is provably primary. The resolution is a per-relay registry
  override recorded as evidence, **not** a heuristic that infers primary from
  a nominal-voltage match — that would be exactly the silent repair §2.5
  forbids. `OPEN_REQUIREMENTS.md` item 4.
- **`incident_features` and `report/build` still key on one record per
  terminal.** The workbench plan proposed changing them to a list; that was
  deliberately not done, because they are analytical surface and changing them
  for a presentation feature risks moving a number. The cross-check lives in
  `workbench/` instead.
- **44 ruff findings**, all pre-existing under a newer ruff than the repo was
  written against, none on a line changed on 2026-09-07. Their own piece of
  work.
- **The Maradam `Zs2` polarity is not corrected in software.** It is reported;
  confirm the physical CT connection first.
- **`data/registry/*.yaml` lengths and impedances.** Provisional and marked as
  such in every file header. Do not quietly promote them to real by using
  them.

---

## 8. Process notes, learned the hard way

- **Run `python scripts/check_architecture.py` directly, never through a
  pipe.** `| tail` swallows the exit code; one commit was pushed with the
  ratchet failing for exactly that reason.
- **Do not patch source with a shell heredoc plus Python string replacement.**
  It has bitten three times: `\b` became literal backspace bytes, silently
  breaking four signal-matching patterns, and a `\r` broke a parse — both
  invisible in an editor and in `grep`. Use the editor tools. It bit again on
  2026-09-07 in `pages.py`, where a line-continuation backslash became spaces;
  harmless, but caught only by reading the file back.
- **Write commit messages to a file and use `git commit -F`.** Backticks in a
  `-m` message get command-substituted by the shell.
- **`multiprocessing` cannot re-import `<stdin>`.** Any script using the
  Stage-A sweep must be a real file, not a heredoc, or the pool hangs.
- **The file-growth ratchet is a real gate.** When a file legitimately grows,
  prefer splitting it; bump the budget deliberately and in the same commit.
  `--reseed` rewrites everything and hides other growth, so avoid it. Both new
  CLI surfaces went into a new file (`cli/wb.py`) rather than growing
  `cli/commands.py` past its budget.
- **Commits carry R. Surya as the sole author.** No AI co-author trailer and
  no "Generated with" line, on any commit or PR in this repository.

---

## 9. Who else has been in this tree

A second agent worked in `src/dranalyser/standards/` during the 2026-09-07
session and has since finished. Theirs: `standards/` (audit, catalogue, cli
and two YAML data files), `project-docs/STANDARDS_CONTEXT.md`,
`tests/test_standards.py`, the `standards` subcommand in `cli/__init__.py`,
and edits to `README.md`, `pyproject.toml` and `rules/signals.py`. Their work
is included in commit `501f9d7`, whose message says so.

Their `RioSettings` import in `standards/audit.py` was repointed at
`ProtectionSettings` in `b0947ed` along with the other eight call sites.

---

## 10. Suggested first prompt for the next session

> Read `project-docs/NEXT_SESSION.md`, then `PROJECT_CONTEXT.md` §2.
>
> Build pairing (§5.2). Every record now resolves to a line and a terminal
> through `registry/assets.py`, so two records at the two ends of one line are
> a candidate pair. **Corroborate electrically before filtering on time** —
> the measured clock spread on one real event is 13 min 24 s.
>
> Do not touch the estimators, the DSP chain or the parser. Stage-A must still
> report clean p95 = 0.4403 % afterwards; if it moves, that is a defect.
>
> Do not write the CSV, XML or TXT settings importers — §6 explains why.
