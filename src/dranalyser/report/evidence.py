"""Escaped, self-contained all-relay evidence annex for incident exports."""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from ..rules.evidence import terminal_evidence
from ..rules.operation_compare import compare_operations


def render_evidence(records, comparisons, operations=None, audits=None, sources=None, stage_locations=None):
    env = Environment(autoescape=True, loader=FileSystemLoader(Path(__file__).parent))
    env.filters["number"] = lambda x: "unavailable" if x is None else format(x, ".3f")
    template = Path(__file__).with_name("evidence.html").read_text(encoding="utf-8")
    template += Path(__file__).with_name('audits.html').read_text(encoding='utf-8')
    return env.from_string(template).render(records=records, comparisons=comparisons,
                                            stage_locations=stage_locations or [],
                                            audits=audits or [], sources=sources or [],
                                            operations=operations if operations is not None else compare_operations(records),
                                            terminals=terminal_evidence(records))
