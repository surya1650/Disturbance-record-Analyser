# Local analysis workbench — plan v1

Written 2026-09-07. Requested: *"run the program in my localhost … analysed
with the files with uploading … manual analysis need to be there."*

**Status: P1, P2 and P3 built and verified on 2026-09-07. P4 not started.**
Approved with the recommended defaults on both build-shaping questions in §9:
bound to `127.0.0.1` only, and bundles persist under `out/bundles/`.

P3 landed differently from the plan, deliberately. The plan proposed changing
`incident_features` and `report/build` to key on a list per terminal. That was
not done: those signatures are analytical surface, and changing them to add a
presentation feature risks moving a number for no gain. Instead the
corroboration lives entirely in `workbench/corroborate.py`, which analyses
every record at each end, reduces each to quantities two relays can be
compared on, and raises XR-01 to XR-04 on disagreement. The primary record
still drives the estimators through the unchanged API. Code is truth; this
paragraph records the divergence.

---

## 1. Problem

Today the only way to analyse a record is to type its path on a command line,
and the command line cannot express the thing being analysed.

**Evidence, from a real run today on `drs sphoorthi/` (event 15665, Maradam
LINE 205):**

1. **A four-record incident cannot be represented.** Event 15665 has four
   records: GE D60 and MiCOM P444 at Garividi, Siemens 7SA522 and the
   "MARADAM" recorder at Maradam. `dranalyse report` accepts exactly two
   paths, `--S` and `--R`. Two of the four must be discarded at the command
   line. §5.3 says one incident absorbs Main-1 *and* Main-2 records at each
   end; the CLI cannot do it.

