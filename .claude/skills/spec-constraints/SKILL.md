---
name: spec-constraints
description: Check a request or design idea against the binding constraints in PROJECT_CONTEXT.md §2 before building it — per-relay ML, traveling wave, time-sync dependency, per-file reports, silent input repair, learned corrections overruling physics. Use whenever a task smells like one of those, when someone proposes "train a model on historical faults", or before starting any design work in this repo.
---

# Spec Constraints — §2 is binding, argue it or leave it out

`PROJECT_CONTEXT.md` §2 records decisions already taken **after review**, each with the
reason that killed the alternative. They exist because they are the approaches that look
attractive to a fresh reader — including a fresh agent — and would otherwise be rebuilt.

**"I'd prefer X" is not new information.** If you think a constraint is wrong, say so
explicitly with the specific technical reason, and wait. Do not build it quietly.

## The six, and how they show up in practice

| § | Ruled out | How the request usually arrives |
|---|---|---|
| 2.1 | **Per-relay ML fault location** | "train on historical fault data of every relay", "learn the relay's bias", "the model can correct the distance" |
| 2.2 | **Traveling-wave location** | "add TW as phase 2", "we can get µs resolution by interpolating" |
| 2.3 | **GPS / time-sync dependency** | "first we need IRIG-B everywhere", "align the two records on absolute time" |
| 2.4 | **One report per file** | "emit a PDF per record", a pipeline keyed on record id |
| 2.5 | **Silent repair of bad input** | "if the CT ratio is missing, assume 1", "flip the polarity if it looks reversed" |
| 2.6 | **Learned correction overruling physics** | a corrected number printed alone, an uncapped residual model |

### 2.1 — the arithmetic that kills per-relay ML

1–3 faults per line per year · 15–30 % patrol-confirmed · ~80 % of those single-line-to-
ground · the "true" location itself accurate to about ± 1 span (≈ 0.3 km) — i.e. **label
noise is the size of the error being corrected** — against 10³–10⁶ free parameters.
A fit on 5 points looks excellent on those 5 points, passes review, and then moves a real
answer the wrong way on the 6th fault while carrying the authority of "the model said so".

The permitted path is §9, **in order**: Tier 1 estimate line parameters (build first) →
Tier 2 hierarchical residual model pooled across the fleet, gated on ≥ 100 confirmed
ground-truth events → Tier 3 ML only where labels are actually plentiful. Tier 2/3 ship
only if they beat the raw two-ended baseline under leave-one-line-out validation.

### 2.3 — E5 is why sync is not a dependency

The primary estimator is unsynchronised. E4 (synchronised) is a bonus taken only when both
records report good clock quality (`tmq_code`). Any plan whose critical path runs through
substation time synchronisation is wrong, and any schedule that says "fault location after
IRIG-B rollout" should be pushed back with §2.3 quoted.

### 2.5 — the tag travels

A conformance failure is not a reason to drop a record; it is a flag that must reach the
report. Never guess a CT/VT ratio, never auto-correct a polarity without flagging it,
never drop a record without a visible record of the drop. Wrong input reported honestly is
a collection defect someone can fix; wrong input silently repaired is a wrong answer with
no trace.

## Procedure when a request touches one of these

1. Name the constraint (`§2.x`) and quote its reason in one or two lines.
2. Say what the request would become if it respected the constraint — there is nearly
   always a permitted version (per-relay ML → Tier 1 line-parameter estimation; TW →
   nothing, it is a hardware purchase; sync → E5 with a δ consistency check).
3. If the user reaffirms the original after hearing the reason, that is their decision:
   say so plainly, record it in `project-docs/LESSONS.md` with the date, and build it.

## [OPEN] items — §17

Where the document says **[OPEN]**, the decision has not been made. A default assumption is
stated for each; you may build against the default **only if you say which default you
used, in the report and in the code comment**. Never silently invent an answer. The open
ones that most often bite: which relay families are in the fleet (§17.1), whether both
terminals are under one utility (§17.3 — inter-utility tie lines are permanently
single-ended without a data-sharing agreement), and how much archived DR + patrol data is
recoverable (§17.5 — this is the entire input to Stage-B validation).
