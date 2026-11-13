# Excel source catalogue acceptance — 2026-11-13

Base: review-branch commit `4742dae`. Work was isolated from the original clean
published checkout. The private workbook and parsed source rows remain in ignored
attachments/QA storage, never in this delivery.

## Delivered behavior

Source catalogue has a separate navigation entry, preserving the four incident
tasks. Upload creates a retained preview; only **Use in catalogue** changes the
active source view. Circle/station/type/search filters, row issues, exact original
cells, original download and retained version switching are available. TL review
and legacy Google snapshot/catalogue support remain. PTR is explicitly inventory
only and rejected by both transmission-line promotion paths.

The supplied workbook reads 26 tabs, 1,961 TL and 2,006 PTR source rows. Blank
identifiers stay blank; Bus Numbers do not merge identities. No operational line
registry, incident assignment, waveform layout or analysis algorithm is changed.
Engineering review is still required before line-model use.

## Evidence

- Direct architecture check and architecture guard self-tests: PASS.
- Full pytest: **2,639 passed, 28 private-source skips**. One existing
  FastAPI/Starlette httpx deprecation warning remains.
- Focused import/model/reader/UI tests: **111 passed**. Covered ZIP/XML bounds,
  unsafe input, cached formulas, source identity, dates, duplicate semantic
  headings, independently moved zone/time columns, immutable storage integrity,
  concurrent activation conflicts, failure atomicity, auth and legacy fallback.
- Node UI tests and Ruff on all changed Python modules/tests: PASS.
- Four focused portal/UI tests plus recording-setup route checks: PASS after
  adding the separate source navigation entry; the four core tasks remain intact.
- Stage-A **10,000 PASS**, clean two-ended p95 **0.4361%** (criterion <0.5%).
- Browser checks against the supplied workbook: empty state, upload preview with
  no activation, explicit selection, TL/PTR counts, filters, source details,
  mobile geometry, version restoration, stale409 and byte-identical original
  download. Screenshots/results are retained in ignored local QA output.

Independent review found duplicate semantic heading ambiguity and adjacent-column
zone timing assumptions. Both are rejected/resolved respectively for new XLSX
imports and have regression tests. Legacy Google row hashes remain unchanged.

The existing file-growth budgets were adjusted only for the three extended Python
modules and four new modules; the Excel inventory model is a separate module.
No architecture boundaries or estimator thresholds were relaxed.

## Limits and operation

This supports the supplied TL/PTR template, not arbitrary spreadsheet schemas.
Imports are source evidence, not compliance certification, verified topology or
incident-effective settings. Parsing is bounded and runs outside the HTTP event
loop with a two-parse limit per process. History shows the latest20 uploads while
older files remain retained. No automatic cleanup or cloud service was added.

Use the [VM update and import guide](EXCEL_CATALOGUE_GUIDE.md). Review-branch code
delivery does not restart the user's Google VM. Keep the same application root
and existing tunnel; no environment publication, main merge or cloud deployment
is part of this change.
