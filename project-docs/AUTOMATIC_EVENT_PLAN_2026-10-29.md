# Automatic intervals and notation follow-up

The user requests automatic pre/fault/post interval selection, at least four
visible digital rows, and consistent case/separator variants such as Ia/IA/I_A.

Use the existing canonical mapper for bounded label/header suggestions, preserving
original channel IDs/labels, explicit choices, quantity conflicts, ambiguous
duplicates, R/Y/B context and distinct residual/derived measurements.

Automatic display intervals use actual-time one-cycle RMS changes with documented
display policies and recorded indication evidence. They never turn the CFG trigger
into fault inception, a trip command into breaker opening, or an unavailable cycle
into a reported value. Retain per-source boundary support/reasons, partial coverage,
manual overrides and a clear warning for additional events. Recompute automatic
choices server-side for report/save; never trust client-supplied detection evidence.
Do not change operational DSP or fault-location algorithms/thresholds.

Default new report selections to automatic timing. Show a concise time summary;
keep sample-index editing inside manual adjustment. Preserve historical manual
selections and reject stale asynchronous record/choice responses. Digital channels
remain below analogs, changed first, with at least four selected by default when
available and a pane large enough to show four compact tracks.

Verify notation/ambiguity, synthetic known event timing across rates/faults,
steady/short/gapped/ongoing/reclose recordings, source-bound API persistence,
automatic/manual UI transitions and four visible tracks in Chromium. Run direct
architecture checks, full pytest and Stage-A10000 before pushing the authorized
review branch. Private records and browser artifacts remain under ignored out/qa.
