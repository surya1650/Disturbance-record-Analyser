"""CLI adapter for the source-grounded standards audit."""
from __future__ import annotations

import math
import os

from ..comtrade.conformance import check
from ..comtrade.parser import read_cff, read_comtrade
from ..registry.loader import load_line
from ..registry.rio import read_rio
from .audit import AuditResult, audit_record, audit_settings, load_encroachment_min_ohm
from .catalogue import context_text, search_chunks


def _read(path: str, end: str):
    return read_cff(path, terminal_end=end) if path.lower().endswith(".cff") else \
        read_comtrade(path, terminal_end=end)


def cmd_standards(args) -> int:
    """Audit a record and/or settings against the supplied standards pack."""
    show_context = getattr(args, "show_context", False)
    asset_type = getattr(args, "asset_type", None)
    topic = getattr(args, "topic", None)
    source_id = getattr(args, "source", None)
    if show_context:
        chunks = search_chunks(asset_type=asset_type, topic=topic, source_id=source_id)
        if chunks:
            print(context_text(chunks))
            print(f"\n{len(chunks)} standards context chunk(s)")
        else:
            print("no standards context chunks matched")

    line = load_line(args.line) if args.line else None
    rio_path = args.rio
    if not rio_path and args.record:
        directory = os.path.dirname(os.path.abspath(args.record))
        base = os.path.splitext(os.path.basename(args.record))[0]
        for ext in (".rio", ".RIO", ".Rio"):
            candidate = os.path.join(directory, base + ext)
            if os.path.exists(candidate):
                rio_path = candidate
                break
    settings = read_rio(rio_path) if rio_path else None

    combined = AuditResult()
    if args.record:
        rec = _read(args.record, args.end)
        check(rec, nominal_kv=line.kv if line else args.kv)
        combined.extend(audit_record(rec, line).checks)
    if args.record is None and settings is None and line is None:
        if show_context:
            return 0
        print("supply a record, --rio, --line, or --show-context")
        return 2

    if settings is not None or args.rio or line is not None:
        combined.extend(audit_settings(
            settings, line, terminal_end=args.end,
            configured_load_reach_primary_ohm=args.load_reach_ohm,
            thermal_rating_mva=args.thermal_mva,
            bay_rating_mva=args.bay_mva,
        ).checks)

    print("=" * 78)
    print(combined.report(indent=""))
    if args.thermal_mva and line is not None:
        angle = settings.line_angle_deg if settings else math.degrees(math.atan2(
            line.z1.imag, line.z1.real))
        primary = load_encroachment_min_ohm(
            line.kv, args.thermal_mva, angle, bay_rating_mva=args.bay_mva)
        print("  calculated RLD: " + format(primary, ".3f") + " primary ohm")
        terminal = line.terminals.get(args.end)
        if terminal and terminal.it.ct_ratio > 0:
            factor = terminal.it.vt_ratio / terminal.it.ct_ratio
            print("                  " + format(primary / factor, ".3f")
                  + " secondary ohm at end " + args.end)
    return 1 if combined.gaps else 0
