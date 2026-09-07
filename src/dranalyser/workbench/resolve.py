"""Pre-fill the assignment form from the AssetResolver.

P4 of the workbench plan. The operator no longer types the assignment from
nothing: the resolver proposes one from evidence, and the operator confirms or
overrides it. Both survive -- `suggested_*` is what the resolver said,
`terminal_end` with `assignment_source: operator` is what the operator
decided. When they differ, the manifest records that a human overruled the
machine, which is exactly the audit trail a wrong location needs.

A suggestion is never applied on its own. `assign()` still has to be called,
and it is still the operator's declaration that reaches the estimators.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Sequence

from ..registry.assets import (Ambiguous, AssetResolver, RecordFacts,
                               load_registry)
from ..registry.model import Line
from ..registry.settings_io import load_settings
from .bundle import Bundle, BundleFile


def _settings_context(bundle: Bundle) -> Dict[str, tuple]:
    """(substation, feeder) from any settings export, keyed by its directory.

    A .rio sitting beside a record describes that record's terminal. Keyed by
    folder so a bundle holding both ends does not cross-contaminate them.
    """
    out: Dict[str, tuple] = {}
    for sf in bundle.settings():
        if not sf.name.lower().endswith(".rio"):
            continue
        full = os.path.join(bundle.root, sf.name.replace("/", os.sep))
        try:
            s = load_settings(full)
        except Exception:                       # noqa: BLE001 - absence, not failure
            continue
        out[os.path.dirname(sf.name)] = (s.substation, s.feeder or s.line_hint)
    return out


def facts_for(bundle: Bundle, f: BundleFile,
              settings_ctx: Optional[Dict[str, tuple]] = None) -> RecordFacts:
    ctx = settings_ctx or {}
    sub, feeder = "", ""
    folder = os.path.dirname(f.name)
    while True:
        if folder in ctx:
            sub, feeder = ctx[folder]
            break
        if not folder:
            break
        folder = os.path.dirname(folder)
    return RecordFacts(
        path=f.name, station=f.station, device_id=f.device_id,
        kv_nominal=f.kv_nominal or None,
        ct_ratio=f.ct_ratio or None, vt_ratio=f.vt_ratio or None,
        settings_substation=sub, settings_feeder=feeder)


def suggest(bundle: Bundle, registry_dir: str = "data/registry",
            lines: Optional[Sequence[Line]] = None) -> int:
    """Fill every usable record's `suggested_*` fields. Returns how many resolved."""
    registry = list(lines) if lines is not None else load_registry(registry_dir)
    for f in bundle.records():
        f.suggested_line_id = f.suggested_end = f.suggested_relay_id = ""
        f.suggested_confidence = 0.0
        f.suggested_reason = ""
        f.suggested_evidence = []
    if not registry:
        for f in bundle.records():
            f.suggested_reason = ("no line definitions in " + registry_dir
                                  + ", so nothing can be resolved against")
        return 0

    resolver = AssetResolver(registry)
    ctx = _settings_context(bundle)
    resolved = 0
    for f in bundle.records():
        if not f.usable:
            f.suggested_reason = "not resolved: this record is not usable"
            continue
        # The operator's own earlier declaration is rank-1 evidence, so a
        # reopened bundle keeps what was decided rather than arguing with it.
        manifest = ({"line_id": f.line_id, "terminal_end": f.terminal_end,
                     "relay_id": f.relay_id, "source": f.assignment_source}
                    if f.terminal_end and f.assignment_source else None)
        r = resolver.resolve(facts_for(bundle, f, ctx), manifest=manifest)
        f.suggested_evidence = [str(h) for h in r.evidence]
        if isinstance(r, Ambiguous):
            f.suggested_reason = r.reason
            continue
        f.suggested_line_id = r.line_id
        f.suggested_end = r.terminal_end
        f.suggested_relay_id = r.relay_id
        f.suggested_confidence = r.confidence
        f.suggested_reason = "resolved from " + ", ".join(
            sorted({h.source for h in r.evidence if h.line_id}))
        resolved += 1
    return resolved


def suggested_line_ids(bundle: Bundle) -> List[str]:
    """Distinct line ids the resolver proposed, most confident first."""
    scored: Dict[str, float] = {}
    for f in bundle.records():
        if f.suggested_line_id:
            scored[f.suggested_line_id] = max(
                scored.get(f.suggested_line_id, 0.0), f.suggested_confidence)
    return [k for k, _ in sorted(scored.items(), key=lambda kv: -kv[1])]
