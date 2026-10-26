# Finite inspection timebase for invalid acquisition

Invalid DAT timing is blocked but should remain inspectable. Its fallback
currently multiplies untrusted nominal line frequency by20. Huge nominal
frequency overflows the sampling rate; tiny frequency overflows display time.
This is the previously deferred malformed-frequency Minor, now in the user's
authorized further-software scope.

Use fixed1000Hz only when invalid acquisition has no usable fitted DAT period.
Label it a fixed inspection placeholder. Retain statusinvalid, alignment false
and the parser TIME-DAT block. The existing finite positive untrusted DAT fit
for gap/jitter/drift remains unchanged. Declared valid sample rates and bounded
timestamp recovery are unchanged. Do not normalize malformed line frequency
into trusted acquisition or enable analysis/location/clock alignment.

TDD direct and public-parser huge/tiny/nonfinite/ordinary nominal frequencies
must yield finite positive fs, finite strictly increasing display grid, invalid
provenance and block. Existing30 timestamp tests, full regression, architecture
and focused Ruff must pass. Preserve historical manifests; changed hashes are
historical bindings, never rewrite them. No new field data or Dash/input/DB edits.
