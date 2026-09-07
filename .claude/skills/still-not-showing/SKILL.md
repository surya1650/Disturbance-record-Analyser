---
name: still-not-showing
description: Diagnose "I changed it but it still gives the old answer / same error" — check the delivery layer (venv, editable install, stale __pycache__, shadowed module, wrong file, cached fixture) BEFORE touching more code, and prove the new code is what actually ran. Use whenever the user says "still not showing", "no change", or "same error again".
---

# Still Not Showing — it is the delivery layer until proven otherwise

When the user says *"still not showing"* or *"same error"*, the overwhelmingly likely
cause is that the change never reached the process that ran. **Do not edit more code
first.** Editing on top of an undelivered fix has produced multi-hour dead ends before.

## Diagnostic order — stop at the first failure

**1. Did the file actually change on disk?**
`git diff --stat` (once the repo is initialised) or check the timestamp. Another agent
works in this repo — a Qodo agent scaffolded `src/` and has been writing tests. The
working tree is not necessarily yours; your edit may have been overwritten.

**2. Which Python, which environment?**
```powershell
python -c "import sys; print(sys.executable)"
python -c "import dranalyser, inspect; print(dranalyser.__file__)"
```
If `dranalyser.__file__` points anywhere other than `E:\dr analyser\src\dranalyser`, that
is the bug. A stale `pip install .` (non-editable) puts a **copy** in `site-packages`
that shadows the source tree — reinstall with `pip install -e .`.

**3. Is there a shadowing name?**
A stray `comtrade.py`, `signals.py`, or `dranalyser/` in the current directory, or an old
`*.egg-info` / `build/` tree, will win over the real module. `python -X importtime -c
"import dranalyser"` shows what actually loaded.

**4. Stale bytecode / caches.**
```powershell
Get-ChildItem -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force
Remove-Item -Recurse -Force .pytest_cache
```
Also `.ruff_cache` if ruff reports a violation on a line you already deleted.

**5. Prove the new code is what ran.** This is the step that ends the argument:
```powershell
python -c "import inspect, dranalyser.faultloc.estimators as e; print(inspect.getsource(e.e5_unsynchronised))"
```
Look for your new symbol in that output — not in the file you edited.

**6. Is it the same input?** A "same wrong answer" often means the same cached input:
a fixture recorded earlier, a parsed record pickled into a test artifact, the wrong
`--line` YAML, or the wrong record pair. Print the input hash / file path the run used,
not the one you intended.

**7. Only now suspect the code.**

## Test-specific traps

- `pytest` collected nothing new? Check `testpaths`/naming (`test_*.py`, `Test*` class,
  `test_*` function) and that no `__init__.py` collision exists between test dirs.
- A test that "passes" may have been **skipped** — corpus tests skip when
  `tests/corpus/` is empty. Read the skip count; a green run with skips proves nothing.
- `-p no:cacheprovider` if you suspect a cached last-failed set is steering the run.

## Done means seen

A maths fix is not fixed until the CLI (or the test with a known `m`) **prints the new
number** on real input. A green build is not done. Report the observation — the actual
output line — not the fact that the build passed.
