---
name: release-check
description: Run the full verification gates for the DR analyser (architecture guard + self-test, ruff, pytest incl. corpus and synthetic sweeps) and report a pass/fail table. Use before any merge, before packaging, or when the user says "run the gates", "is this ready", or "verify everything".
---

# Release Check — the gates, in this order

All commands from the repo root (`E:\dr analyser`), PowerShell. Run them **in this
order**: the architecture gate is the cheapest and fails fastest.

```powershell
# 1. Architecture guard (checks itself first, then the tree)
python scripts\check_architecture.py --self-test
python scripts\check_architecture.py

# 2. Lint
python -m ruff check .

# 3. Tests
python -m pytest -q
```

Optional, when the change touches them:

```powershell
python -m pytest -q -m corpus          # real vendor COMTRADE files
python -m pytest -q -m slow            # Stage-A synthetic sweeps (10k+ cases)
python -m pytest -q --cov=dranalyser --cov-report=term-missing
dranalyse selftest                     # CLI's own end-to-end check
```

## Reading each gate honestly

**Architecture guard.** Enforces the §2 decisions and the layering: maths purity in
`faultloc/`+`dsp/`, no third-party COMTRADE parser, no ML import in the fault-location
path, no traveling-wave module, allowed import directions, every estimator returning
`Estimate`, and the file-growth ratchet.

The ratchet in `scripts/architecture_budgets.json` is seeded at the **exact current line
counts** — zero headroom, so one added line fails. That is deliberate: growth is a
decision, not a drift. Bump the budget in the **same commit** as the growth
(`python scripts\check_architecture.py --reseed` rewrites every budget to current counts —
use it only when the growth is intended, and read the diff before committing it). The
`exceptions` block is for temporary growth with an expiry date, and an **expired exception
is itself an error**.

**ruff.** Config in `pyproject.toml`: py311, line length 120, rules E4/E7/E9/F/B — the
same set as the AHI portal. Zero errors is the gate. The legacy folders (`dr/`, `DR1/`,
`DR 9-4-2026`, `DR & Events 9-4-2026`) are excluded on purpose: they are earlier
prototypes, not this project.

**pytest.** `pythonpath = ["src"]` is set, so tests import `dranalyser` without an
install; `pip install -e .` is still what puts the `dranalyse` command on PATH.
- Run the **whole** suite and expect zero failures. Do not chase a remembered count.
- **A skip is a result, not noise.** `-m corpus` tests skip silently when
  `tests/corpus/` is empty — a green run with corpus skips proves nothing about vendor
  files. State the skip count and what it means.
- `filterwarnings = ["error::RuntimeWarning"]` is on purpose: an overflow or a
  divide-by-zero in the maths is a failure, not a warning to scroll past.

## Then the part a green build cannot give you

**Done means exercised.** Run the CLI against a real archived record pair, or a synthetic
case with a known `m`, and paste the per-method table:

```powershell
dranalyse locate --line data\registry\<line>.yaml --S <recordS.cfg> --R <recordR.cfg>
```

Check the output actually carries: every method's `m`, its residual, its flags, the
reconciled estimate, the conformance tags, and the tower number. A number without its
method is not an acceptable output.

## Report shape

A table: gate · command · result · notes. Then, explicitly:
- what changed and **what was deliberately left untouched**;
- any gate **not** run, named as not run (never a remembered pass);
- the expected step change in any number this touches, so it is not mistaken for a
  regression.
