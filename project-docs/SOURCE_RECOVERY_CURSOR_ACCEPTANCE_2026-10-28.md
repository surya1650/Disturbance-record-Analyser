# Main application: bounded recovery and cursor acceptance

Candidate range9d1853a..HEAD oncodex/inspection-first. G1/G2/G6 closure candidate;
fresh whole-branch review and primary verification remain before integration.

## Recoverable source contracts

- Standalone CFG/DAT and explicitly framed CFG-first CFF support ASCII, BINARY,
  BINARY32 and FLOAT32. An explicit DAT type must agree with the CFG type; an omitted
  DAT-marker type relies on the explicit CFG declaration. Unknown/conflicting formats,
  malformed separators and ambiguous tails retain a specific local reason and readable header.
- Digital-only and one/two-sample records retain exact nullable observations.
  Existing source-time/fitter minimum support stays unchanged; unavailable time means indices.
- Truncated binary data recovers complete rows from byte zero only, with counters beginning
  at0or1 and consecutive through the prefix. A broken counter stops recovery; remaining bytes
  are opaque and counted. No row padding, guessed offsets or timing model is introduced.
  Fully aligned record handling is unchanged.
- Binary CFF payload is bounded by explicit declared row width/count. Marker-like payload
  bytes are not framing. Only framed HDR/INF text may follow that boundary. Unsupported
  containers remain available as original uploads with errors; no universal CFF claim.
- CFF SHA256/content identity covers original container bytes; virtual CFG/DAT sections are
  never represented as separately uploaded files. Declared gains, ratios, normal states and
  recorded date strings remain unverified source metadata.
- Budgets remain CFG1MiB, DAT64MiB, CFF65MiB total, analog64/digital256,
  source200000samples/4000000cells and native intervals20000samples. Explicit overflow reasons
  retain original files; no silent truncation to a budget.

## Cursor behavior

One read-only point request validates one source and returns up to8channels×17unique indices.
The UI supports16pins plus hover, reuses exact loaded native observations locally, and never
uses display extrema/interpolation as cursor values. Tokens bind source hashes, revision,
record and generation. Aborted/stale results and errors cannot replace a newer record's values.
Native path loading retains up to8bounded interval requests per viewport; cursor fanout is gone.

## Measured qualification observations

Public synthetic BINARY record:64channels,50000samples,3.2million channel observations,
a50ms source-coordinate gap and explicit missing amplitudes. Inspection preserved all channels,
all sample indices and unknowns. Decimated overview12592points/338606JSONbytes.
Cold overview3.701s, warm2.697s. Exact40point batch2255JSONbytes/14.5ms.
These are local observations, not capacity, field or standards certification.

Copied real DR2/Dhone source inspection retains1800/3624samples and40channels each.
All26original source hashes and the real pending revision matched the preserved baselines.
Protected previews8091/8113/8092, originals/Downloads/workbook/Dash/live appDB were not changed.
Disposable8094 uses out/qa/inspection-first/app only.

QA scripts/logs/results are ignored under out/qa/source-recovery; preserve them plus all earlier
milestone QA and scoped ledgers, verifying hashes before native worktree archival.
Full isolated release1785PASS/29skip (28absent private corpus and1Windows symlink permission),
one existing Starlette warning275.49s. Architecture and changed-file Ruff passed.
Three older truncated-binary controls now assert95complete rows/no fabricated final row and
timing withheld, matching the deliberate recovery contract. Study artifacts/fitter policy unchanged.
Fresh final review, primary outcomes and actual browser scope follow here.
