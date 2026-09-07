---
name: fault-location-math
description: Change or add fault-location / DSP maths safely — derive before coding, keep the function pure, test against a synthetic case with known m, and never guess an engineering constant. Use whenever touching src/dranalyser/faultloc/, src/dranalyser/dsp/, the k0 definition, the E5 quadratic, or any accuracy/threshold number.
---

# Fault-Location Maths — derive it, then test it against a known answer

An algebra slip here is **silent and catastrophic**: the CLI still prints a confident
number, the report still looks professional, and a line crew walks the wrong 8 km of
right-of-way at night. Nothing else in this repo fails that quietly.

## Before writing code

1. **Find the authority.** `PROJECT_CONTEXT.md` §7 for the estimator family, IEEE
   C37.114-2014 for the method itself, §7.4 for the accuracy target the change must still
   meet. Quote the section you are implementing in the docstring.
2. **Write the derivation out** — in the docstring or in the PR/report, not only in your
   head. For anything quadratic (E5), show the terms `a`, `b`, `c` and where each came
   from. The E5 expansion is the single most load-bearing piece of algebra in the system
   and was flagged for independent verification in the handoff prompt for that reason.
3. **Never guess a constant.** Line parameters (Z1, Z0, k0, length, chainage, CT/VT
   ratios) come from the registry. Standard limits come from the standard. If a number
   cannot be sourced, stop and ask — do not approximate it, and do not "temporarily"
   hard-code it.
4. Get the definitions right and reuse the existing ones rather than restating them:
   `k0` lives in `registry/model.py` (`k0_from_impedances`, `k0_from_siemens`), the loop
   selection in `estimators.loop_quantities`, the quadratic in `stable_quadratic`.
   A second definition of `k0` in a second file is a defect even while the numbers agree.

## Rules the architecture gate enforces (`python scripts\check_architecture.py`)

- **Purity.** No `open`, `print`, `logging`, `yaml`, `os`, `pathlib`, `argparse`, no
  config lookup, no DB inside `faultloc/` or `dsp/`. An estimator takes phasors + line
  parameters and returns `(m, residual, diagnostics)`. This is what makes it testable
  against 10⁴ synthetic cases in seconds.
- **No ML import in the fault-location path** (§2.1). The learning layer may read the
  physics; the physics never reads the learning layer.
- **Every estimator returns an `Estimate`,** never a bare float — so the number always
  carries its method name, residual, and flags. A caller must not be able to receive a
  distance with no provenance.

## Numerical discipline

- Per-unit distance `m` is measured **from end S**, always. If you write a formula from a
  paper that measures from the remote end, convert it in one clearly-commented place.
- Quadratics: use the numerically stable form already in `stable_quadratic` (the
  `-b ± √…` textbook form loses precision when `b² ≫ 4ac`, which is exactly the near-end
  fault case). Report **both** roots and the rule that selected one; a root chosen by
  "whichever is in [0,1]" must say so in the diagnostics, because both roots landing in
  range is a real and meaningful condition.
- **Never clamp silently.** `m` outside [0, 1], a complex root, a non-convergent solve, a
  δ (sync angle) inconsistent between the two ends → an `Estimate` carrying the reason.
  A clamped 0.0 or 1.0 with no flag is the worst possible output: plausible and wrong.
- No `float ==`. Compare against a named tolerance and put the tolerance next to the
  physics that justifies it.
- Angles in radians internally; degrees only at display. Phasor magnitude convention
  (peak vs RMS) and primary-vs-secondary scaling are stated in the docstring of every
  function that assumes one — a P/S convention mismatch between two relays is a real
  failure mode already seen in this repo's tests.

## The test is not optional

Every maths change ships with a test in `tests/` that asserts the result against a
**synthetic case with known `m`** from `synth/generator.py`:

- sweep `m` across the line, fault type (LG/LL/LLG/LLL), fault resistance R_F, source
  impedance ratio (SIR), inception angle, sampling rate;
- assert the §13 Stage-A criterion: two-ended error < 0.5 % of line length in 95 % of
  clean cases, and no physically impossible `m` returned unflagged;
- **report the tail, not the mean** — the 90th-percentile error is the number that
  decides whether the line crew keeps trusting the tool.

Then run it on real data: `dranalyse locate --line data/registry/<line>.yaml --S … --R …`
against an archived record pair, and paste the per-method table. A green pytest alone is
not done.

## When the numbers move

A corrected formula changes historical answers. That is usually right. State the expected
step change — which estimator, which direction, roughly how much, and why — before the
user has to ask. Never quietly tune a constant to restore the old answer.
