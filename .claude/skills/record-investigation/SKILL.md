---
name: record-investigation
description: Answer "why does this record / this fault give X" with evidence from the actual file and the actual registry entry instead of by reading code — inspect the record, check the conformance flags, check the line parameters, and only then blame the maths. Use whenever a location looks wrong, two ends disagree, a method returns nothing, or the user asks "why is it showing this km".
---

# Record Investigation — evidence before theory

A wrong location has four possible homes, and they are cheap to separate in this order.
Reading the estimator first is the slow way; it is also how a data problem gets "fixed"
in the algebra.

## Order of investigation

**1. What is in the file?**
```powershell
dranalyse inspect <record.cfg>
```
Read: edition, container form, sample rate(s), number of channels, resolved channel roles,
CT/VT ratios, primary/secondary convention, record length in cycles pre- and post-fault,
`tmq_code` / clock quality, and the conformance flags. **Unresolved channel roles and a
wrong ratio explain more wrong answers than any estimator bug.**

**2. What did the gate say?**
Conformance flags are structured and travel to the report (§2.5). A record that produced a
number *and* a flag is not a mystery — the flag is the answer. Quote it.

**3. Is the registry entry right?**
`data/registry/<line>.yaml` — Z1, Z0 (and therefore k0), line length, tower chainage,
CT/VT ratios, which end is S. A 5 % error in Z1 is a 5 % error in the answer, and nothing
in the maths will reveal it. Cross-check the length against the tower chainage table and
against what the relay itself reports.

**4. Do the two ends agree?**
For one incident, compare per-terminal results. Disagreement between two independent
relays on the same fault is a **data** signal, not an algorithm signal: different sample
rate, different CT ratio, opposite P/S convention, different filter window, a record that
starts after inception. Check the inception instants first — if the two ends disagree
about *when*, they will disagree about *where*.

**5. Which methods ran, and which refused?**
The per-method table is the diagnostic. A method returning an `Estimate` with a reason
("no zero-sequence source data", "roots complex", "δ inconsistent") is telling you exactly
what is missing. A blank column means the input was not there — go back to step 1.

**6. Only now read the maths** — and if you do change it, `fault-location-math` applies:
derivation, purity, synthetic test with known `m`.

## Ground truth

When a patrol-confirmed location exists, it is the only real check — and it is itself
accurate to roughly ± 1 span (≈ 0.3 km). Never present agreement inside that band as
proof the estimator is precise, and never tune a constant to chase one confirmed event
(that is §2.1 by the back door).

## Reporting a finding

State: the record(s) by filename, the flags, the registry values used, the per-method
table, and the one sentence that explains the discrepancy. If the cause is upstream
(collection, ratio, settings), say so plainly — §2.7 makes the collection boundary part
of this project's scope, so "not our bug" is not an outcome; "a collection defect, here is
the evidence to hand the substation team" is.
