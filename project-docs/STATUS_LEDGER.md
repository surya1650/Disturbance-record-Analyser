# STATUS LEDGER — DR Analyser

Newest entry at the top. One entry per milestone (plan approved, phase merged, audit,
big fix). State plainly what was done, what was run, and what is outstanding. "Built",
"merged" and "verified on real records" are three different states — use the true one.

---

## 2026-09-07 - First PR built, tested and pushed

**State:** committed and pushed to https://github.com/surya1650/Disturbance-record-Analyser
(branch `main`, commit `a4897d1`). 141 tests pass. `scripts/check_architecture.py` passes.
**Not yet verified against a real two-ended pair** - none exists in the corpus.

Built (`src/dranalyser/`): own COMTRADE parser (1991/1999/2013, ASCII/BINARY/BINARY32/
FLOAT32, .CFF, nrates 0/1/n, P/S scaling); conformance gate (13 checks); DSP chain
(frequency tracking, mimic filter, sliding full/half-cycle DFT, sequence, superimposed,
inception, fault-type classification, CT saturation, ADC clipping, window selection);
estimators E1-E5 and the E6 ensemble; synthetic two-source phase-domain fault generator
(the oracle); registry with vendor k0 conversions; CLI (`locate`/`inspect`/`selftest`/
`template`); ML tiers 1/2/3.

Verified: Stage-A (§13) PASS - mean 0.030 %, p95 0.092 %, max 0.152 % of line length,
through the full DSP chain with 1418 s clock skew, CVT transient, decaying DC, ADC
quantisation, 1000 Hz vs 1200 Hz. Parser verified on all four real DHONE records.

**Field finding from the real records - needs action, not code.** Main-1 measures 575 V
of V0 during an A-G fault carrying 1670 A of I0; Main-2, same bay, same fault, measures
34 kV. Main-1's VT secondary cannot pass zero sequence, so its ground-loop voltage is
missing V0 and it reports the fault ~13 % of the line too far out - consistent with
Main-1 tripping in Zone 2 while Main-2 tripped in Zone 1. The analyser now detects this
(`VT-NO-ZERO`) and refuses the single-ended ground-loop calculation at that terminal
rather than answering wrongly. **Check the Main-1 VT connection at DHONE.**

Also confirmed on real records: relay clocks in one bay differ by 1418 s; pre-fault load
sits in 11 (Main-1) and 7 (Main-2) ADC counts; no clock-quality code anywhere, so E4 is
permanently gated off in this fleet; Main-1 has no carrier-send digital channel mapped,
so rule CR-01 cannot be evaluated from it.

Outstanding, in priority order:
1. Recover a genuine two-ended pair (Nandyal end). Everything in §7.2, §13 Stage B and
   the §14 proof depends on it. Organisational lead time, start now.
2. Real Z1/Z0/length/tower schedule for DHN-NNR - `data/registry/dhn-nnr.yaml` is
   PROVISIONAL and marked so.
3. Not built: pairing, transport, edge collector, rules engine, two-page PDF report.
4. Not handled: distributed-parameter model for long lines, three-terminal lines.
   Series-compensated lines are detected and refused, not approximated.

Real records, the .rio settings export and event PDFs are NOT committed - the repo is
public. Tests needing them skip cleanly.

---

## 2026-09-06 — Toolchain, guard rails and agent context installed

**State:** repo is NOT a git repository yet; everything below is uncommitted on disk.

Added (this session, by Claude):
- `CLAUDE.md` — project instructions: binding §2 constraints, layout, hard rules,
  definition of done, conventions, and how R. Surya works.
- `.claude/skills/` — 10 skills (+ `README.md` index): `spec-constraints`,
  `fault-location-math`, `comtrade-corpus`, `record-investigation`, `release-check`,
  `same-defect-sweep`, `still-not-showing`, `plan-first`, `plan-review`,
  `session-handoff`.
- `pyproject.toml` (setuptools src-layout, `dranalyse` entry point, ruff py311/120/E4-E7-E9-F-B,
  pytest with `pythonpath=["src"]`, `corpus`/`slow` markers, RuntimeWarning-as-error),
  `requirements.txt`, `requirements-dev.txt`, `.gitignore` (records excluded except
  `tests/corpus/`).
- `scripts/check_architecture.py` + `scripts/architecture_budgets.json` — purity of the
  maths core, no third-party COMTRADE parser, no ML in the fault-location path, no
  traveling-wave module, import-direction layering, estimators must return `Estimate`,
  file-growth ratchet seeded at exact current line counts (23 files).
- `project-docs/STATUS_LEDGER.md`, `project-docs/LESSONS.md`.

Not touched: `src/`, `tests/`, `data/`, `PROJECT_CONTEXT.md`, `HANDOFF_PROMPT.md`, and the
legacy prototypes (`dr/`, `DR1/`, `DR 9-4-2026`, `DR & Events 9-4-2026`) — another agent
(Qodo) is actively writing `src/` and `tests/`.

**Gates as of this session:**

| Gate | Result |
|---|---|
| `python scripts\check_architecture.py --self-test` | pass |
| `python scripts\check_architecture.py` | pass (after allowing `comtrade -> dsp` and `ml -> dsp/synth`, which the existing code legitimately uses) |
| `python -m ruff check .` | **18 errors** in `src/` and `tests/` (pre-existing, deliberately not fixed — mostly unused imports). `scripts/` is clean. |
| `python -m pytest -q` | **141 passed** at 21:5x. Earlier in the same session two `tests/test_real_records.py` tests failed (the two relays located the same fault 13.07 % of line / 8.102 km apart, and their inception instants disagreed); the other agent fixed them mid-session. |

Budgets were reseeded twice while the other agent's files grew under the gate — the
ratchet works, but with zero headroom it will keep firing while `src/` is under active
construction. During the §14 first-PR build, `--reseed` after intentional growth is the
right move; the ratchet becomes a real constraint once §14 lands.

**Outstanding:**
1. `git init` and a first commit — nothing is under version control yet.
2. The two real-record failures above (owned by the other agent's current work; they are a
   sample-rate / P-S-convention / inception-detection question, see `record-investigation`).
3. 19 ruff errors to clear once the other agent's edits settle.
4. `tests/corpus/` is empty — every corpus-marked test skips, so no claim about real
   vendor files is currently supported.
5. §17 [OPEN] items 1–7 in `PROJECT_CONTEXT.md` are still unanswered; item 8 ("what is in
   E:\dr analyser") is now answered by the working tree itself.
