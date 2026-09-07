# LESSONS — DR Analyser

One-off gotchas that do not fit a standing rule. Newest at the top, dated.
Symptom → cause → the check that catches it next time.
If a lesson generalises into a rule, move it to `CLAUDE.md` or a skill.

---

### 2026-09-07 — `BrokenProcessPool` and two ML test failures were one OpenBLAS problem

**Symptom:** `dranalyse stage-a` died with `BrokenProcessPool` at the default worker
count but worked at `--workers 1`, `2` and `4`; separately,
`tests/test_ml.py::test_tier3_*` failed with `OpenBLAS error: Memory allocation still
failed after 10 retries`. They looked like two unrelated environment quirks and the
first was written off as "machine-level, use `--workers 1`".
**Cause:** one thing. Every worker process spawns one OpenBLAS thread per core, and on
a 14-core machine the total allocation exhausts memory. The Stage-A pool and the
sklearn import hit the same wall from different directions.
**Resolution:** `OPENBLAS_NUM_THREADS=1` (with `OMP_NUM_THREADS=1`). Everything then
runs multi-worker, and 10,000 Stage-A cases take 30 s instead of 111 s.
**The check that catches it next time:** when a parallel gate fails but its
single-worker form passes, suspect thread-per-core libraries before suspecting the
code — and confirm by `git stash`-ing `src/` and re-running. It reproduced on a clean
tree, which is what proved it was not the change under test.

### 2026-09-07 — A CFG station name is not the station

**Symptom:** on the Sphoorthi records, `garividi-maradam-2/Main-1 P444` carries the
station name `MARADAM 2`, and the ABB REL670 in the same bay carries
`BRAHMANAKOTKUR` — a substation in a different district entirely.
**Cause:** the field is populated by whoever configured the relay. Here it appears to
be a feeder name (the bay named for the remote end) in one case and a configuration
cloned from another station and never renamed in the other. Both records are
electrically at Garividi — they measure 15,684 A and ~15,300 A where the far-end
7SA522 measures 6871 A.
**The check that catches it next time:** fault-current magnitude. The end nearer the
fault feeds more current, and the two ends of one line carry the same pre-fault load.
This is why `AssetResolver` ranks the CFG header third, below a manifest and a path
rule, and never treats it as authority.

### 2026-09-07 — A relay model number looks like an identifier and is not

**Symptom:** while building `AssetResolver`, a test that should have resolved cleanly
came back `Ambiguous` because the resolver matched `7SA522` in a CFG header against a
relay entry at the *wrong* terminal.
**Cause:** relay `model` was in the list of names a record could be matched on. On a
fleet where half the relays are 7SA522 that is a confident end signal carrying no
information, and it fought with the correct substation match.
**The check that catches it next time:** when adding anything to a match list, ask
whether the value is unique to one asset. Model, vendor and firmware version are not.
Only the relay id and the aliases someone deliberately configured are.

### 2026-09-06 — The other agent overwrote `pyproject.toml` and `.gitignore` mid-session

**Symptom:** config files written 20 minutes earlier came back different — ruff config,
`package-dir`, and the `corpus` marker were gone from `pyproject.toml`; `.gitignore` was
replaced with a version that excludes the real `DR *` record folders and states *"this
repository is public"*.
**Cause:** two agents writing the same repo-level config files.
**Resolution:** their versions were kept and the missing tooling merged back in additively
(ruff config, `[tool.setuptools] package-dir`, the `corpus` marker, the secrets ignore
lines). **Note for R. Surya:** "this repository is public" is the other agent's assumption
— for utility relay settings, CT/VT ratios and fault records it is worth confirming
deliberately before `git init` and a first push.
**Check:** before editing a shared config file, re-read it; after editing, re-run the gates
rather than trusting the earlier green.

### 2026-09-06 — `pytest` could not import `dranalyser` at all

**Symptom:** every test file failed at collection with `ModuleNotFoundError: No module
named 'dranalyser'`, so the suite looked catastrophically broken when the code was fine.
**Cause:** src-layout with no packaging metadata — nothing put `src/` on the path.
**Fix / check:** `pythonpath = ["src"]` in `[tool.pytest.ini_options]`, plus
`pip install -e .` for the `dranalyse` command. If imports break again, check
`python -c "import dranalyser; print(dranalyser.__file__)"` before touching code.

### 2026-09-06 — A second agent is writing in this tree

**Symptom:** files appear and change between two reads minutes apart (`tests/` went from
empty to three test modules; `ml/tier2.py` and `ml/tier3.py` appeared).
**Cause:** a Qodo agent (`.qodo/`) is building `src/` concurrently.
**Check:** before reporting "the tests are failing" or "this file doesn't exist", re-read;
and when asked to "check the changes", diff honestly rather than assuming the tree is
yours.

### 2026-09-06 — The architecture guard's first run found real crossings, not bugs

**Symptom:** `comtrade/conformance.py` imports `dsp/`, `ml/tier1.py` and `ml/tier3.py`
import `dsp/` and `synth/` — flagged as illegal layering on the first run.
**Cause:** the initial allowed-import table was stricter than the design intends: the
conformance gate legitimately needs DSP primitives (prefault RMS, rotation), and the
learning layer legitimately reads analysed records and synthetic cases.
**Resolution:** the table now allows `comtrade -> dsp` and `ml -> dsp/synth`. The
direction that stays forbidden is the important one: **nothing in `faultloc/` or `dsp/`
may import `ml/`** (§2.1/§2.6).

### 2026-09-06 — Console output mangles em dashes

**Symptom:** gate output printed `... imports dsp/ ? not an allowed direction`.
**Cause:** Windows console codepage (cp1252) versus UTF-8 punctuation in the message.
**Check:** keep tool/gate output ASCII (`--`, `->`); prose in Markdown files is fine.
