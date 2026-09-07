# Context for the next session

Written 2026-09-07, at commit `0a42087` plus the ledger update, and revised
the same day after the Sphoorthi records arrived. Read this, then
[`PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md) §2 (binding constraints) and
the "What is different from the brief" section of [`README.md`](../README.md).

**Changed in the Sphoorthi revision** (§2b is the new material):

- `inspect` and `verdict` now refuse a record the conformance gate has
  blocked, instead of calling `analyse()` on it and dying with `KeyError:
  'I1'`. `locate`, `report` and `backtest` already gated correctly.
- `map_channel` and `detect_phase_naming` fall back to the last
  separator-delimited token of a channel id, so a vendor prefix no longer
  defeats the phase match. ABB's `LINE1_A_IL1` / `LINE1_UL1` map now. Only
  the *last* token is tried, and only after the whole id and the `ph` field,
  so nothing that mapped before can change -- and the GE D60's RMS channel
  `SRC 1  Ia Mag` still stays unmapped rather than colliding with `F1-IA`.
- `.gitignore` now covers `drs */`, `*.zip` and `*.ZIP`. The nine zips that
  came with the Sphoorthi records were stageable on a public repo.

---

## 1. Get running in two minutes

```bash
cd "e:\dr analyser"
pip install -e ".[dev]"

python scripts/check_architecture.py     # run FIRST, it is the cheapest gate
pytest -q                                # 231 tests
dranalyse stage-a --cases 10000 --workers 1     # PASS, clean p95 = 0.4403 %
dranalyse verdict --S "DR & Events 9-4-2026/Main-2/DR-1/DR-1.CFG" \
                  --line data/registry/dhn-nnr.yaml
```

**Set `OPENBLAS_NUM_THREADS=1`.** Without it, on this machine, the Stage-A
pool dies with `BrokenProcessPool` at the default worker count and two
`tests/test_ml.py` cases fail with `OpenBLAS error: Memory allocation still
failed after 10 retries`. It is one root cause, not two: every worker process
spawns one OpenBLAS thread per core and the machine runs out. Neither is a
defect in the code -- both reproduce on a clean `git stash` of `src/`. With
the variable set, everything passes multi-worker and 10,000 cases take 30 s
instead of 111 s at `--workers 1`. The p95 is identical either way (0.4403 %),
as it should be: the sweep is seeded, not worker-count dependent.

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1     # PowerShell: $env:OPENBLAS_NUM_THREADS=1
```

The local workbench:

```bash
dranalyse workbench --port 8090          # then open http://127.0.0.1:8090/
dranalyse bundle "drs sphoorthi/garividi-maradam-1"   # the same thing, no browser
```

Real records are **not** in the repository (it is public). They are on the
originator's machine under `DR & Events 9-4-2026/` and `DR 9-4-2026/`. Every
test that needs them skips cleanly, so a clone without them still runs green.

---

## 2. What is true, and what is merely built

**Proven against real data**

- The COMTRADE parser reads all four real records: `rev_year` values of 2001
  and 1997 (neither is a valid revision), `nrates=0` with the rate only in the
  DAT timestamp column, a trailing DOS `0x1A`, and `ps=P` vs `ps=S` scaling.
- The measurement chain is validated against the relays' **own zone
  decisions**: Main-2 computes into Zone 1 and tripped Zone 1; Main-1 computes
  into Zone 2 and tripped Zone 2. That is real ground truth, already in the
  archive, needing no patrol result.
- Breaker timing agrees between two independent relays on the same fault:
  phase A opens at 78.1 ms and 78.5 ms, measured at 1200.5 Hz and 1000 Hz.

**Proven only against the synthetic oracle**

- Fault location. Stage-A passes at 100,000 cases with clean p95 = 0.465 %
  against a 0.5 % criterion. Thin margin, stable across seeds.
- **CT saturation is the dominant unhandled error source**: 10.7 % mean error
  against 0.12 % clean. Detected and down-weighted, *not compensated*.

**Not proven at all**

- **The two-ended path has still never run on real data**, but the records
  to run it on now exist locally -- see §2b. What is missing is no longer the
  far-end record, it is the line constants for that corridor.
- `data/registry/dhn-nnr.yaml` is **PROVISIONAL**. Its length and impedances
  are typical ACSR Zebra values, not surveyed. Absolute distances from it are
  not operational.

**Not built**: pairing, transport, edge collector, asset resolution.
**Not handled**: distributed-parameter model for long lines, three-terminal
lines, **zero-sequence mutual coupling between the two circuits of a
double-circuit corridor** -- which the new records in §2b need. Series-
compensated lines are detected and refused, not approximated.

---

## 2b. The Sphoorthi records -- the first real two-ended data

`drs sphoorthi/` (local only, gitignored) arrived 2026-09-07. Eleven distinct
records, no byte-duplicates, covering **three events on two ends each**:

| Event | End A | End B |
|---|---|---|
| 15665, 20/08/2026 -- Maradam LINE 205 | Garividi: GE **D60**, MiCOM **P444** | Maradam: Siemens **7SA522**, "MARADAM" recorder |
| 15662, 20/08/2026 -- Maradam LINE 206 | Garividi: **P444**, ABB **REL670** | Maradam: **7SA522**, "MARADAM" recorder |
| 15251, 10/08/2026 -- 400 kV Kalpaka-Gajuwaka | Gajuwaka Main-1 | Kalpaka Main-2 (two records, 20 s apart) |

All eleven parse and all eleven map to the canonical channel schema. Four
vendors joined the evidence base: GE D60 (BINARY), MiCOM P444, ABB REL670
(BINARY, `nrates=1`), Siemens 7SA522.

**The pairing is corroborated electrically, not by folder name.** On event
15665 the three usable relays measure pre-fault 725.9 / 732.1 / 719.5 A and
all three call it CG; Maradam feeds 2857 A against Garividi's 2019 A, so the
fault is nearer Maradam. On 15662 the two ends measure 331 A and 329 A
pre-fault, and the fault-phase currents are 15,684 A at Garividi against
6871 A at Maradam. **Trigger times spread 13 min 24 s across the four relays
of event 15665** -- any pairing that filters on time before electrical
corroboration throws this event away. This is the field confirmation of the
§7.5 clock warning.

### What blocks the two-ended solve, precisely

Not the records: **the line constants for the Garividi-Maradam corridor.**
This is not a convenience. E5 solves
`|V2S - m.Z1L.I2S| = |V2R - (1-m).Z1L.I2R|`: one real equation in one unknown
`m`, *given* `Z1L`. Treating `Z1L` as unknown too leaves 3 real unknowns
(`|Z_SF|`, `|Z_RF|`, the sync angle) against 1 equation. **The line reactance
cannot be recovered from the two-ended data alone** -- it must be supplied.

### Three findings from the attempt, all needing an answer before any location is trusted

1. **Cross-vendor validation passed at Garividi.** The measured negative-
   sequence source impedance `Zs2 = -V2/I2`, which needs no line constants,
   comes out at `1.67 + j10.28` ohm from the P444 and `2.61 + j10.27` ohm
   from the REL670 -- same bus, same fault, two vendors, agreeing to 0.5 ohm
   and 5 degrees. The measurement chain is right on both.
2. **The Maradam 7SA522 negative-sequence polarity is inverted** relative to
   the Garividi relays: `Zs2` comes out at -167.1 deg (event 15665) and
   -173.3 deg (15662) where the Garividi relays give +75.7 to +84.6 deg. A
   flipped CT is silent and mirrors a two-ended answer. **Settle the CT star-
   point convention at Maradam before trusting any location from this
   corridor.** Note that reversing the sign alone does not fully explain it
   (it would leave +13 deg, still not a plausible source angle), so the
   parallel circuit below may be part of it.
3. **The corridor is double-circuit** -- LINE 205 and LINE 206 run Garividi
   to Maradam -- and **both events are ground faults**, 9 minutes apart on
   the same morning. Zero-sequence mutual coupling between the two circuits
   is a first-order error source for single-ended ground-fault location and
   is not modelled. `dhn-nnr.yaml` carries `double_circuit: false`; these
   lines cannot.

Also open: the GE D60 disagrees with the P444 at the same bus on event 15665
(`Zs2` 155.97 ohm at 9.7 deg against 21.68 ohm at 84.6 deg) while measuring
the same 305-310 A of I2, so the disagreement is in V2, not I2. The D60 also
raises `I-BALANCE` at 69.9 % and places inception at 202.6 ms against a
trigger at 1623.6 ms. Not diagnosed.

### The 400 kV event is parked

Both ends of 15251 block on `RATIO-PS`, the two Main-2 records are 20 s apart
with the second showing no fault at all, and the two ends disagree on fault
type (ABC against CG). Nothing from it is usable until the `ps` question in
§2c is settled.

### 2c. The `ps=S` question, with the evidence

Five records declare `ps=S` with unity ratios and are correctly blocked. They
are not really secondary. Measured pre-fault RMS on
`maradam-garividi-1/Main-2` with the CFG's own `a=17.44`:

```
VA 127,005.6 V   VB 127,709.4 V   VC 127,354.5 V      220 kV / sqrt(3) = 127,017 V
IA     714.3 A   IB     707.8 A   IC     709.5 A
```

Exactly nominal primary volts. And the identical relay at the far end
(`garividi .. Main-2 P444`) uses the same `a=17.44` / `2.21` constants but
declares **`ps=P`**. Same model, same constants, contradictory flag.

The gate is right to refuse -- do **not** add a heuristic that infers primary
from a nominal-voltage match. The resolution is a per-relay override in the
registry, recorded as evidence with its justification, which is one more
reason the `AssetResolver` of §6 comes first.

---

## 3. Where to start, and why

**Start with asset resolution, not with the settings importers.**

Everything today is driven by an operator typing `--S thisfile.cfg`. That does
not scale past one incident, and three things are blocked behind it:

- `backtest.py` hardcodes `terminal_end="S"` and cannot tell two lines apart,
  so it cannot be pointed at a real multi-substation archive — which is the
  cheapest validation available.
- **Pairing (§5.2) is entirely downstream of it.** When the Nandyal records
  finally arrive, nothing will match them to the Dhone records, because
  nothing knows which line or which end either belongs to.
- The report and the ground-truth store both key on a line id that is
  currently whatever the operator passed.

The recommended order:

1. ~~**`ProtectionSettings` interface refactor**~~ — **done 2026-09-07**, see §4.
2. **`AssetResolver`** — folder and file to line / terminal / relay. This is
   the real unlock, and it is now the next thing. The workbench already writes
   the manifest the resolver should fill in: today the operator declares the
   assignment with `source: operator`, and the resolver's job is to pre-fill
   it with `source: resolver` for the operator to confirm or override.
3. **Pairing**, which is now possible.
4. **Concrete settings importers**, one per format, *as real sample files
   arrive* — see the warning in §5.
5. CT saturation compensation, the largest remaining accuracy gap.

---

## 4. Universal settings import — **DONE 2026-09-07**

### The problem that was in the code

`RioSettings` — a Siemens/OMICRON-specific type — was imported directly by
`backtest.py`, `report/render.py`, `rules/features.py` and `cli/commands.py`
(and by `standards/` and `workbench/` by the time it was fixed). A second
vendor could not be added without touching all of them.

### What was built

`registry/settings.py` holds the vendor-neutral model, `registry/settings_io/`
holds the importers, and the RIO reader moved into `settings_io/rio.py` behind
`load_settings(path)`. Nine call sites now name `ProtectionSettings` and
`load_settings`, and none names a vendor.

**The rule has teeth.** `scripts/check_architecture.py` now fails the build if
anything outside `registry/settings_io/` imports a module inside it. The rule
is structural, not a list of banned names, so an `scl.py` or `sel.py` added
later is covered without editing the guard. Six cases are pinned in the
guard's own `--self-test`.

`Characteristic` is an interface with `contains(z)`. `PolygonChar` is the
Siemens shape; `MhoChar` is a self-polarised mho circle for ABB and SEL, whose
maths is standard (a ray at angle *a* leaves a circle of diameter *D* at angle
*theta* at `|D|cos(a - theta)`), not inferred from any file; `quad_char()` is
deliberately a **builder returning a PolygonChar**, because a quadrilateral is
a polygon and inventing separate maths would add a way to be wrong without
adding a capability.

k0 now dispatches on a recorded convention — `siemens_re_xe`, `abb_kn`,
`sel_k0`, `impedances`, `complex_k0` — through the converters already in
`registry/model.py`. An incomplete convention yields `None`, never a guess.

`ProtectionSettings` carries `provenance` (path, format, importer, sha256,
parsed_at, warnings), `raw` (every key the importer saw, untouched) and
`unknown` (what it could not determine, so consumers treat it as unavailable
— the same discipline the rules engine uses with `requires`).

`load_settings` sniffs by content, takes the best importer, and **refuses when
two tie**. Verified end to end on the real `DR-1.rio`: k0 comes out at 0.8061
angle -2.417 deg, matching the value recorded in `dhn-nnr.yaml`.

**Still not built, and §5 still applies:** the CSV, XML and TXT importers. The
interface, the sniffing and the refusal-on-tie are there; each concrete
importer waits for one real sample file.

### Target shape, as built

```
registry/settings.py          vendor-neutral model, what the analyser consumes
    ProtectionSettings
        device, vendor, model, substation, feeder, line_hint
        vt_secondary_v, ct_secondary_a, frequency, line_angle_deg
        k0: complex          + k0_source: which convention it came from
        zs_secondary
        zones: [Zone(name, t1, overreach, reverse, phase_char, earth_char)]
        backup: [BackupStage]
        scheme
        provenance: file path, format, importer, sha256, parsed_at, warnings
        raw: {key: value}    every field seen, untouched
        unknown: [field names it could not determine]

registry/settings_io/
    __init__.py     importer registry, sniffing, load_settings(path)
    rio.py          the existing reader, moved behind the interface
    csv_kv.py       key/value and tabular CSV
    xml_scl.py      IEC 61850 SCL / ICD / CID
    xml_generic.py
    text_kv.py      SEL .txt SET dumps, MiCOM courier text
```

Three design points that matter:

**`raw` keeps everything.** A settings file is evidence. Anything the importer
did not understand stays visible rather than being dropped, and `unknown`
names what could not be determined so consumers can treat it as unavailable —
the same discipline the rules engine already uses with `requires`.

**Characteristics must generalise beyond polygons.** The current model is
Siemens-shaped: a list of `(R, X)` vertices. SEL and ABB use mho circles, and
there are lens and load-blinder shapes. Make `Characteristic` an interface
with `contains(z)`, and implement `PolygonChar`, `MhoChar`, `QuadChar`.
Getting this wrong bakes the Siemens assumption in one layer deeper.

**Setting-name mapping should reuse the scored-alias approach that already
works** in `rules/signals.py`. Same shape: canonical name, match patterns,
prefer and avoid lists, all candidates kept. For example the line angle is
`LINEANGLE`, `RCA`, `MTA`, `Z1ANG`, "Angle of Z1" depending on vendor; k0 is
`RE/RL`+`XE/XL` (Siemens), `KN` (ABB), `kZN` (Alstom), `k0M`/`k0A` (SEL), or a
raw Z0/Z1 ratio. **The k0 conversion table in `registry/model.py` already
covers all four conventions** — it just needs the importers to feed it.

**Sniffing must refuse on ambiguity.** `load_settings(path)` asks every
importer for a confidence, takes the best, and records which one in
provenance. If two tie, it declines and says so. Never guess a format.

### How settings-vs-DR checking works — today and generalised

The mechanism already works end to end for RIO. Only steps 1 and 6 are
vendor-specific:

1. Parse settings: zone reaches in **secondary ohm**, line angle, k0, backup
   pickups.  *(vendor-specific)*
2. Parse the DR to primary volts and amps.
3. Convert the measured loop impedance to secondary with
   `Z_sec = Z_pri * CT_ratio / VT_ratio`. This conversion lives in one place
   on purpose — inverted, it is a factor of 6.25 on this fleet.
4. `which_zone(z_secondary, ground=...)` gives the zone that **should** have
   contained the fault.
5. The DR digital channels give the zone that **did** operate.
6. Compare. Disagreement is rule FL-03 and the back-test confusion matrix.

Also already wired: k0 from the settings drives the ground loop, and the
backup pickups drive BU-03/04/05.

**Once settings import is universal, these become possible and are worth
building** — none of them need a fault location or a far-end record:

| Rule | Check |
|---|---|
| SET-01 | Settings hash changed between two records from one relay: someone changed settings. §11 requires versioned settings; this is how you detect an unrecorded change. |
| SET-02 | Relay CT/VT ratio disagrees with the registry. |
| SET-03 | Zone 1 reach implies a line length that disagrees with the registry. **This is the Dhone–Nandyal question below, as an automated rule.** |
| SET-04 | Grading: Z2 time against the remote Z1, backup time against Z3. |
| SET-05 | The two ends of one line carry inconsistent line angle or k0. |

---

## 5. Warning: do not write the CSV / XML / TXT importers speculatively

There is **no real `.csv`, `.xml` or `.txt` settings file in the corpus** —
only the two Siemens `.rio` files. An importer written against an imagined
format is a guess that will look finished and be wrong, and it will be
believed because it has tests.

**Ask the wing for one real sample of each format before writing its
importer.** Build the interface, the alias machinery and the sniffing now;
build each concrete importer when its file exists. One genuine SEL `.txt`
teaches more than a week of speculation.

---

## 6. Requirement: mapping folders to substation, line and terminal

### What the real folder tree looks like

```
DR & Events 9-4-2026/            <- the DOWNLOAD date, not the event date
    Main-1/                      <- relay function, not the line
        26.04.09 03.05.24.000.000.CFG
    Main-2/
        DR-1/  DR-1.CFG  DR-1.rio
        DR-2/  dr-2.CFG  dr-2.rio
DR 9-4-2026/
    MAin-1 events/               <- note the case and the typo
    Main-2/
        26.02.13 17.02.36.000.000.CFG    <- byte-identical to the Main-1 file
```

Three things this tells you. Folder names encode the **relay function and the
download date**, never the line. Case and spelling are not dependable. And the
same record can be filed under two different relays — the pair above is
byte-identical, caught only by content hash.

### Target shape

```
registry/assets.py
    AssetHint(line_id, terminal_end, relay_id, substation, confidence, source)
    Assignment(line_id, terminal_end, relay_id, confidence, evidence[])
    AssetResolver.resolve(path, record) -> Assignment | Ambiguous
```

Evidence sources, in decreasing authority:

1. **Sidecar manifest** (`_asset.yaml` beside the records). Explicit and
   authoritative. This is what the edge collector will emit later — §4.2 is
   already manifest-first — so adopting the same shape now means the collector
   drops straight in.
2. **Path rules**, configured in the registry rather than coded:
   ```yaml
   path_rules:
     - pattern: '(?i)(?P<substation>[A-Z ]+)[/\\]Main-?(?P<main>\d)'
       relay_function: 'main{main}'
   ```
3. **CFG header**: `DHONE(SWS)` and
   `220KV DHN-NNR 18-3-2026  Folder  7SA522 V4.7 Var` both name the station,
   and the second names the line and the relay model.
4. **A sibling settings file**: the RIO carries `SUBSTATION` and `FEEDER`.
5. **Electrical corroboration**: nominal voltage from the pre-fault reading,
   and CT/VT ratios matching a registered terminal.

The registry needs `aliases` per line, terminal and relay, so `DHN-NNR`,
`DHONE-NANDYAL` and `220KV DHN NNR` all resolve to one line.

**The terminal end is derived by matching the resolved substation against the
line's two terminals — never from file order, and never from which flag the
operator typed.** Today `--S` and `--R` decide it, which means the operator
can silently swap the ends and the answer will be confidently mirrored.

**Refuse on ambiguity.** If two lines match, return `Ambiguous` with the
candidates and the evidence, exactly as the conformance gate and the rules
engine already do. A wrongly assigned record produces a confident location for
the wrong line, which is worse than no location.

---

## 7. Field findings awaiting APTRANSCO action, not code

These came out of the real records and are still open:

1. **Main-1's VT cannot pass zero sequence.** 575 V of V0 during a ground
   fault carrying 1670 A of I0, where Main-2 in the same bay saw 34 kV. It
   makes Main-1 overreach on every earth fault, and it explains Main-1
   tripping Zone 2 while Main-2 tripped Zone 1. **Check the VT secondary
   connection at DHONE.**
2. **`IE>>` carries the not-set sentinel (2^31/100)** — the earth-fault
   backup is disabled at that terminal. Confirm that is intentional.
3. **A 7.1 kA fault against a 1600 A `I>>` pickup produced no overcurrent
   pickup at all.** The settings export and the recorded behaviour disagree;
   only the settings sheet can settle whether that stage is in service.
4. **Main-1 has no carrier-send channel mapped to its recorder**, so CR-01 —
   the highest-value rule in the catalogue — cannot be evaluated from it
   anywhere in the corpus.
5. **Relay clocks in one bay differ by 1418 s.** Any pairing scheme that
   filters on time before electrical corroboration will fail on this fleet.

From the Sphoorthi records (§2b), and these are what actually block progress:

6. **Line constants for Garividi-Maradam LINE 205 and LINE 206**, 220 kV:
   length, conductor, Z1 and Z0, and the zero-sequence mutual coupling
   between the two circuits. CT 800/1 and VT 220000/110 are already read out
   of the 7SA522 and D60 headers, so only the line data is missing. **One
   answer here turns the first real two-ended validation on.**
7. **The CT star-point convention at Maradam** -- see §2b finding 2. A
   flipped CT is silent and mirrors the answer.
8. **The relays' own fault-locator output for events 15662 and 15665** (the
   7SA522 / P444 fault report or the event PDF). That is a comparison
   baseline needing no patrol, the same trick as the zone decisions.
