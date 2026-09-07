# Two-ended disturbance record analyser

Automated analysis of disturbance records from distance protection relays at
**one or both** terminals of a transmission line. For every line fault it
produces a fault location with a defensible confidence interval, the method
that produced it, and the evidence for and against.

Single-ended and double-ended are one code path, not two. The ensemble takes
whatever terminals are present and gates each estimator on what the data can
actually support, so a single-ended report issued now can be re-issued as a
corrected two-ended report when the far-end record arrives late.

See [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md) for the full brief. Section 2
of that document is binding: several plausible-looking approaches are ruled
out there with reasons.

---

## Status

| Area | State |
|---|---|
| COMTRADE parser (1991 / 1999 / 2013, ASCII / BINARY / BINARY32 / FLOAT32, `.CFF`) | working |
| Conformance gate | working, 13 checks |
| DSP chain (frequency tracking, mimic filter, sliding DFT, sequence, superimposed, inception, classification, CT saturation, window selection) | working |
| Estimators E1, E2, E3, E4, E5 + E6 ensemble | working |
| Synthetic fault generator (the test oracle) | working |
| Tier 1 line-parameter estimation | working |
| Tier 2 hierarchical residual correction | implemented, **gated off** until 100 confirmed events |
| Tier 3 classifiers trained on synthetic labels | working |
| Relay settings reader (`.rio`), incl. backup O/C and E/F stages | working |
| Conclusions engine, 25 rules, 21 needing no fault location | working |
| Zone-decision back-test over an archive | working |
| Two-page incident report | working |
| Ground-truth capture: store, form, accuracy dashboard | working |
| Stage-A acceptance sweep | working |
| Pairing, transport, edge collector | not started |

### Stage-A acceptance (brief section 13)

**PASS**, measured over 100,000 synthetic incidents sweeping `m`, fault type,
fault resistance, source impedance ratio, inception angle, CT saturation,
sample rate, ADC resolution and noise, through the full DSP chain, with up to
2 s of clock skew between terminals:

```
clean data   n=42657   mean 0.121 %   p90 0.305 %   p95 0.465 %   max  4.9 %
everything   n=99221   mean 2.202 %   p90 3.150 %   p95 11.30 %   max  141 %
```

The criterion is under 0.5 % in 95 % of clean-data cases. **It passes with a
thin margin, not a comfortable one** — 0.465 against 0.5, stable across seeds
(0.419–0.468 over five 5,000-case runs).

Both columns are quoted deliberately. "Clean" means no CT saturation, no weak
infeed, moderate fault resistance and a full-cycle window; quoting only that
figure would describe a system nobody recognises in the field. The honest
summary is that **CT saturation is the dominant unhandled error source**:
saturated cases average 10.7 % against 0.12 % for clean ones. It is detected
and down-weighted, not compensated.

Accuracy improves monotonically with sample rate — p95 of 0.47 % at 12
samples per cycle against 0.31 % at 96 — which is the concrete argument for
the recording-settings change in the brief's section 4.3.

---

## Install and run

```bash
pip install -e ".[dev]"

dranalyse stage-a --cases 10000             # full acceptance sweep
dranalyse template mylinedata.yaml          # starter line definition
dranalyse inspect record.cfg --kv 220       # parse and describe one record
dranalyse settings relay.rio --ct 800 --vt 2000    # read relay settings
dranalyse locate  --line line.yaml --S a.cfg --R b.cfg   # two-ended
dranalyse verdict --line line.yaml --S a.cfg             # protection verdict
dranalyse report  --line line.yaml --S a.cfg -o out.html # two-page report
dranalyse backtest ARCHIVE/ --line line.yaml             # zone-decision replay
dranalyse capture --port 8080               # ground-truth capture form
dranalyse pending / confirm / accuracy      # patrol confirmations
pytest -q                                   # 229 tests
```

Real disturbance records are **not** in this repository (see
[`.gitignore`](.gitignore)); every test that needs them skips cleanly.

---

## What is different from the brief, and why

The brief was reviewed before implementation. Corrections carried into the
code, each with the reasoning in the relevant docstring:

**E2 (Takagi).** The brief's denominator uses the raw phase current `I_S`.
The defining equation is `V_loop = m*Z1L*I_loop + R_F*I_F`, so it must use the
compensated **loop** current. With `I_ph` the error is of order
`|k0*3I0 / I_loop|` — tens of percent on a solid single-phase-to-ground fault.

**E3 (modified Takagi).** The brief writes `exp(-j*beta)` and never defines
the sign of `beta`. Deriving it, cancelling the `R_F` term needs
`conj(3*I0)*exp(+j*beta)` with `beta = arg(d0)`. The opposite sign applies the
homogeneity correction backwards, roughly doubling the error it exists to
remove.

