# Continuation: source catalogue and acceptance readiness

Resume from `fe99a06`; the baseline is 666 passing tests and an unchanged working tree.
The user authorized completing remaining work possible without additional field data,
and supplied a Google Sheet as an input. Preserve existing recordings, registry
definitions, application databases and saved report revisions.

## Delivery sequence

1. Acquire an immutable local snapshot of the 13 transmission-line tabs, with
   source version, exact row/cell locators and checksums. Parse lengths, sequence
   impedances, instrument ratios and settings references; report missing/conflicting
   values. Keep transformer tabs outside the line solver. Never publish source rows.
2. Add a reusable catalogue importer, conservative reciprocal-end candidate search,
   and source-bound reviewed registry export. Do not interpret a bus number as a
   unique bay/SAP/circuit ID, fill down missing IDs, assume settings impedance bases,
   convert incomplete reach vectors into quadrilateral polygons, or infer Main-1/2.
   Expose the imported catalogue through the local application and CLI.
3. Implement a reproducible held-out acceptance evaluator with explicit truth/input
   provenance, duplicate-event/leakage checks, refused-case accounting and diagnostic
   interval coverage reporting. Provide an empty real-data manifest; do not create
   confirmations or field-accuracy claims from the source workbook.
4. Complete practical non-field workflow gaps exposed by this work, validate the
   source against the available corpus read-only, and update the handoff/status docs.

## Validation boundaries

The existing clean synthetic acceptance threshold is a project criterion, not a
CIGRE accuracy requirement. A workbook date/reference is not proof of event-effective
relay settings, correct field wiring, approved topology, or patrol truth.
New general coupled/distributed electrical models and CT/CVT reconstruction require
their own independent physical validation; importing data cannot establish them.
Keep the present model-domain refusals until such implementations are validated.
Travelling-wave and per-relay learned fault location remain excluded by project scope.