9. **Is `garividi-maradam-2/Main-1 P444`'s station name `MARADAM 2` a feeder
   name** (the bay named for the remote end), and is the REL670's
   `BRAHMANAKOTKUR` a config cloned from another station and never renamed?
   The electrical evidence says both records sit at the Garividi end: they
   measure 15,684 A and ~15,300 A of fault current where the Maradam 7SA522
   measures 6871 A. The CFG station name is evidence, never authority.

---

## 8. The open question that unblocks the registry

**Is Dhone–Nandyal about 27 km?**

The Zone 1 reach in the RIO is 8.75 Ω primary. At the usual 80 % of line that
implies a line reactance of 10.94 Ω, which at 0.399 Ω/km is 27.4 km. If the
line is really 50 km, then Zone 1 is set to about 44 % and that relay is
underreaching badly — which is a finding in its own right, and would also
explain a great deal about the Zone 2 trip.

One answer settles the provisional line file and possibly a protection defect.

---

## 9. Process notes, learned the hard way

- **Run `python scripts/check_architecture.py` directly, never through a
  pipe.** `| tail` swallows the exit code; one commit was pushed with the
  ratchet failing because of exactly that.
- **Do not patch source with shell heredoc plus Python string replacement.**
  It happened three times: `\b` became literal backspace bytes (16 of them,
  silently breaking four signal-matching patterns), and `\r` became a literal
  carriage return that broke the parse. They are invisible in an editor and in
  `grep`. Use the editor tools.
