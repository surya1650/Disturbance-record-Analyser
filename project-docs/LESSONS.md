# LESSONS — DR Analyser

One-off gotchas that do not fit a standing rule. Newest at the top, dated.
Symptom → cause → the check that catches it next time.
If a lesson generalises into a rule, move it to `CLAUDE.md` or a skill.

---

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
