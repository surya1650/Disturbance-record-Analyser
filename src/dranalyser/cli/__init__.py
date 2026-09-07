"""Command line entry point.

    dranalyse locate --line line.yaml --S a.cfg --R b.cfg
    dranalyse locate --line line.yaml --S a.cfg              (single-ended)
    dranalyse inspect record.cfg
    dranalyse verdict --S a.cfg --R b.cfg --line line.yaml
    dranalyse settings relay.rio --ct 800 --vt 2000
    dranalyse selftest
    dranalyse template line.yaml

One record gives a single-ended answer, two give a double-ended one, through
the same code path. The per-method table is always printed: a single number
with no method attached is never reported.
"""
from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from .commands import (BAR, cmd_backtest, cmd_inspect, cmd_locate,
                       cmd_selftest, cmd_settings, cmd_template, cmd_verdict)

__all__ = ["main", "build_parser"]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dranalyse",
                                description="Two-ended disturbance record analyser")
    sub = p.add_subparsers(dest="cmd", required=True)

    q = sub.add_parser("locate", help="locate a fault from one or two records")
    q.add_argument("--line", required=True, help="line definition YAML")
    q.add_argument("--S", help="COMTRADE .cfg or .cff at end S")
    q.add_argument("--R", help="COMTRADE .cfg or .cff at end R")
    q.set_defaults(func=cmd_locate)

    q = sub.add_parser("inspect", help="parse and describe one record")
    q.add_argument("record")
    q.add_argument("--kv", type=float, default=None, help="nominal line kV")
    q.set_defaults(func=cmd_inspect)

    q = sub.add_parser("selftest", help="synthetic Stage-A acceptance check")
    q.add_argument("--cases", type=int, default=64)
    q.set_defaults(func=cmd_selftest)

    q = sub.add_parser("verdict",
                       help="protection-performance verdict (no line constants needed)")
    q.add_argument("--S", help="COMTRADE record at end S")
    q.add_argument("--R", help="COMTRADE record at end R")
    q.add_argument("--line", help="line definition YAML (optional; adds location)")
    q.add_argument("--rio", help="relay settings export (auto-discovered if omitted)")
    q.add_argument("--rules", help="rule catalogue YAML (defaults to the built-in one)")
    q.set_defaults(func=cmd_verdict)

    q = sub.add_parser("backtest",
                       help="replay an archive against the relays' own zone decisions")
    q.add_argument("paths", nargs="+", help="record files or directories to walk")
    q.add_argument("--line", help="line definition YAML (optional; adds location)")
    q.add_argument("--kv", type=float, help="nominal line kV when no line file is given")
    q.add_argument("--csv", help="write the per-record table to this CSV")
    q.add_argument("--rows", type=int, default=40, help="rows to print (default 40)")
    q.set_defaults(func=cmd_backtest)

    q = sub.add_parser("settings", help="read a relay .rio settings export")
    q.add_argument("rio")
    q.add_argument("--ct", type=float, help="CT ratio, e.g. 800 for 800/1")
    q.add_argument("--vt", type=float, help="VT ratio, e.g. 2000 for 220000/110")
    q.add_argument("--reach", type=float, default=0.80,
                   help="assumed Zone 1 reach as a fraction of line (default 0.80)")
    q.add_argument("--ohm-per-km", type=float, dest="ohm_per_km",
                   help="line X1 per km, to turn the implied Z1 into a length")
    q.set_defaults(func=cmd_settings)

    q = sub.add_parser("template", help="write a starter line definition")
    q.add_argument("path")
    q.set_defaults(func=cmd_template)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
