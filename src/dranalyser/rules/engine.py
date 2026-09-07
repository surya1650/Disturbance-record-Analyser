"""The conclusions engine: rules are data, not code.

Each rule is a YAML entry with a condition over the feature set, a severity,
an evidence pointer and a recommended action, so the protection group can add
rules without a software release.

Three design choices worth stating:

  * Conditions are evaluated by a whitelisted AST walker, not by eval(). A
    rule file is configuration that a protection engineer edits; it must not
    be able to execute arbitrary code.

  * An unknown name in a condition is an ERROR, not False. A typo in a rule
    that quietly never fires is indistinguishable from a healthy network.

  * Every rule may declare `requires`. If a required feature is missing --
    typically because the relay has no such channel wired to the recorder --
    the rule is reported NOT EVALUABLE with the reason, and never as a pass.
    This is the difference between "the carrier did not arrive" and "this
    relay cannot tell you whether the carrier arrived", and on the source
    corpus that distinction is real: Main-1 records a carrier receive but no
    carrier send, so CR-01 cannot be judged from it.
"""
from __future__ import annotations

import ast
import math
import os
import string
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import yaml

SEVERITIES = ("info", "investigate", "critical")
VERDICTS = ("Correct operation", "Correct but investigate", "Incorrect operation")

CATALOGUE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "catalogue.yaml")


class RuleError(Exception):
    pass


# --------------------------------------------------------------------------
# safe expression evaluation
# --------------------------------------------------------------------------
_ALLOWED_NODES = (
    ast.Expression, ast.BoolOp, ast.UnaryOp, ast.BinOp, ast.Compare, ast.Name,
    ast.Load, ast.Constant, ast.Call, ast.IfExp, ast.List, ast.Tuple,
    ast.And, ast.Or, ast.Not, ast.USub, ast.UAdd,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn,
    ast.Is, ast.IsNot,
)


def _fn_defined(x: Any) -> bool:
    return x is not None


_FUNCS = {
    "abs": abs, "min": min, "max": max, "len": len, "round": round,
    "any": any, "all": all, "defined": _fn_defined, "float": float, "int": int,
    "isnan": lambda x: x is None or (isinstance(x, float) and math.isnan(x)),
}


class _Eval(ast.NodeVisitor):
    """Whitelisted evaluator with None-tolerant comparisons.

    A comparison where either side is None yields False rather than raising.
    Protection features are legitimately absent -- no breaker aux contact, no
    reclose, a record that stops before the fault clears -- and a rule author
    should not have to guard every term.
    """

    def __init__(self, names: Dict[str, Any]):
        self.names = names
        self.used: List[str] = []

    def visit(self, node):
        if not isinstance(node, _ALLOWED_NODES):
            raise RuleError("expression uses " + type(node).__name__
                            + ", which is not allowed in a rule condition")
        return super().visit(node)

    def visit_Expression(self, node):
        return self.visit(node.body)

    def visit_Constant(self, node):
        return node.value

    def visit_Name(self, node):
        if node.id in _FUNCS:
            return _FUNCS[node.id]
        if node.id == "None":
            return None
        if node.id not in self.names:
            raise RuleError("unknown feature " + repr(node.id)
                            + " in rule condition; a typo here would make the "
                              "rule silently never fire")
        self.used.append(node.id)
        return self.names[node.id]

    def visit_BoolOp(self, node):
        vals = [self.visit(v) for v in node.values]
        if isinstance(node.op, ast.And):
            return all(bool(v) for v in vals)
        return any(bool(v) for v in vals)

    def visit_UnaryOp(self, node):
        v = self.visit(node.operand)
        if isinstance(node.op, ast.Not):
            return not bool(v)
        if v is None:
            return None
        return -v if isinstance(node.op, ast.USub) else +v

    def visit_BinOp(self, node):
        a, b = self.visit(node.left), self.visit(node.right)
        if a is None or b is None:
            return None
        op = node.op
        if isinstance(op, ast.Add):
            return a + b
        if isinstance(op, ast.Sub):
            return a - b
        if isinstance(op, ast.Mult):
            return a * b
        if isinstance(op, ast.Div):
            return a / b if b else None
        if isinstance(op, ast.Mod):
            return a % b if b else None
        if isinstance(op, ast.Pow):
            return a ** b
        raise RuleError("unsupported operator")

    def visit_Compare(self, node):
        left = self.visit(node.left)
        for op, comp in zip(node.ops, node.comparators):
            right = self.visit(comp)
            if isinstance(op, ast.Is):
                ok = left is right
            elif isinstance(op, ast.IsNot):
                ok = left is not right
            elif isinstance(op, (ast.In, ast.NotIn)):
                if right is None:
                    ok = False
                else:
                    ok = (left in right) if isinstance(op, ast.In) else (left not in right)
            elif left is None or right is None:
                ok = False
            elif isinstance(op, ast.Eq):
                ok = left == right
            elif isinstance(op, ast.NotEq):
                ok = left != right
            elif isinstance(op, ast.Lt):
                ok = left < right
            elif isinstance(op, ast.LtE):
                ok = left <= right
            elif isinstance(op, ast.Gt):
                ok = left > right
            else:
                ok = left >= right
            if not ok:
                return False
            left = right
        return True

    def visit_Call(self, node):
        fn = self.visit(node.func)
        if fn not in _FUNCS.values():
            raise RuleError("only " + ", ".join(sorted(_FUNCS)) + " may be called")
        return fn(*[self.visit(a) for a in node.args])

    def visit_IfExp(self, node):
        return self.visit(node.body) if bool(self.visit(node.test)) else self.visit(node.orelse)

    def visit_List(self, node):
        return [self.visit(e) for e in node.elts]

    def visit_Tuple(self, node):
        return tuple(self.visit(e) for e in node.elts)


