# Context for the next session

Written 2026-09-07, at commit `0a42087` plus the ledger update. Read this,
then [`PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md) §2 (binding constraints)
and the "What is different from the brief" section of [`README.md`](../README.md).

---

## 1. Get running in two minutes

```bash
cd "e:\dr analyser"
pip install -e ".[dev]"

python scripts/check_architecture.py     # run FIRST, it is the cheapest gate
pytest -q                                # 229 tests
dranalyse stage-a --cases 10000          # acceptance sweep, ~10 s on 14 cores
dranalyse verdict --S "DR & Events 9-4-2026/Main-2/DR-1/DR-1.CFG" \
                  --line data/registry/dhn-nnr.yaml
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

- **The two-ended path has never run on real data.** There is no far-end
  record anywhere in the corpus. Everything in §7.2 rests on the synthetic
  generator alone.
- `data/registry/dhn-nnr.yaml` is **PROVISIONAL**. Its length and impedances
  are typical ACSR Zebra values, not surveyed. Absolute distances from it are
  not operational.

**Not built**: pairing, transport, edge collector, asset resolution.
**Not handled**: distributed-parameter model for long lines, three-terminal
lines. Series-compensated lines are detected and refused, not approximated.

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

1. **`ProtectionSettings` interface refactor** — small, mechanical, unblocks
   everything else. Tests already exist. Half a day.
2. **`AssetResolver`** — folder and file to line / terminal / relay. This is
   the real unlock.
3. **Pairing**, which is now possible.
4. **Concrete settings importers**, one per format, *as real sample files
   arrive* — see the warning in §5.
5. CT saturation compensation, the largest remaining accuracy gap.

---

## 4. Requirement: universal settings import

### The problem in the current code

`RioSettings` — a Siemens/OMICRON-specific type — is imported directly by
`backtest.py`, `report/render.py`, `rules/features.py` and `cli/commands.py`.
A second vendor cannot be added without touching all four. That is the single
piece of vendor lock-in in the codebase and it should go first.

### Target shape

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
