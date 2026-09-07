# Open requirements — what the analyser needs and cannot derive

Written 2026-09-07 at commit `bc759d7`. One page, so it can be sent to the
protection wing as it stands.

Every item here **blocks work that is otherwise finished**. None of them is a
coding task, and none can be worked around by assuming a value — where an
assumption was unavoidable, the code refuses to report a number rather than
producing a confident wrong one.

Ordered by how much they unblock.

---

## 1. Line constants for Garividi–Maradam LINE 205 and LINE 206 (220 kV)

**Needed:** route length, conductor type, positive-sequence Z1 (R and X per
km), zero-sequence Z0, and the **zero-sequence mutual coupling** between the
two circuits.

**Already known, read out of the records — do not re-survey these:** nominal
220 kV (pre-fault 127.0 kV phase-to-ground measured at both ends), CT ratio
800/1, VT ratio 2000 (220000/110 on the 7SA522, 127000/63.5 on the D60).

**What it unblocks:** the first real two-ended fault location in the project.
Both ends of two faults are already in hand and everything else is built.

**Why it cannot be derived.** The two-ended estimator E5 solves

    |V2S − m·Z1L·I2S| = |V2R − (1−m)·Z1L·I2R|

which is one real equation in one unknown `m`, **given `Z1L`**. Treat `Z1L` as
unknown too and there are three real unknowns (`|Z_SF|`, `|Z_RF|`, the
synchronisation angle) against one equation. The line reactance is not
recoverable from the measurements; it has to be supplied.

`data/registry/grv-mrd-1.yaml` and `grv-mrd-2.yaml` currently hold typical
ACSR Panther values, clearly marked PROVISIONAL. They exist so records can be
identified, not so distances can be reported.

---

## 2. CT star-point convention at Maradam

**Needed:** confirmation of which way the CT star point faces on the LINE 205
and LINE 206 bays at Maradam — towards the busbar or towards the line.

**The evidence.** The measured negative-sequence source impedance
`Zs2 = −V2/I2`, which needs no line constants at all, comes out at:

| relay | event 15665 | event 15662 |
|---|---|---|
| Maradam 7SA522 | 162.10 Ω at **−167.1°** | 427.21 Ω at **−173.3°** |
| Garividi P444 | 21.68 Ω at +84.6° | 10.41 Ω at +80.8° |
| Garividi REL670 | — | 10.60 Ω at +75.7° |

A source impedance sits at +75° to +85°. The Maradam figures are on the
opposite side, in both events.

**Why it matters:** a reversed CT is completely silent — no flag, no error —
and it **mirrors** a two-ended answer. A fault 8 km from Maradam would be
reported 8 km from Garividi.

**Note:** reversing the sign alone does not fully explain it (it would leave
+13°, still not a plausible source angle), so the parallel circuit may also be
involved. Please confirm the physical connection rather than assuming the
number can be corrected in software.

---

## 3. The D60's voltage input at Garividi

**Needed:** a check of the VT connection and the voltage input wiring on the
GE D60 on the Garividi end of LINE 205.

**The evidence,** event 15665, two relays on the *same* bus watching the
*same* fault:

| | GE D60 | MiCOM P444 | agreement |
|---|---|---|---|
| pre-fault load current | 643.6 A | 648.1 A | 0.7 % |
| fault current (p90) | 727.8 A | 749.2 A | 2.9 % |
| measured Zs2 | **155.97 Ω at 9.7°** | **21.68 Ω at 84.6°** | factor 7.2, 75° apart |

The currents agree, so the CTs are fine. Only the voltage-derived quantity
disagrees. The analyser now raises this automatically as finding **XR-04**.

---

## 4. The `ps=S` declaration on the 1999-era recorders

**Needed:** confirmation that the "MARADAM" and 400 kV bay recorders export
**primary** values, so a per-relay override can be recorded in the registry.

**The evidence.** Five of the eleven Sphoorthi records declare `ps=S`
(secondary) with unity CT and VT ratios. Measured pre-fault RMS on
`maradam-garividi-1/Main-2`, using the CFG's own scale factor:

```
VA 127,005.6 V   VB 127,709.4 V   VC 127,354.5 V     220 kV / √3 = 127,017 V
IA     714.3 A   IB     707.8 A   IC     709.5 A
```

Exactly nominal primary volts. And the identical relay at the far end
(`garividi .. Main-2 P444`) uses the same `a = 17.44` and `2.21` constants but
declares **`ps=P`**. Same model, same constants, contradictory flag.

**What it unblocks:** five records, including both ends of the 400 kV
Kalpaka–Gajuwaka event, currently refused.

**Please do not ask for this to be auto-detected.** Inferring "these look like
primary volts" from a nominal-voltage match is exactly the silent repair that
§2.5 forbids. The fix is a per-relay override in the registry, recorded with
this evidence beside it.

---

## 5. Relay fault-locator output for events 15662 and 15665

**Needed:** the 7SA522 / P444 fault report or the event PDF for the two
Garividi–Maradam faults of 20/08/2026.

**Why:** it gives a comparison baseline for the analyser's own answer with no
patrol required — the same trick already used with the zone decisions, where
the relay's own trip is the ground truth.

---

## 6. Confirmation of two station-name oddities

`garividi-maradam-2/Main-1 P444` carries the station name `MARADAM 2`, and the
ABB REL670 in the same bay carries `BRAHMANAKOTKUR`. The electrical evidence
puts both at the **Garividi** end (they measure 15,684 A and ~15,300 A where
the Maradam 7SA522 measures 6871 A).

Reading: the first is a *feeder* name (the bay named for the remote end), the
second a configuration cloned from another station and never renamed. **Is
that right?** The resolver treats a CFG station name as rank-3 evidence, never
authority, partly because of these two.

---

## 7. Still open from the Dhone/Nandyal records (older, unchanged)

1. **Main-1's VT cannot pass zero sequence** — 575 V of V0 during a ground
   fault carrying 1670 A of I0, where Main-2 in the same bay saw 34 kV. It
   makes Main-1 overreach on every earth fault. **Check the VT secondary
   connection at DHONE.**
2. **`IE>>` carries the not-set sentinel (2³¹/100)** — the earth-fault backup
   is disabled at that terminal. Confirm that is intentional.
3. **A 7.1 kA fault against a 1600 A `I>>` pickup produced no overcurrent
   pickup at all.** The settings export and the recorded behaviour disagree.
4. **Main-1 has no carrier-send channel mapped to its recorder**, so CR-01 —
   the highest-value rule in the catalogue — cannot be evaluated anywhere in
   the corpus.
5. **Is Dhone–Nandyal about 27 km?** Zone 1 is 8.75 Ω primary; at the usual
   80 % that implies 10.94 Ω of line reactance, which at 0.399 Ω/km is 27.4 km.
   If the line is really 50 km then Zone 1 is set to about 44 % and that relay
   is underreaching badly — a finding in its own right.

---

## What is NOT waiting on anyone

For the avoidance of doubt, these are done and need nothing from the wing:
the COMTRADE parser and conformance gate, the DSP chain, the estimators and
the ensemble, the rules engine, the two-page report, ground-truth capture, the
Stage-A acceptance sweep, vendor-neutral settings import, asset resolution,
and the local upload workbench.

The next piece of code, needing no answer from anyone, is **pairing**
(`PROJECT_CONTEXT.md` §5.2).