2. **The end assignment is unchecked operator input.** `--S` and `--R` are
   taken on trust. On event 15662 the CFG station name reads `MARADAM 2` for
   a record that is electrically at the Garividi end (it measures 15,684 A
   against Maradam's 6871 A). An engineer assigning ends by reading the
   header would get a confidently mirrored answer. CLAUDE.md already forbids
   inferring the terminal from argument order; today's CLI does exactly that.

3. **The incident has no identity.** The run registered
   `Relay-1-20260820T113637-b9652f` under line id `UNKNOWN`, because there is
   no line file for this corridor and nothing else supplies one.

4. **Blocked records vanish.** Five of the eleven Sphoorthi records block on
   `RATIO-PS`. On the command line the operator sees that. In a naive upload
   they would silently not appear in the answer, which §2.5 forbids.

5. **The files do not arrive as bare `.cfg`.** They arrive as `.cfg`+`.dat`
   pairs, inside nine `.zip` archives, in folders whose names are unreliable.

None of this is a maths problem. It is that the tool's unit of work is a
*file path* when the domain's unit of work is an *incident*.

## 2. Scope

**In scope**

- A `Bundle`: a set of uploaded files plus a manifest recording, per file,
  the operator's **declared** line / terminal / relay, the content hash, and
  the conformance outcome.
- Accepting `.cfg`+`.dat` pairs, `.cff`, `.rio` settings exports, and `.zip`
  archives containing any of those.
- A local HTTP workbench on `127.0.0.1`: upload, assign, one incident page.
- A per-record parsing-and-conformance panel for **every** file in the
  bundle, including the blocked ones.
- Reusing the existing two-page report unchanged as the incident page's
  analysis section.

**NOT in scope — explicitly**

- **No change to `comtrade/`, `dsp/`, `faultloc/` or `synth/`.** Not one
  line. No number this tool reports may move because of this work.
- No FastAPI, no React, no Node, no Docker, no Postgres, no MinIO, no Celery.
  See §4.
- No authentication, no multi-user, no concurrent sessions, no LAN exposure
  (see the open question in §9).
- No `AssetResolver`. The operator declares the assignment; nothing infers
  it. The manifest this plan writes is designed to be what the resolver later
  pre-fills — see P4 — but the resolver is not built here.
- No pairing across bundles. One bundle is one incident, declared as such.
- No PDF export. The report is already self-contained HTML.

## 3. Constraint check — `PROJECT_CONTEXT.md` §2

| Constraint | How this stays inside it |
|---|---|
| **§2.4 DO NOT emit one report per file** | This is the constraint that shapes the whole feature. Upload takes a *set*; the page produced is *one incident*. There is deliberately **no** "analyse this file" route that emits a report — a single file uploaded is an incident of one record, and it is labelled as such. The per-record panels are evidence inside the incident, not reports. |
| **§2.5 DO NOT silently repair bad input** | Every uploaded file appears in the bundle with its conformance verdict, including duplicates (by content hash) and blocked records. A blocked record is shown with its BLOCK flags and excluded from the estimators with the exclusion stated on the page. Nothing is dropped without a visible record of the drop. |
| **§2.3 DO NOT make time sync a dependency** | Grouping is declared by the operator, never inferred from trigger timestamps. This is not theoretical: event 15665's four relays are spread 13 min 24 s apart. |
| **§2.6 learned corrections** | Not touched. |
| **CLAUDE.md: nothing infers a terminal from argument order** | The operator's assignment in the form is an **explicit declaration**, recorded in the manifest with `source: operator` and carried onto the page. In §6's evidence hierarchy that is rank 1, the sidecar manifest — the highest authority, above the CFG header. It is not inference, and it is not argument order. |

**§17 [OPEN] assumed defaults:** item 7 (internal tool vs product) — assumed
**internal**, which is why single-user with no authentication is acceptable.
Item 8 ("what is in `E:\dr analyser`") is now answered by the working tree.

## 4. Standards basis, and one deliberate deviation from §12

- COMTRADE handling is unchanged and remains IEEE C37.111-2013 / IEC 60255-24
  as already implemented. This plan adds no parsing.
- Incident-not-record is **§2.4 and §5.3 of the project spec**, not a
  standard. Labelled as project policy.
- File naming inside the bundle follows C37.232-2011 where a name is
  generated; where the operator's original filename is kept it is kept
  verbatim, as evidence.

**Deviation from §12 (technology stack), stated in the open.** §12 names
*FastAPI + React* for the API and web view and *Docker Compose* for
deployment. This plan uses the Python standard library's HTTP server and
server-rendered HTML, with **no new runtime dependency**, for three reasons:

1. §12's stack is specified for the multi-site service, which also assumes
   PostgreSQL, MinIO, Celery and a transport broker. None of those exist and
   none are in scope. Adopting the web half alone buys a build chain and no
   capability.
2. §12 requires the deployment to be **air-gap capable**. A stdlib server on
   a substation PC is; an `npm install` is not.
3. `groundtruth/web.py` already proves the pattern in this repo — it serves
   the confirmation form today with no framework.

The analysis code stays free of any web framework, so a FastAPI + React
service can later sit on exactly the same `Bundle` and report objects. If
you want FastAPI + React now instead, say so and I will re-plan; it is a
different and larger piece of work.

## 5. Phases

### P1 — Bundle and manifest (no web)

New `src/dranalyser/workbench/bundle.py`. A `Bundle` takes a directory or a
zip, walks it, pairs `.cfg` with `.dat`, picks up `.cff` and `.rio`,
de-duplicates by content hash, runs `check()` on each record, and writes a
manifest whose shape is §6's sidecar `_asset.yaml`.

CLI: `dranalyse bundle <path> [--out manifest.yaml]`.

*Done when:* pointing it at `drs sphoorthi/garividi-maradam-1` plus
`drs sphoorthi/maradam-garividi-1` yields one manifest listing four records
with their hashes, stations, sample rates and conformance verdicts; the two
`ps=S` blocked records appear flagged, not missing; and a zip and its
extracted folder produce identical manifests.

### P2 — The workbench server

New `src/dranalyser/workbench/server.py` and `pages.py`. Stdlib
`ThreadingHTTPServer`, four routes: upload form, bundle view with the
assignment form, incident page, and a static-ish asset route for the
generated report.

CLI: `dranalyse workbench --port 8090` (binds `127.0.0.1` by default).

Upload accepts multiple files at once and zips. The bundle view lists every
file with its parse result and conformance flags, and offers per-record
dropdowns for terminal (S / R / unassigned) and a free-text line id. Submit
writes the manifest and renders the incident page, which embeds the existing
two-page report for the two records the operator marked primary.

*Done when:* the four files of event 15665 can be dropped in through the
browser, assigned, and produce one incident page; and a bundle where two
records are assigned the same terminal is **refused with the reason**, not
silently resolved.

### P3 — More than one record per terminal

`incident_features` and `report/build` currently key on `{"S": …, "R": …}`.
Extend to `{"S": [primary, …], "R": [primary, …]}`: the primary record drives
the estimators, the others corroborate. Disagreement between two relays at
one terminal becomes a finding.

This has a real case waiting for it: on event 15665 the D60 and the P444 sit
on the same bus and disagree on the measured negative-sequence source
impedance (155.97 Ω at 9.7° against 21.68 Ω at 84.6°) while measuring the
same 305–310 A of I2. Today nothing surfaces that.

*Done when:* the 15665 incident page shows all four records, names which one
drove each terminal's estimate and why, and raises the D60/P444 disagreement
as a finding rather than hiding it behind a choice of `--R`.

### P4 — Manifest as the AssetResolver's contract (not built here)

When §6's `AssetResolver` lands it pre-fills the assignment form from
evidence and the operator confirms or overrides, with both the inferred and
the declared value kept. Listed so P1's manifest schema is designed for it,
not retrofitted.

## 6. Test plan

- P1: new `tests/test_workbench.py` — manifest from a synthetic bundle
  (generated by `synth/`, so it runs on a clone with no corpus); zip and
  folder equivalence; hash de-duplication; a blocked record stays listed.
  Corpus-marked tests over `drs sphoorthi/` skip cleanly when absent.
- P2: route tests against the handler with a fake socket, as
  `test_groundtruth.py` already does for the capture form. Including the
  refusal path for a double-assigned terminal.
- P3: a synthetic incident with two records per terminal and a known `m`;
  the located `m` must be unchanged from the single-record case to within
  floating point, since the primary record is the same.
- **Unchanged gates every phase:** `python scripts/check_architecture.py`
  exit 0, `pytest -q` all green, and `dranalyse stage-a --cases 10000
  --workers 1` still **PASS** at p95 < 0.5 % (currently 0.4403 %). P1 and P2
  touch no analytical code, so any movement in that number is a bug in the
  phase.

Architecture guard needs a new entry:
`"workbench": {"signals", "comtrade", "dsp", "faultloc", "registry", "rules",
"report", "groundtruth"}`, and `workbench` added to `cli`'s allowed set.
Nothing analytical may import `workbench`.

## 7. Data / registry impact

- **New file format:** the bundle manifest. Deliberately the same shape as
  §6's `_asset.yaml` sidecar, so the future edge collector emits something
  the workbench can already read.
- **No change** to the line YAML schema, to `registry/model.py`, or to the
  `groundtruth` SQLite schema.
- **No recomputation** of past results. Nothing stored changes meaning.
- One new writable directory for uploaded bundles (default
  `out/bundles/<bundle-id>/`), already covered by the `out/` gitignore rule.

## 8. Expected step change

**No analytical number moves.** Fault location, DSP, conformance and the
rules engine are untouched.

What visibly changes: an incident can be assembled in a browser instead of a
command line; an incident's line id becomes the operator's declared value
instead of `UNKNOWN`; and after P3 an incident page shows four records where
it showed two. If a located distance changes at any point in this work,
that is a defect, not an improvement.

## 9. Risks and open questions

1. **Bind address.** Default is `127.0.0.1`, this machine only. Making it
   reachable from the substation LAN means an unauthenticated tool serving
   real protection data on a shared network. I would not do it without
   authentication. **Do you need LAN access?**
2. **Do bundles persist?** Default assumed: yes, written under `out/bundles/`
   so an incident can be reopened, and never committed. The alternative is
   ephemeral per session.
3. **P3 primary-record selection.** When two relays at one terminal both pass
   the gate, which drives the estimate? Assumed default: the one with the
   better conformance and window quality, with the choice stated on the page
   — never silently.
4. **Browser file-picker and `.cfg`+`.dat` pairs.** The operator must select
   both halves. The upload page will say so and refuse a `.cfg` whose `.dat`
   is missing rather than half-parsing it. Uploading the zip avoids the
   problem entirely and will be the recommended path.
5. This plan does not fix the two things actually blocking a fault location
   on the Sphoorthi corridor — the line constants and the Maradam CT polarity
   (`NEXT_SESSION.md` §7 items 6 and 7). The workbench will show the analysis
   and refuse the distance, correctly.
