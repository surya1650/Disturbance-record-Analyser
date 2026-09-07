# Working rules for this repository

Read [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md) before any work here.
**Section 2 of that document is binding** — several plausible-looking
approaches are ruled out there with reasons. If you believe one of them is
wrong, argue it explicitly; do not silently build it.

Read the "What is different from the brief, and why" section of
[`README.md`](README.md) before touching `faultloc/` or `ml/`. Several
equations in the brief were corrected during implementation and the code is
right where they differ.

## Hard rules

- **The synthetic generator in `synth/generator.py` is the oracle.** It
  depends on nothing else in the package. Anything that changes an estimator,
  the DSP chain or the window logic must be graded against it before it is
  graded against a real record.
- **Never silently repair bad input.** A wrong ratio, a reversed CT, a VT
  that cannot pass zero sequence — all are reported and the affected
  estimators are gated off. None are corrected in place. A confident wrong
  number is worse than a refusal.
- **Every reported location names its method.** A single number with no
  method attached is never emitted.
- **`m` is per unit of series REACTANCE, not of length.** Converting to km
  always walks the section table (`Line.m_to_km`). A linear conversion on a
  mixed-conductor line can be kilometres out.
- **Currents are positive from bus INTO the line at both ends.** Every
  equation in `faultloc/` assumes it. A flipped CT is silent, not an error.
- **k0 is derived from the vendor's native form, never typed in.** See
  `registry/model.py`.
- **Real substation data is not committed.** This repository is public. The
  disturbance records, the `.rio` settings export and the event PDFs stay
  local; tests that need them skip cleanly.

## Before saying a change works

`pytest -q` must pass — 141 tests. `dranalyse selftest` must still report
PASS on the Stage-A criterion. A build passing is not the same as a change
working.
