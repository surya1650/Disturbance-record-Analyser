# Fractional-window DSP study â€” 2026-10-27

The physical fundamental correction is validated for the specified synthetic
model, **but production adoption is held**. Rounded sample supports mix the
conjugate fundamental into the scalar DFT. Fitting filtered cosine/sine bases
jointly removes that deterministic leakage, including mimic startup and half
windows. It does not establish that corrupted measurements support a location.

## Numerical results and scope

The new independent grid uses47Hz/fs3200 and53Hz/fs4100, disjoint phases/seeds,
and80 six-channel integer COMTRADE records. The public parser, actual tracked
frequency/tau and raw current channels feed an explicit research adapter; no
oracle phasor is substituted into measured data. Physical truth is compared
separately from matched-operator perturbations. Independent SVD/pseudoinverse
tests check production2x2 algebra and composed raw FIR coefficients.

| Explicit research metrology | New grid | Historical-grid replay |
|---|---:|---:|
| Records evaluated / failed |80 /0|80 /0|
| All complete supports |87,720|73,160|
| Supports within declared error caps |61,404|51,212|
| Within-cap bound misses |0|0|
| Within-cap conditional statuses |8,772|7,316|
| Conditional >5% physical I2 error within caps |0|0|
| Maximum ideal physical I2 bias, primary A |0.000424212|0.000907113|

The old-grid ideal bias was1.1438625A. Fractional pure-sinusoid tests recover
physical phasors within1e-8A; a100,000-sample diagnostic reached~2.6e-9A.
The remaining parsed-record ideal bias includes tracked-frequency mismatch.
The hard peak sample caps are assumptions, not estimates from sine residuals.
Twenty-four coherent gain/polarity/fundamental-alias controls in EACH grid
deliberately violate ADC-only caps: their conditional statuses and large
physical errors are outside verified coverage. An unbounded Gaussian process
does not become deterministically bounded by its observed maximum.

The `.01A` physical-bias ceiling is a frozen research criterion, not a field
accuracy standard. Floating accumulation is tested numerically, not formally
interval-certified. Uniform-grid, correct-frequency model assumptions, rank
guard64eps times squared Gram trace and research2..100000-sample domain remain
explicit. Unsupported research supports return unavailable phasors/bounds.

## Why the production default stays unchanged

A trial with the corrected method as the default passed every regression and
the existing Stage-A clean criterion, yet produced new bad outputs. Comparing
the same10,000 Stage-A incidents changed two saturatedABC refusals to locations:
seed8410 error0.035684% and seed9984 error**6.212321%** of line length. At9984,
the S terminal is detected saturated and calledAG while R is calledABC with
weakI2. Existing scalar logic downweights saturation and reconciles the calls;
small corrected-R changes alter E5/root validity and release a blended output.
No threshold or clock policy was changed. A clean-data p95 gate misses this.

| Full workflow trial | Historical default | Corrected-default trial |
|---|---:|---:|
| Stage-A located / refused |9,242 /758|9,244 /756|
| Stage-A clean p95 (% of line) |0.4361|0.4411|
| Parsed three-phase incidents / workflows |552 /1,104|552 /1,104|
| Parsed workflows located / refused |168 /936|226 /878|
| Located error above1km |57|76|
| Balanced-control locations / E4 outcomes |0 /0|0 /0|
| Harmful CT quality passes |0|0|
| Harmful joint quality passes |81|81|

The full-record trial has zero numerical failures, but the acquisition
candidate's adoption gate still fails. Its81 harmful joint passes comprise
coherent-bias counterexamples and the previously found colored balanced
control. Maximum located error remains~24.311km under a polarity defect.
This study is not a safe-location or acquisition-quality approval.

Final code therefore preserves `sliding_dft`'s historical default and matching
`dft_noise_radius` bound. Both expose `method='basis'` explicitly for research;
no production pipeline/location caller selects it. A real seed9984 RED/GREEN
refusal regression and independent legacy-formula comparison protect that
decision. The new fit and its raw-input error bound remain available for further
study. Production fractional-window bias and noisy-input refusals persist.

## Evidence, reproduction and remaining work

Use the current explicit-opt-in
[new-grid HELD evidence](validation/FRACTIONAL_DSP_DISJOINT_2026-10-27_HELD.json)
and [historical-grid HELD replay](validation/FRACTIONAL_DSP_HISTORICAL_REPLAY_2026-10-27_HELD.json),
each binding16 UTF-8/LF sources at the adoption-hold implementation28d609b.
Earlier unqualified files bind the default-change trial27cdec2 and remain
historical. The [552-incident trial](validation/FRACTIONAL_DSP_FULL_RECORD_REPLAY_2026-10-27.json)
binds its29 historical sources; its corrected kernel is additionally bound by
the earlier16-source metrology manifests. Never rewrite old bindings to imply
that they validate a later checkout. Full CSV/QA traces stay locally in ignored
`out/qa/fractional-dsp-2026-10-27/` after archival.

```powershell
$env:PYTHONPATH='src;.'
$env:OPENBLAS_NUM_THREADS='1'
& 'E:\dr analyser\.venv\Scripts\python.exe' scripts/fractional_dsp_validation.py --output out/qa/new-research-run.json
& 'E:\dr analyser\.venv\Scripts\python.exe' scripts/fractional_dsp_validation.py --historical --output out/qa/new-historical-replay.json
```

Next software work is a separately frozen conservative scalar saturation/
weakI2 observability policy, checked on disjoint faults and the counterexamples,
before reconsidering this default. Do not tune against published holdouts or
infer polarity/gain/alias/clock truth from waveform shape. The malformed-
frequency inspection fallback also remains pending. No field cases have been
accepted; project remains advanced prototype/pre-pilot, without standards or
operational certification. Dash/source captures/workbook/database are unchanged.

Verification: initial corrected-default full suite1317passed/28corpus skips;
198 final focused tests pass. Final held-default/full/Stage-A and independent
review results are recorded below when complete.

Held-default release: **1,351 passed /28 corpus skips**, one existing upstream
Starlette/httpx warning,85.53s. Fresh default Stage-A10000 PASS,9,242located /
758refused,clean p95.4361%,31.1s. All categorical fields match the prior10,000
rows; maximum numeric metric difference is1.3e-11 percentage points from floating
arithmetic ordering. Both newly released trial outputs are refused by default.
Architecture direct/self-tests and changed-file Ruff pass. Fresh independent
review and final primary delivery follow below.
