---
name: same-defect-sweep
description: After fixing a bug in one estimator, one parser branch, one vendor channel map, or one conformance check, sweep every sibling for the identical defect class before reporting done. Use immediately after any single-surface fix, and whenever the user says "check the others also" or "why like this errors again and again".
---

# Same-Defect Sweep — the fix is not done until the siblings are checked

This codebase is built from parallel families: six estimators, four COMTRADE editions ×
two container forms × two data formats, one channel-name dictionary per vendor, one
conformance check per rule. A mistake made once was almost certainly made in the family.
**Fixing one and stopping is the most repeated complaint across the user's projects.**

## Procedure

1. **Name the defect class in one sentence** — not "E2 gave a wrong m" but *"the loop
   selection used the faulted phase pair instead of the phase-to-ground loop for an LG
   fault"*. The class is what you grep for.
2. **List the sibling set** (below) for the surface you touched.
3. **Grep the class across the whole set**, then read the hits. Two shapes work for
   nearly everything: the wrong pattern itself, or the *absence* of the right one (list
   the family, subtract the files containing the correct call — the remainder are
   suspects).
4. **Report a table**: sibling · affected yes/no · evidence line. Never "checked all
   estimators" without the list.
5. Fix them **one at a time** if the user says fix; otherwise report and wait —
   "check/review/verify" means report.

## Sibling sets

**Estimators** — `src/dranalyser/faultloc/estimators.py`:
`e1_reactance`, `e2_takagi`, `e3_modified_takagi`, `e4_synchronised`, `e5_unsynchronised`
(+ the E5 helpers `e5_terms`, `e5_roots`, `e5_delta`, `e5_residual`) and the shared
`loop_quantities` / `distribution_factor_zero`. A convention bug (per-unit vs km, S vs R
reference, RMS vs peak, primary vs secondary, degrees vs radians) is never in one
estimator only.

**Ensemble paths** — `faultloc/ensemble.py`: `_single_ended`, `_two_ended`, `_weigh`,
`_fault_consensus`. Single-ended and two-ended paths drift apart; a flag added to one
almost always belongs in the other.

**Parser branches** — `comtrade/parser.py`: edition 1991 / 1999 / 2013 · `.CFF` vs
four-file · ASCII vs binary vs float32 · single vs multiple sample rates
(`nrates`) · per-vendor channel-name resolution. Scaling, offset, and endianness bugs
sweep across all of them.

**Conformance checks** — `comtrade/conformance.py`: every rule in `check()`. If one rule
returns a bare bool instead of a structured flag, or repairs instead of tagging, look at
all of them.

**DSP steps** — `dsp/core.py`, `dsp/detect.py`, `dsp/pipeline.py`: prefault reference,
window selection, filtering, phasor extraction, sequence decomposition. A window bug at
one step shifts every downstream number.

**Registry** — `registry/model.py` / `loader.py`: every parameter with a unit
(Ω, Ω/km, km, ratio). A unit or per-km-vs-total bug in one field is usually in its
neighbours.

**CLI commands** — `cli.py`: `locate`, `inspect`, `selftest`, `template`. Output and flag
rendering defects repeat across all four.

## Defect classes that repeat in this problem domain

- A **unit or convention mismatch** — per-unit vs km, per-km vs whole-line impedance,
  primary vs secondary, RMS vs peak, degrees vs radians, m from S vs from R.
- A number **re-derived per view** instead of read from the one computed field, so the
  table and the summary disagree about the same fault.
- A **silent clamp or silent default** where a flag was required (`m` forced into [0,1],
  a missing CT ratio defaulting to 1, a missing `tmq_code` treated as good clock).
- A check that **repairs instead of tagging** (§2.5).
- A **sampling-rate assumption** baked into a window length in samples instead of cycles.
- A vendor channel name matched by a **substring** that also matches another channel
  (`IN` inside `IN_1`, `V_R` inside `V_RY`).
- A **magic constant** hard-coded where a registry value belongs.

## Finish

Report what changed AND what was deliberately left untouched. If a sibling is genuinely
unaffected, say why in one clause — that clause is the evidence the sweep happened.
