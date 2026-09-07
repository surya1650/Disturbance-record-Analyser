"""Fast architecture boundary checks for the DR analyser. Run this FIRST — before ruff,
before pytest — because it is the cheapest gate and it encodes the decisions in
PROJECT_CONTEXT.md §2 that a well-meaning change would otherwise quietly undo.

    python scripts\\check_architecture.py --self-test
    python scripts\\check_architecture.py
    python scripts\\check_architecture.py --reseed     (deliberate budget bump)

What it enforces:

1. The maths is pure (§14 build rules). Nothing under faultloc/ or dsp/ may do I/O,
   print, log, read config, or touch the filesystem. An estimator takes phasors and line
   parameters and returns numbers — that is what makes it testable against synthetic
   cases with a known m.
2. No third-party COMTRADE parser (§12). We write our own; off-the-shelf parsers assume
   a conformance real vendor files do not have.
3. No ML anywhere in the fault-location path (§2.1). The learned layer may read the
   physics; the physics may never read the learned layer.
4. No traveling-wave module (§2.2) — ruled out on hardware grounds, not backlogged.
5. Layering direction: comtrade -> signals; dsp -> signals; faultloc -> dsp/registry;
   cli -> everything. No cycles, no upward imports.
6. Every estimator returns an Estimate (so a number always carries its method, residual
   and flags — never a bare float that a caller can mistake for an answer).
7. File-growth ratchet, seeded at the exact current line counts.
"""
from __future__ import annotations

import argparse
import ast
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "dranalyser"
BUDGETS = ROOT / "scripts" / "architecture_budgets.json"

# Modules that mean "this code touches the outside world". Allowed in cli.py, the parser,
# and the registry loader; forbidden in the maths core.
IO_MODULES = {
    "os", "io", "sys", "pathlib", "shutil", "glob", "tempfile", "socket", "subprocess",
    "logging", "json", "csv", "yaml", "sqlite3", "requests", "urllib", "sqlalchemy",
    "psycopg", "psycopg2", "pickle", "configparser", "argparse",
}
IO_CALLS = {"open", "print", "input"}

ML_MODULES = {"sklearn", "torch", "tensorflow", "keras", "xgboost", "lightgbm", "statsmodels", "pymc"}

FORBIDDEN_COMTRADE_LIBS = {"comtrade", "pycomtrade", "comtradehandlers"}

PURE_PACKAGES = ("faultloc", "dsp")

# package -> packages it is allowed to import from (within dranalyser)
ALLOWED_IMPORTS = {
    "comtrade": {"signals", "dsp"},
    "dsp": {"signals"},
    "faultloc": {"signals", "dsp", "registry"},
    "registry": set(),
    "synth": {"signals", "registry"},
    "ml": {"signals", "registry", "faultloc", "dsp", "synth"},
    # The conclusions engine sits above the analysis layers and below the CLI.
    # It reads their results; nothing in dsp/ or faultloc/ may read a rule.
    "rules": {"signals", "dsp", "faultloc", "registry"},
    # The back-test replays the whole pipeline over an archive; it sits at the
    # top of the analysis stack, below only the CLI.
    "backtest": {"signals", "comtrade", "dsp", "faultloc", "registry", "rules"},
    # The report renders what the analysis concluded. Nothing analytical may
    # import it, so a presentation change can never move a number.
    "report": {"signals", "dsp", "faultloc", "registry", "rules"},
    # Ground-truth capture depends on nothing in the package: it stores a
    # tower number against an incident id and must keep working when every
    # analytical layer around it changes.
    "groundtruth": set(),
    "cli": {"signals", "comtrade", "dsp", "faultloc", "registry", "synth", "ml",
            "rules", "backtest", "report",
            "groundtruth"},
    "signals": set(),
}


def _module_of(node: ast.AST) -> list[str]:
    """Top-level module names an import statement pulls in."""
    if isinstance(node, ast.Import):
        return [alias.name.split(".")[0] for alias in node.names]
    if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
        return [node.module.split(".")[0]]
    return []


def _relative_targets(tree: ast.AST) -> list[str]:
    """Package names reached by relative imports (`from ..dsp.core import x` -> 'dsp')."""
    targets = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level:
            if node.module:
                targets.append(node.module.split(".")[0])
            else:
                targets.extend(alias.name.split(".")[0] for alias in node.names)
    return targets


def _purity_errors(source: str, label: str) -> list[str]:
    tree = ast.parse(source)
    errors = []
    for node in ast.walk(tree):
        for mod in _module_of(node):
            if mod in IO_MODULES:
                errors.append(f"{label}: maths core imports I/O module '{mod}' (line {node.lineno})")
            if mod in ML_MODULES:
                errors.append(f"{label}: fault-location path imports ML module '{mod}' — PROJECT_CONTEXT.md §2.1")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in IO_CALLS:
            errors.append(f"{label}: maths core calls {node.func.id}() at line {node.lineno} — keep estimators pure")
    for target in _relative_targets(tree):
        if target == "ml":
            errors.append(f"{label}: fault-location path imports the learning layer — PROJECT_CONTEXT.md §2.1/§2.6")
    return errors


