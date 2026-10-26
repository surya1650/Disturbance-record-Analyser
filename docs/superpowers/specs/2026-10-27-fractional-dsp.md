# Fractional-window fundamental correction

The 2026-10-26 conditional-budget study measured up to1.1438625 primary A of
physical I2 bias at48 Hz/fs3500: a73-sample window is not a complete cycle.
The scalar DFT assumes orthogonal sine/cosine bases, leaking the conjugate of
positive sequence into negative sequence. Integer-cycle52 Hz/fs2600 is the
working control. This is a deterministic estimator defect, separate from noise.

Use existing Python/NumPy and a real two-basis least-squares fundamental fit on
each complete support. Reference remains absolute t=0 and RMS phasor is
(cosine coefficient - j*sine coefficient)/sqrt(2). Filter samples and BOTH bases
with the same existing mimic FIR and initialized first sample. Sliding2x2 Gram
and cross-product sums keep linear complexity. Relative determinant guard
64*machine epsilon times squared Gram trace rejects deficient supports as NaN,
never a plausible phasor (a product-of-diagonals test misses tiny basis columns).
Keep window rounding/full-half support and public signatures. Keep mimic_filter
return contract. A focused pure DSP module owns filtering/fitting/kernel weights.

Update dft_noise_radius to bound exactly this operator: compute complex output
coefficients of filtered samples and compose the FIR onto raw input, including
the prior boundary sample and initialized first window. Use the larger L1 norm
of initial and steady support plus64 ulps. Explicit uniform-grid, caller cap,
finite-parameter requirements remain. Support2..100000 samples; larger windows
are unsupported by this utility rather than consuming unbounded resources.
No floating-point interval certificate or frequency/model/gain/CT/alias/clock
guarantee is introduced. i2_budget and operational gates remain unchanged.

Tests must fail on old exact-frequency phasors before implementation. Independent
oracle uses np.linalg.lstsq/pinv on the filtered real design matrix, rather than
the production2x2 algebra. Include fractional and integer full/half windows,
nonzero absolute origins, mimicNone/0/.02/.08, initialization, balanced/weakI2,
Nyquist/singular supports, short/empty data and finite bounded perturbations.

Freeze a new disjoint parsed-record metrology grid before running it: development
47 Hz/fs3200/pre.16/negativephase.53, validation53 Hz/fs4100/pre.19/phase1.17;
I2=0,.1,10,100 primary A; all10 existing noise/coherent scenarios. These80 new
records reuse the independent generator, not historical evidence rows. Report
matched-kernel additive coverage AND physical bias separately; require zero
within-cap bound misses/numerical failures and ideal physical I2 bias<.01A
on complete clean supports. Coherent controls remain out of assumed-cap coverage.
Also replay the earlier80 records to a new file; do not overwrite historical
artifacts/manifests. Fresh Stage-A10000 must pass unchanged acceptance criteria,
and all existing parsed main/stage/noise/CT regression tests must pass. Review
the whole branch independently before integrating. If adoption gates fail,
retain research evidence without weakening gates or claiming a completed fix.

No new field data, accepted field cases, standards certification, E4/clock
promotion, operational enablement, or Dash/workbook/database changes. User
authorized autonomous inline work and integration/push without approval gates.
