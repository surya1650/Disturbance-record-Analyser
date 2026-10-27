# Scalar observability study —2026-10-27

The separately frozen necessary-condition screen rejects every harmful CT case
in this grid, but **fails the adoption gate**. Coherent gain, polarity and aliased
fundamental errors still pass and can produce large scalar-location errors.
The candidate remains offline; production gates and the research-DSP adoption
hold are unchanged. Nothing here establishes field acceptance or clock alignment.

## Experiment and decision boundary

A new120km uniform phase-network study uses development37km/Rf3 and holdout83km/
Rf7,11 fault connections,2source profiles per split and14scenarios:616 parsed
paired incidents. Sampling47.5/51.5Hz,3000/1800 versus3600/2200Hz, phases, seeds,
timing, CT burdens and initial flux biases are disjoint from the prior grids.
Independent nodal and toy nonlinear CT oracles supply physical waveforms; the
existing independent integer20bit COMTRADE writer is loaded in an isolated
namespace and calls the public parser. Historical generator defaults are intact.

The pure candidate consumes actual legacy analyses, measured scalar-consensus
fault and every complete selected local support. It rejects known blocked/
multi-rate acquisition, invalid metadata/polarity/grid, detected saturation,
clipping, missing/nonfinite streams, transitions and an individual I2 below the
existing section floor max(1% medianI1,1e-6 primary A). ABC/ABCG/NONE cannot use
a positive-sequence substitute in this negative-sequence study. Passing means
only that these necessary checks found no refusal; it never authorizes location.

The overlay preserves an existing scalar location exactly or suppresses it;
it does not run a replacement solver. Independent waveform quadrature computes
measurement and CT errors separately. Truth fault, chainage and error metrics
never enter the candidate. No thresholds were tuned after observing results.

| Result | Development | Validation | Total |
|---|---:|---:|---:|
| Planned/evaluated incidents |308|308|616|
| Numerical failures |0|0|0|
| Candidate passes |58|58|116|
| Candidate refusals |250|250|500|
| Baseline scalar locations |284|267|551|
| Overlay locations |58|58|116|
| Baseline located errors>1km |135|104|239|
| Overlay located errors>1km |27|32|59|
| Harmful CT incidents (>5% current error) |58|29|87|
| Harmful CT candidate passes |0|0|0|
| Harmful measurement candidate passes |36|36|72|
| Clean unbalanced candidate passes |9|9|18|
| Balanced overlay locations |0|0|0|

Maximum overlay error is**45.02455km** (development/baseline/AG/polarity,case11);
the declared scalar polarity remains+1 while the sourceIA waveform is inverted.
No shape or relative-sequence test establishes that declaration's truth.
All72 harmful passes are coherent gain_i/gain_v/polarity/alias controls,18 each.
Both gain scenarios produce18 errors>1km; polarity15 and alias8 add the rest.
All18 clean unbalanced locations have error<=.207856km in this bounded study.
All44 metadata-skew cases match corresponding clean candidate/baseline outputs
exactly; clock alignment eligibility remains0. This is local-timing invariance,
not synchronization recovery. Both weak-source cohorts and all white/colored
noise cases are withheld; this conservative policy does not solve noisy-input
availability. Of44ct_single incidents,8 mild cases pass; none is harmful by the
independent>5% definition. Rejecting87 harmful CT cases does not certify all CTs.

## Limits and next software work

The gate fails on72 harmful measurement passes and59 errors>1km despite zero
numerical failures. Lowering a noise/saturation threshold to gain coverage would
not establish gain, polarity, anti-alias or clock provenance. Production adoption
and the fractional-window default remain HELD. The source model is sinusoidal
state splicing, not EMT; the CT is a secondary-referred memoryless toy excitation
curve, not manufacturer hysteresis/remanence. Initial flux is a bias only.
Truth quadrature and the5% harm/1km gates are study definitions, not calibrated
confidence or a protection standard. Sampling and model errors remain separate
from conditional additive bounds. Source asymmetry beyond these profiles and
field performance have not been established.

Next mathematical work can propagate explicit two-terminal phasor-error bounds
through E5/section observability to show when a defensible distance interval is
possible. Caller assumptions must stay distinct from field measurement/error
provenance. Field gain/phase/CT/anti-alias calibration, line/topology review and
accepted fault ground truth remain external evidence requirements. This study
does not justify operational lines or clearing current refusals.

## Reproduction and verification

[Full616-case evidence](validation/SCALAR_OBSERVABILITY_2026-10-27.json) binds44
UTF-8/LF sources from protocol/code freeze907092b. Every failure, refused case,
support diagnostic, baseline and overlay remains visible. CLI publishes finite
JSON exclusively and returns2 on numerical failure; scientific adoption failure
is recorded separately. Never rewrite old manifests to imply later-source
validation. Candidate is an unused pure module; existing consumer sources are
unchanged. Dash's two findings hashes match their prior local values.

```powershell
$env:PYTHONPATH='src;.'
$env:OPENBLAS_NUM_THREADS='1'
& 'E:\dr analyser\.venv\Scripts\python.exe' -m pytest tests/test_scalar_quality.py tests/test_scalar_observability_validation.py -q
& 'E:\dr analyser\.venv\Scripts\python.exe' scripts/scalar_observability_validation.py --output out/qa/new-scalar-study.json
```

TDD:33 candidate and13 source/runner tests failed before implementation;46
focused tests pass. Isolated baseline1373passed/28corpus skips,252.09s; release
**1419passed/28corpus skips**,237.80s, each with one existing upstream warning.
Architecture/focused Ruff pass. Existing production sources are unchanged, so
the previous Stage-A10000 remains historical; no new Stage-A result is claimed.
Fresh whole-branch review and combined primary delivery follow below. Project
remains advanced prototype/pre-pilot with zero accepted field cases.
