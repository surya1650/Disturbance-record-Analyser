# Comparison and vector UI follow-up — 2026-10-30

User requested restoration of comparison playback/digitals, less vertical space,
parameter names on vectors, IA/Ia matching review and consistent end wording.

Comparison retains all analog channels in quantity/phase rows, with independent
axes and source-start coordinates. Compact plots use 88px desktop/80px mobile;
observed desktop first-row total height is250px. Play/Pause, reset and speed share
the cursor across analog and digital tracks. Playback stops at the longer source
end, when hidden, on changed source/revision or destruction; missing source tails
are not extended. Unknown/gapped digital states are never filled. Each source has
changed-first digital tracks, four initially shown, additional channels expandable.
Digital bars are recorded state1 observations, not reviewed assertions or proof
of trip/breaker operation. Display playback does not synchronize physical ends.

Vectors use informative source names; generic CH1/CH2 names use explicitly supplied
VA/IA meanings only when quantity units agree. Source names/IDs remain in tooltips
and request identities; no phase is inferred from channel numbers. Sending end(S)
and Receiving end(R) wording is consistent across primary assignments, calculation,
event report, technical evidence and printable report templates. Internal S/R
keys, physics references and historical results are unchanged.

IA/Ia case-only normalization already worked. Expanded realistic casing/phase/unit
header regression tests confirm IA vsIa/iA/I_a/I a pair without weakening ambiguous
phase, unit or digital-vs-analog guards. The user's exact mismatching record/header
has not been supplied, so no claim is made to have reproduced that specific pair.

Chromium1440x1000 and390x844 checks passed: playback/pause/reset, hidden-pane stop,
digital tracks, compact rows, no page errors or document overflow. Screenshots and
reproducible QA harness are ignored under out/qa/comparison-followup. Four Node
suites cover labeling, escaping/provenance,128analog rendering, known digital spans,
unknown gaps and requestAnimationFrame cleanup. Direct architecture/self-tests
and StageA10000 passed; cleanp95 remains .4361%, zero uncaveated impossible m.
Full-suite final result is recorded below after verification.

No engine, parser, settings or engineering gates changed. No environment draft,
publication, production deployment or main merge is part of this work.

User clarification: retain S/R end identifiers. The user will upload the actual
DRs for the remaining record-specific matching check. Browser verification using
actual decoded synthetic inventories with the right source label changed from
IA toIa confirms a single IA pair; generic CH1 with supplied VA meaning renders
VA(A1). No original capture bytes or physical channel assignments were changed.
An initial full run hit a vector fallback assertion during integration (the test
kept an explicit meaning while expecting an unnamed ID); the final test separates
missing meaning from supplied meaning and passes focused checks. The frozen tree
is being rerun completely, rather than treating that initial failure as green.

Final frozen-tree qualification: **2003 passed,28 private-corpus skips,one upstream
Starlette warning**,105.02s. Architecture/self-tests and every changed JS syntax
check pass. Stage-A10000PASS cleanp95 .4361%; no maths changes. Working tree was
reviewed with git diff --check. Review-branch push is authorized; no main merge
or environment publication is performed.