def _parser_errors(source: str, label: str) -> list[str]:
    tree = ast.parse(source)
    errors = []
    for node in ast.walk(tree):
        for mod in _module_of(node):
            if mod in FORBIDDEN_COMTRADE_LIBS:
                errors.append(f"{label}: third-party COMTRADE parser '{mod}' — PROJECT_CONTEXT.md §12 says write our own")
    return errors


def _layering_errors(source: str, package: str, label: str) -> list[str]:
    tree = ast.parse(source)
    allowed = ALLOWED_IMPORTS.get(package, set())
    errors = []
    for target in _relative_targets(tree):
        if target in ALLOWED_IMPORTS and target != package and target not in allowed:
            errors.append(f"{label}: {package}/ imports {target}/ -- not an allowed direction")
    return errors


def _estimator_errors(source: str, label: str) -> list[str]:
    """Public estimators must be annotated to return Estimate, so no bare float escapes."""
    tree = ast.parse(source)
    errors = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        if not node.name.startswith(("e1_", "e2_", "e3_", "e4_", "e5_", "e6_")):
            continue
        if node.name.endswith(("_terms", "_roots", "_delta", "_residual")):
            continue  # documented helpers of the E5 expansion, not answers
        returns = node.returns
        name = returns.id if isinstance(returns, ast.Name) else None
        if name != "Estimate":
            errors.append(f"{label}: estimator {node.name} does not return Estimate — a number must carry its method")
    return errors


def _traveling_wave_errors(paths: list[Path]) -> list[str]:
    hits = [p for p in paths if "travel" in p.name.lower()]
    return [f"traveling-wave module {p.relative_to(ROOT).as_posix()} — ruled out in PROJECT_CONTEXT.md §2.2" for p in hits]


def _source_files() -> list[Path]:
    return sorted(p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts)


def _budget_errors() -> list[str]:
    if not BUDGETS.exists():
        return ["scripts/architecture_budgets.json is missing — reseed it with --reseed"]
    config = json.loads(BUDGETS.read_text(encoding="utf-8"))
    errors = []
    today = date.today()
    for rel, baseline in config["files"].items():
        path = ROOT / rel
        if not path.exists():
            errors.append(f"budgeted file no longer exists: {rel} (update architecture_budgets.json in this commit)")
            continue
        count = len(path.read_text(encoding="utf-8").splitlines())
        allowed = baseline
        exception = config.get("exceptions", {}).get(rel)
        if exception:
            expires = date.fromisoformat(exception["expires"])
            if expires < today:
                errors.append(f"expired growth exception for {rel}: {exception['expires']}")
            else:
                allowed += int(exception["extra_lines"])
        if count > allowed:
            errors.append(f"file growth ratchet exceeded: {rel} has {count}, allowed {allowed}")
    return errors


def check() -> list[str]:
    errors: list[str] = []
    files = _source_files()
    errors.extend(_traveling_wave_errors(files))
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        source = path.read_text(encoding="utf-8")
        parts = path.relative_to(SRC).parts
        package = parts[0] if len(parts) > 1 else path.stem
        if package in PURE_PACKAGES:
            errors.extend(_purity_errors(source, rel))
        if package == "comtrade":
            errors.extend(_parser_errors(source, rel))
        errors.extend(_layering_errors(source, package, rel))
        if path.name == "estimators.py":
            errors.extend(_estimator_errors(source, rel))
    errors.extend(_budget_errors())
    return errors


def reseed() -> None:
    config = json.loads(BUDGETS.read_text(encoding="utf-8")) if BUDGETS.exists() else {"files": {}, "exceptions": {}}
    files = {}
    for path in _source_files() + sorted((ROOT / "scripts").glob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        files[rel] = len(path.read_text(encoding="utf-8").splitlines())
    config["files"] = dict(sorted(files.items()))
    config.setdefault("exceptions", {})
    BUDGETS.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(f"reseeded {len(files)} budgets at current line counts")


def self_test() -> None:
    assert _purity_errors("import os\n", "x")
    assert _purity_errors("def f():\n    print(1)\n", "x")
    assert _purity_errors("from ..ml.tier1 import fit\n", "x")
    assert not _purity_errors("import math\nimport numpy as np\nfrom .core import PhasorStream\n", "x")
    assert _parser_errors("import comtrade\n", "x")
    assert not _parser_errors("import numpy as np\n", "x")
    assert _layering_errors("from ..faultloc.ensemble import locate\n", "comtrade", "x")
    assert not _layering_errors("from ..signals import Record\n", "comtrade", "x")
    assert _estimator_errors("def e1_reactance(v, i, z):\n    return 0.5\n", "x")
    assert not _estimator_errors("def e1_reactance(v, i, z) -> Estimate:\n    return Estimate()\n", "x")
    assert not _estimator_errors("def e5_residual(m) -> float:\n    return 0.0\n", "x")
    assert _traveling_wave_errors([ROOT / "src/dranalyser/faultloc/traveling_wave.py"])
    assert date.fromisoformat("2026-01-02") < date.fromisoformat("2026-01-03")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true", help="check the guard itself")
    parser.add_argument("--reseed", action="store_true", help="rewrite line budgets to current counts (deliberate)")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        print("architecture guard self-tests passed")
        return 0
    if args.reseed:
        reseed()
        return 0
    errors = check()
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors))
        return 1
    print("architecture checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
