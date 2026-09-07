# Handoff prompt — paste this to the reviewing / building agent

Copy the block below verbatim as your first message to the other agent, with
`PROJECT_CONTEXT.md` attached or present in the repo root.

---

```
Attached is PROJECT_CONTEXT.md — the full brief for a two-ended disturbance record
analyser for distance protection relays. It is self-contained; you have no prior
conversation with me.

Read it end to end before responding. Pay particular attention to §2 (Non-goals and
hard constraints) — several plausible-looking approaches are explicitly ruled out
there with reasons.

Do two things, in this order:

PART 1 — REVIEW (do this before writing any code)

Act as a critical reviewer, not an implementer. Specifically:

1. Attack the physics and the maths. Verify the fault-location equations in §7,
   especially the E5 quadratic expansion and the k0 definition. Show your working.
   If any of them is wrong or ambiguous, say so and give the correction.
2. Attack the constraints in §2. For each of §2.1–§2.7, say whether you agree, and
   if you disagree give the specific technical reason and what you would do instead.
   Do not silently reintroduce a ruled-out approach.
3. Find what is missing. Name the things a working system needs that this document
   does not cover, ranked by how badly their absence would hurt.
4. Challenge the sequencing. §14 defines the first PR and §16 the phases. Say
   whether that ordering maximises the chance of a working system, and if not, what
   you would reorder.
5. Flag anything in §17 [OPEN] that blocks you from starting.

Give me the review as prose with specific references to section numbers. Do not
soften it. If a section is fine, say so in one line and move on.

PART 2 — BUILD (only after I have responded to your review)

Implement §14 "Definition of done for the first PR" — nothing beyond it. That is:
a COMTRADE parser, the §5.1 conformance gate, §6 DSP steps 1–8, estimators
E1/E2/E5 with the delta consistency check, a CLI that prints the per-method table,
and a synthetic test harness asserting the Stage-A criterion from §13.

Rules for the build:
- Python, NumPy/SciPy. No framework until the CLI works end to end.
- Write your own COMTRADE parser. Do not pip-install one — §12 explains why.
- Every estimator is a pure function taking phasors and line parameters and
  returning (m, residual, diagnostics). No I/O inside the maths.
- Tests first for the maths: synthetic waveforms with known m, asserted to the
  accuracy targets in §7.4.
- Where §2 says do not do something, do not do it. Where the document says [OPEN],
  stop and ask rather than assuming.

Start with Part 1.
```

---

## Notes for Surya (do not paste)

- **Part 1 exists so the other agent argues before it builds.** An agent handed a
  document and told "start building" will build it, including the parts that are wrong.
  Forcing a review pass is the cheapest bug-finding you will get.
- **The E5 quadratic is worth having independently verified.** It is the single most
  load-bearing equation in the whole system; an algebra slip there is silent and
  catastrophic. The review prompt asks specifically for the derivation to be checked.
- **If the other agent is a coding agent in a repo** (Claude Code, Cursor, Codex),
  put `PROJECT_CONTEXT.md` at the repo root and add a one-line `CLAUDE.md` /
  `AGENTS.md` pointing at it:
  `Read PROJECT_CONTEXT.md before any work on this repo. §2 is binding.`
- **If you get the `E:\dr analyser` folder to me**, I will fold its contents into §17
  item 8 and revise the first-PR definition so the other agent doesn't rebuild what
  already exists.
