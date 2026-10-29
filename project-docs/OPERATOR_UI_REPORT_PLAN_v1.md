# Operator UI and simple report

2026-10-29. User authorized reviewing and improving the current draft. Preserve the
channel comparison changes and published baseline. No publication is requested.

## Problem and scope

Current source inspection combines waveform controls, channel mappings, line inputs,
report, technical windows and comparison in one long panel. Required line inputs are
visible even when the operator only wants raw waveforms. The source report contains
supported A/B condition values, but these compete with diagnostics and the line
projection appears far from the basic interpretation.

Implement a consistent accessible task workspace: Waveforms, Simple report, Inputs
& help, Compare and Technical evidence. Put optional operational/history tools behind
a clear disclosure. Add plain descriptions, feature-specific required/optional input
lists, availability and next actions. Preserve the current record/revision source binding.

Lead the report with selected pre-fault/fault/post-fault supported RMS values, distance
with its method/reference and caveats, analog changes and conditional digital
indications. Use one serialized report model for screen, JSON and printable HTML.
No bounds means no fabricated pre/fault/post values. No physical breaker opening
or successful reclosing inferred solely from command indications.

## Constraints and standards basis

PROJECT_CONTEXT section 2 remains binding. Keep original observations, parser,
estimators, four-cycle/stationarity policies, ratios and database untouched. Existing
source inspection reports stay selected-record evidence within one incident. E5 does
not acquire a clock-sync requirement. A conditional line projection is not an adopted
operational fault location. UI organization, spacing and motion are project policy;
no standards certification is claimed. Use WAI-ARIA tab roles, keyboard operation,
focus visibility and reduced-motion handling as accessibility design guidance.

## Phases

1. Pure feature requirements and report models, including adverse/missing/null/zero,
   unavailable fitting, unreviewed digital polarity and outside-line distances.
2. Task panels and explanatory controls, consistent styling, reduced-motion-aware
   transitions and same-source report/export integration.
3. Browser desktop/mobile/keyboard and actual downloads; focused tests, architecture,
   full tests and Stage-A 10,000. Record the actual supported scope and remaining
   production/browser/field qualification limits.

## Acceptance and data impact

Raw inspection requires only readable source data; additional inputs belong to the
chosen calculation. Values retain units/assumptions and exact applied A/B bounds;
changed choices clear stale reports. All optional report fields have a specific
unavailable explanation. No new services, dependencies, schema migration or numerical
result changes. The UI consumes bounded existing API data; report computation is
bounded by the existing channel/window/digital response limits.

Scalability acceptance here is responsive bounded source inspection, clear failure
states and deterministic explanations. Distributed authenticated multiuser hosting,
fleet ingestion and universal relay/field qualification require separate architecture
and operational evidence; this UI change does not claim to complete them.
