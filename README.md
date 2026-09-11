# Two-ended disturbance record analyser

Automated analysis of disturbance records from distance protection relays at
**one or both** terminals of a transmission line. For every line fault it
produces a fault location with a diagnostic interval, the method
that produced it, and the evidence for and against.

The interval is not calibrated confidence coverage. Operational field accuracy
requires verified line data and independent patrol-confirmed outcomes.

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
| FOLD/APTRANSCO standards audit (recording, zones, RLD calculation) | working |
| Zone-decision back-test over an archive | working |
| Two-page incident report | working |
| Ground-truth capture: store, form, accuracy dashboard | working |
| Stage-A acceptance sweep | working |
| Local application, manual upload, durable jobs and report revisions | working |
| Collector intake through watched folder and push API | working |
| Reviewed stage associations, clock evidence and guarded stage E5 | implemented; bounded synthetic validation |
| Autonomous event pairing and direct relay protocol collectors | not started |

Latest validation: **666 tests**, architecture checks, Stage-A 10,000 PASS
(clean located p95 0.4361%; 25/4,283 clean cases refused) and desktop/mobile browser checks. Separate stage E5 requires
matching source-bound reviews and explicit selection at both terminal primaries;
the main ensemble refuses supported nonstationary windows. See
[stage-location validation](project-docs/STAGE_LOCATION_VALIDATION.md) for
limitations and runtime details. The main solver also refuses indistinguishable
E5 roots, external patrol assignments and declared unsupported electrical models.
See the [TB/field validation audit](project-docs/TB854_FIELD_VALIDATION_2026-09-11.md)
for completed software checks and the verified-data requirements still blocking
full TB 854 and field validation.

### Stage-A acceptance (brief section 13)

**Historical baseline before the 2026-09-11 refusal changes:** PASS over 100,000 synthetic incidents sweeping `m`, fault type,
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

### Local browser application

On Windows, double-click **`start-local.cmd`**, then open
**http://127.0.0.1:8091**. The launcher creates `.venv` and installs the app
dependencies on first use. For an existing environment, run
`powershell -ExecutionPolicy Bypass -File .\start-local.ps1 -Install` once.

Upload matching CFG/DAT files, a CFF, a ZIP, or an entire event folder. Confirm
the line and terminal assignments, then analyse. The application includes a
persistent job queue, report history, late-record attachments, retries, a
watched inbox and a shared intake API. It uses the existing numerical analyser.
Records and results stay under `out/application`.

See [local application setup and integration contracts](project-docs/LOCAL_APPLICATION.md).
The current app includes all-relay evidence, separate Main-1/Main-2 identity,
trigger-relative digital intervals and windowed phase RMS/peak measurements.
Pairwise operation comparisons and advisory onset-correlation candidates are
documented in [operation association validation](project-docs/OPERATION_ASSOCIATION_VALIDATION.md).
Per-relay recording profiles, digital-point completeness and settings screens are
documented in [checklist validation](project-docs/RECORDING_PHILOSOPHY_VALIDATION.md).
Linked waveform, phase-phase R-X, digital interval and logical SLD inspection is
documented in [navigation validation](project-docs/NAVIGATION_VALIDATION.md).
Exact-record channel mapping review and native waveform interval inspection are
documented in [mapping and sample validation](project-docs/CHANNEL_MAPPING_VALIDATION.md).
Reviewed AG/BG/CG and separate phase/earth zone-boundary inspection are documented
in [R-X input validation](project-docs/RX_INPUT_VALIDATION.md). Reviewer declarations
do not establish verified field settings or TB 854 validation.
See the [operational workflow delivery status](project-docs/DR_OPERATIONAL_WORKFLOW_PLAN.md)
for implemented behavior, bounded validation and remaining work.
The older `dranalyse workbench` remains available on port 8090.

### Command-line tools

```bash
pip install -e ".[app,dev]"

dranalyse stage-a --cases 10000             # full acceptance sweep
dranalyse template mylinedata.yaml          # starter line definition
dranalyse inspect record.cfg --kv 220       # parse and describe one record
dranalyse settings relay.rio --ct 800 --vt 2000    # read relay settings
dranalyse standards record.cfg --line line.yaml --rio relay.rio  # standards gaps
dranalyse standards --show-context --asset-type transformer      # source chunks
dranalyse locate  --line line.yaml --S a.cfg --R b.cfg   # two-ended
dranalyse verdict --line line.yaml --S a.cfg             # protection verdict
dranalyse report  --line line.yaml --S a.cfg -o out.html # two-page report
dranalyse backtest ARCHIVE/ --line line.yaml             # zone-decision replay
dranalyse capture --port 8080               # ground-truth capture form
dranalyse pending / confirm / accuracy      # patrol confirmations
pytest -q                                   # regression suite
```

The engineering rules derived from the local standards pack, their source
pages and the boundaries of what can be proved are recorded in
[`project-docs/STANDARDS_CONTEXT.md`](project-docs/STANDARDS_CONTEXT.md).

CIGRE TB 854 methods, applicability to the current estimators, source cautions,
and proposed improvements are mapped in
[`project-docs/CIGRE_TB854_METHODS.md`](project-docs/CIGRE_TB854_METHODS.md).
Retrieve its advisory entries with
`dranalyse standards --show-context --source cigre-tb854`.

The [TB 854 validation matrix](project-docs/TB854_VALIDATION_MATRIX.md) separates
implemented methods, bounded test evidence and unsupported physics. Repository
test passes are not TB 854 validation or proof of field accuracy.

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
