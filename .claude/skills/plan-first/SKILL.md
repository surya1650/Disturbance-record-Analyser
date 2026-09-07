---
name: plan-first
description: Write a phased plan doc to project-docs/ for a big feature and STOP for approval, instead of starting to build. Use when the user describes a multi-part feature, says "plan this / write a plan / keep it documented, we will proceed again", or when a request would touch more than a couple of modules.
---

# Plan First — write the doc, then stop

Significant work gets a plan in `project-docs/` **before** any code. The user approves it,
then implementation follows the plan's phases with **one commit per phase** (`P1:`, `P2:` …
subjects matching the plan).

When the user says *"keep this plan documented, we will proceed again"*, persist it and
**stop**. Do not start building. Do not "just scaffold P1".

## File

`project-docs/<FEATURE_NAME>_PLAN_v1.md` — SCREAMING_SNAKE, versioned `_v1`, `_v2`… A
revision is a new `_v2` file, not an edit that erases what was approved.

## Sections

1. **Problem** — what is wrong or missing today, with evidence from a real run (a record
   pair, the per-method table it produced, the error in km). Not a hypothesis.
2. **Scope** — what is in, and an explicit **NOT in scope** list. The user will ask "no
   changes to the parser ryt?" — the plan should already answer it.
3. **Constraint check** — which `PROJECT_CONTEXT.md` §2 constraints the work comes near,
   and how it stays inside them. If it needs one relaxed, say so here, in the open, with
   the technical reason (see the `spec-constraints` skill). Name any §17 **[OPEN]** item
   the plan assumes a default for, and state the default used.
4. **Standards basis** — cite the clause for anything engineering-facing (IEEE
   C37.114-2014 for location, C37.111-2013 / IEC 60255-24 for COMTRADE, C37.232-2011 for
   naming). **If no standard covers it, say so explicitly and label it project policy** —
   a policy threshold must never be presented as standards-derived.
5. **Phases P1…Pn** — each independently mergeable, with its named files and its own
   "done when". A phase that cannot be verified on its own is too big.
6. **Test plan** — which synthetic cases (with known `m`), which corpus files, which
   accuracy target from §7.4 / §13 the change must still meet after it lands.
7. **Data / registry impact** — new registry fields, changes to the line YAML schema,
   anything that makes stored results mean something different, and whether past results
   must be recomputed.
8. **Expected step change** — what numbers will visibly move once this ships, by how much,
   and why it is correct. So the user can warn testers and not read it as a regression.
9. **Risks / open questions** — the things you would otherwise silently guess.

## Then

- Save the plan, add a one-line memory pointer and a `project-docs/STATUS_LEDGER.md`
  entry, and **report the plan location and a short summary**. Ask for approval. Wait.
- On approval, implement **one phase at a time**, running the gates per phase
  (`release-check`), reporting what changed and what was deliberately left alone.
- If the plan turns out to be wrong mid-build, say so and update the doc — do not silently
  diverge. Afterwards, where doc and code disagree, **code is truth**: fix the doc.
  (`PROJECT_CONTEXT.md` is the exception — it is the agreed spec.)