- **Write commit messages to a file and use `git commit -F`.** Backticks in a
  `-m` message get command-substituted by the shell; one message lost a word
  that way.
- **`multiprocessing` cannot re-import `<stdin>`.** Any script that uses the
  Stage-A sweep must be a real file, not a heredoc, or the pool hangs.
- The file-growth ratchet in `scripts/architecture_budgets.json` is a real
  gate. When a file legitimately grows, prefer splitting it; bump the budget
  deliberately and in the same commit. `--reseed` rewrites everything and
  hides other growth, so avoid it.

---

## 10. Suggested first prompt for the next session

> Read `project-docs/NEXT_SESSION.md`, then `PROJECT_CONTEXT.md` §2.
>
> Start with the `ProtectionSettings` refactor described in §4: make the
> analyser depend on a vendor-neutral settings model instead of `RioSettings`,
> with the existing RIO reader as the first importer behind the interface, and
> `Characteristic` generalised so a mho circle can be represented as well as a
> polygon. Keep every existing test green.
>
> Then build the `AssetResolver` in §6, and make `dranalyse backtest` use it
> instead of hardcoding `terminal_end="S"`.
>
> Do **not** write the CSV, XML or TXT settings importers yet — §5 explains
> why. Tell me which sample files you need from the protection wing.