**E4.** The brief does not say what to do with the imaginary part of `m`.
`Re(m)` is the answer and `|Im(m)|` is returned as a free quality metric — a
large imaginary part means a ratio error, a polarity error or misalignment.

**E5.** The brief's algebra is correct (verified), but it says only "solve;
take the root in [0,1]". The leading coefficient is
`|Z1L|^2 * (|I2S|^2 - |I2R|^2)`, which vanishes for a fault near the
electrical midpoint of a line with comparable sources — the commonest case,
not a corner case. Solved with a numerically stable formulation that
degenerates to linear, and the root is chosen by **sync-angle stability
across the window**, which needs no clock.

**MS-03.** The brief proposes checking the recovered `delta` against the
offset implied by the two trigger timestamps. `delta` wraps every 20 ms, so
that check needs clocks good to well under a cycle — which is exactly the
condition under which you would not need E5. Replaced by delta stability
across the window, and by cross-checking the negative-sequence delta against
the superimposed-positive-sequence delta.

**Pairing order.** The brief filters on time (±5 s, widened to ±60 s) before
electrical corroboration. The measured skew between two relays *in the same
bay* in the source corpus is **1418 seconds**. Electrical corroboration has to
come first; time is the weakest evidence available, not the second strongest.

**k0 conventions.** The brief's registry field is "k0 mag & angle". A
SIPROTEC stores two real ratios, `RE/RL` and `XE/XL`, whose complex `k0` has
an angle that vanishes if you copy `XE/XL` into a magnitude box. The registry
stores the vendor's native form and derives `k0`. Worked from a real settings
file: `RE/RL = 1.020`, `XE/XL = 0.800`, line angle 81° gives
`k0 = 0.806 ∠ −2.417°`, not `0.800 ∠ 0°`.

**Tier 2 cap.** The brief caps the learned correction at ±2 % of line length.
On a 300 km line that is 6 km, about twenty spans, which is not a guardrail.
The cap is `min(2 % of length, 1.5 km)`.

**Tier 2 shipping criterion.** "Beats the raw two-ended estimate" is not
sufficient: capping a correction pulls every estimate slightly towards the
fleet mean, which shrinks MAE by a percent or two *on pure noise*. Shipping
additionally requires a minimum effect size and a paired bootstrap whose 5th
percentile is still an improvement.

---

## Machine learning

Per-relay learned fault location is **not** built, for the reason in the
brief's section 2.1: a line sees 1–3 faults a year, a fraction get a
patrol-confirmed location, and the label noise is about one span — the size of
the error being corrected. The learning layer is three tiers instead.

**Tier 1 — parameter estimation, not learning.** `E5` gives `m` without using
any zero-sequence data, which leaves `k0` as the only unknown in the
single-ended ground-loop equation. Least squares over a few events recovers
the line's actual `Z0`. Tested by entering `Z0` 22 % high and recovering it to
within 5 %. This improves every subsequent single-ended calculation,
including the one the relay itself performs.

**Tier 2 — hierarchical residual correction.** Fixed effects on features
available at prediction time, plus **two** random effects per line shrunk
towards the fleet mean by empirical Bayes. Refuses to fit below 100
confirmed events, caps its own correction, always reports the raw physics
estimate alongside, and validates leave-one-**line**-out — never a random
split, which leaks the same line across train and test.

**Tier 3 — ML where labels are plentiful.** Fault type and CT saturation are
trained on the synthetic generator, which produces labels in unlimited
quantity. Every model here is a **second opinion**: the physics classifier
runs first and its answer is what the estimators use; disagreement raises a
finding for a human.

---

## Layout

```
src/dranalyser/
├── signals.py           canonical Record and Flag
├── comtrade/
│   ├── parser.py        CFG/DAT/CFF reader, written from the standard
│   └── conformance.py   the gate: 13 checks, block / flag / info
├── dsp/
│   ├── core.py          frequency tracking, mimic filter, sliding DFT, sequence
│   ├── detect.py        inception, classification, saturation, window selection
│   └── pipeline.py      the whole chain over one record
├── faultloc/
│   ├── estimators.py    E1-E5, pure functions of phasors and line parameters
│   └── ensemble.py      E6 reconciliation; single- and double-ended entry point
├── registry/            line, sections, towers, settings, k0 conventions
├── synth/generator.py   the test oracle: two-source phase-domain fault model
├── ml/                  tier1 / tier2 / tier3
└── cli.py
```

## Known gaps

- No far-end record exists in the source corpus, so the two-ended path has
  never run on real data. Recovering a genuine two-ended pair is the single
  highest-priority work item.
- Long lines use a lumped series model. Above roughly 150 km at 400 kV the
  distributed-parameter correction is needed before the quoted accuracy holds.
- Series-compensated lines are detected and **refused**, not approximated.
- Three-terminal and tapped lines are not handled.
- Pairing, transport, the rules engine and the two-page PDF report are
  specified in the brief but not built.
