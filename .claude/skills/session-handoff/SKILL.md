---
name: session-handoff
description: Persist state after a milestone (merge, audit, big fix, or an approved plan the user parked) so the next cold session can resume — status ledger, lessons, memory entry, plan doc. Use whenever work reaches a milestone, when the user says "keep this documented / we will proceed again later", or at the end of any session that changed what runs.
---

# Session Handoff — write it down in the same sitting

Sessions start cold. Anything not written to one of these places is lost, and the next
session re-derives it wrongly.

## What to update, and where

**1. STATUS LEDGER — `project-docs/STATUS_LEDGER.md`**
After every milestone. Record the date, what changed, the state (uncommitted / committed
on branch X / merged to main at sha Y / pushed to which remote), which gates were run,
and anything still outstanding. "Built", "merged", and "verified against real records" are
three different states — never blur them.

**2. LESSONS — `project-docs/LESSONS.md`**
One-off gotchas that do not fit a standing rule. Newest at the top, dated, one short
paragraph: symptom → cause → the check that catches it next time. If the gotcha
generalises into a rule, it belongs in `CLAUDE.md` or a skill instead.

**3. Persistent memory — `C:\Users\rscvr\.claude\projects\e--dr-analyser\memory\`**
One file per fact, one line per file in `MEMORY.md`. Write what was **non-obvious**: the
surprise, the silent failure, the thing that looked fine and wasn't. Do NOT write what the
repo already records (file structure, what CLAUDE.md says, git history). Convert relative
dates to absolute ("2026-09-06", not "today"). Keep index lines short — the index loads
into every session.

**4. Plan docs — `project-docs/<NAME>_PLAN_v1.md`**
When the user says *"keep this plan documented, we will proceed again"*: persist the plan
to the doc AND memory, then **stop**. Do not start building.

## The handoff note itself

State plainly, in this order:

1. **What state the code is in** — uncommitted / on branch X / merged / exercised against
   real records or only synthetic ones.
2. **What is outstanding** — a gate not run, a corpus file not added, a recompute of
   stored results owed, an §17 [OPEN] question waiting on the user.
3. **What was deliberately left untouched** — so the next session doesn't "fix" it.
4. **Anything deferred or ON HOLD** — record it so it is not re-proposed uninvited.
5. **Who else has been in the tree** — another agent works in this repo; say which files
   were theirs if you can tell.

## Honesty rules

- If a gate was not run, say it was not run. Never report a remembered pass.
- If a step was skipped, name it.
- "Tests pass" ≠ "works on a real record pair". Use the sentence that is true.
