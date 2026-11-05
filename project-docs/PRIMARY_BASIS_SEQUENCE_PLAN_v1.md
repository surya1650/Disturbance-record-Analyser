# Primary measurement basis and same-end capture sequence

Branch `codex/operator-ui-review`, baseline `97489e4`, 5 November 2026.
The user's new recordings and explicit already-primary declaration reopen only
this bounded follow-up; earlier completed goals remain closed. Read the
[checkpoint](PRIMARY_BASIS_SEQUENCE_CHECKPOINT.md) first and preserve all work.

The portal must inspect one recording or successive captures from one end,
without requiring an opposite-end record. COMTRADE gain/offset and unit conversion
always apply. An extra CT/VT multiplier applies only to supported secondary
measurements, never again to already-primary data. The user's proposed magnitude
check is useful as an explanation and review prompt, not proof of actual ratings:
low primary current, voltage collapse, raw counts and voltage basis can look alike.

- P0: check old leases, preserve source bytes/history and branch, record ownership.
- P1: source-hash-bound explicit PRIMARY declaration on the same logical record;
  preserve legacy secondary review digests and source bytes, rerun all gates,
  retain original and effective declarations. Never bypass invalid gains or units.
- P2: simple primary/secondary choice in Setup; display-only supported one-cycle
  RMS hints; explicit 132 kV / 110 V with 600/1 A and 220 kV / 110 V with 800/1 A
  examples plus custom ratings. No automatic voltage-level/rating assumptions.
  Label phase/line voltage basis, leave unknowns unresolved and retain drafts.
- P3: one incident with independent chronological captures; name any unrecorded
  gap or overlap and keep signals within their own sample support. Do not silently
  stitch originals, assign opposite ends or assert AR/breaker motion from a zone
  bit or zero current. Reuse existing source timing/stages/native engines.
- P4: privately analyse both real uploads after the explicit user-declared primary
  basis review, including supported phase RMS, digital edges and one-ended native
  eligibility/refusals. Do not invent line impedance/length, ratings, end identity
  or clock evidence. Private source data and values stay ignored/local.
- P5: focused and full tests, direct architecture guard/self-test, Stage-A 10,000,
  browser Setup workflow and actual four-page PDF checks, build/package/privacy
  review, phase commits and authorized review-branch push with remote HEAD check.

Only code/tests and sanitized evidence may be public. No main merge, deployment,
environment publication or new continuation automation. Keep old goals' owned
continuations paused. If automatic approval review rejects publication, preserve
local commits and save `PUSH_PENDING_AUTH`; do not retry another publishing path.
Platform interruption must be recorded exactly; elapsed time is never consent or
evidence of continuing work. The local exclusive writer lease is under ignored
`work/qa-primary-basis-sequence-2026-11-05/active-writer.json`.