def evaluate(expression: str, features: Dict[str, Any]) -> bool:
    tree = ast.parse(expression, mode="eval")
    return bool(_Eval(features).visit(tree))


# --------------------------------------------------------------------------
# rules
# --------------------------------------------------------------------------
@dataclass
class Rule:
    id: str
    title: str
    severity: str
    when: str
    message: str = ""
    action: str = ""
    requires: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    needs_location: bool = False
    enabled: bool = True

    def __post_init__(self):
        if self.severity not in SEVERITIES:
            raise RuleError("rule " + self.id + " has severity " + repr(self.severity)
                            + "; expected one of " + ", ".join(SEVERITIES))


@dataclass
class Finding:
    rule_id: str
    title: str
    severity: str
    message: str
    action: str
    evidence: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return "[" + self.severity.upper() + " " + self.rule_id + "] " + self.message


@dataclass
class NotEvaluable:
    rule_id: str
    title: str
    reason: str

    def __str__(self) -> str:
        return "[SKIPPED " + self.rule_id + "] " + self.reason


@dataclass
class RuleResult:
    findings: List[Finding] = field(default_factory=list)
    skipped: List[NotEvaluable] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def verdict(self) -> str:
        if any(f.severity == "critical" for f in self.findings):
            return VERDICTS[2]
        if any(f.severity == "investigate" for f in self.findings):
            return VERDICTS[1]
        return VERDICTS[0]

    def top(self, n: int = 3) -> List[Finding]:
        order = {"critical": 0, "investigate": 1, "info": 2}
        return sorted(self.findings, key=lambda f: order[f.severity])[:n]

    def report(self) -> str:
        rows = ["VERDICT: " + self.verdict]
        for f in self.top(99):
            rows.append("  " + str(f))
            if f.action:
                rows.append("      action: " + f.action)
        if self.skipped:
            rows.append("  not evaluable:")
            for s in self.skipped:
                rows.append("      " + str(s))
        for e in self.errors:
            rows.append("  RULE ERROR: " + e)
        return "\n".join(rows)


class _SafeFormatter(string.Formatter):
    """Renders a message even when some of its values are unavailable.

    A message written as "{S_breaker_ms:.0f} ms at S and {R_breaker_ms:.0f} at R"
    is perfectly reasonable, and it must still read correctly on a
    single-ended incident where the R value does not exist. Formatting the
    whole template as one unit fails and would print raw braces at the reader.
    """

    def get_value(self, key, args, kwargs):
        if isinstance(key, str):
            return kwargs.get(key, None)
        return super().get_value(key, args, kwargs)

    def format_field(self, value, format_spec):
        if value is None:
            return "n/a"
        try:
            return format(value, format_spec)
        except (TypeError, ValueError):
            return str(value)


_FORMATTER = _SafeFormatter()


def _render(template: str, features: Dict[str, Any]) -> str:
    try:
        return _FORMATTER.vformat(template, (), dict(features))
    except (ValueError, TypeError, KeyError, IndexError):
        return template


def load_rules(path: str = CATALOGUE) -> List[Rule]:
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or []
    if isinstance(raw, dict):
        raw = raw.get("rules", [])
    out = []
    seen = set()
    for entry in raw:
        r = Rule(**entry)
        if r.id in seen:
            raise RuleError("duplicate rule id " + r.id)
        seen.add(r.id)
        out.append(r)
    return out


def apply_rules(features: Dict[str, Any], rules: Optional[Sequence[Rule]] = None,
                path: str = CATALOGUE) -> RuleResult:
    rules = list(rules) if rules is not None else load_rules(path)
    res = RuleResult()
    for r in rules:
        if not r.enabled:
            continue
        missing = [k for k in r.requires
                   if k not in features or features.get(k) in (None, False)]
        if missing:
            res.skipped.append(NotEvaluable(
                r.id, r.title,
                r.title + " could not be judged: " + ", ".join(missing)
                + " unavailable. This is a recording or configuration gap, "
                  "not a healthy result."))
            continue
        if r.needs_location and not features.get("location_available"):
            res.skipped.append(NotEvaluable(
                r.id, r.title, r.title + " needs a fault location and none was produced"))
            continue
        try:
            hit = evaluate(r.when, features)
        except RuleError as exc:
            res.errors.append(r.id + ": " + str(exc))
            continue
        except Exception as exc:                       # noqa: BLE001
            res.errors.append(r.id + ": " + type(exc).__name__ + ": " + str(exc))
            continue
        if hit:
            res.findings.append(Finding(
                rule_id=r.id, title=r.title, severity=r.severity,
                message=_render(r.message or r.title, features),
                action=_render(r.action, features),
                evidence={k: features.get(k) for k in r.evidence},
            ))
    return res
