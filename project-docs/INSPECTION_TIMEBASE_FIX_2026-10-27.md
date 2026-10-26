# Invalid-acquisition inspection fallback —2026-10-27

The previously deferred malformed-frequency display bug is fixed. When DAT
timing is invalid and supplies no usable fitted period, inspection now uses a
fixed1000Hz placeholder. Untrusted nominal frequency no longer determines the
display rate. A huge nominal frequency previously overflowed fs; tiny values
produced nonfinite display time. Both prevented useful inspection of a record
that was already correctly blocked for analysis.

This does not recover acquisition. Invalid status, TIME-DAT block and ineligible
clock alignment remain. Valid declared/recovered grids and the existing finite
untrusted DAT fitted-period path are unchanged. No acquisition/location gate or
field metadata is promoted. Source captures, workbook, DB and Dash are untouched.

Six direct/public-parser cases failed first on1e308,1e-320 and1e-308 nominal Hz.
After the fix, all16 new huge/tiny/nonfinite/ordinary controls and30 existing
timestamp tests pass: **46 focused tests**. They verify finite positive rate,
finite increasing display times, invalid provenance, parser blocking and no
clock verification/alignment/application. Existing slow-deviation tests retain
their fitted inspection period. Architecture and focused Ruff pass.

Historical numerical manifests continue to bind their original source versions;
they are not rewritten to claim this checkout. This bounded inspection fix is
not field acceptance or a standards certificate. Full regression, independent
review and primary delivery are recorded below when complete.
