"""Command line entry point.

    dranalyse locate --line line.yaml --S a.cfg --R b.cfg
    dranalyse locate --line line.yaml --S a.cfg              (single-ended)
    dranalyse inspect record.cfg
    dranalyse verdict --S a.cfg --R b.cfg --line line.yaml
    dranalyse report  --S a.cfg --line line.yaml -o incident.html
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

from .commands import (BAR, cmd_accuracy, cmd_backtest, cmd_capture,
                       cmd_confirm, cmd_inspect, cmd_locate, cmd_pending,
                       cmd_report, cmd_selftest, cmd_settings, cmd_stage_a,
                       cmd_template, cmd_verdict)
from .wb import cmd_bundle, cmd_workbench
from ..standards.cli import cmd_standards

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

    q = sub.add_parser("report", help="two-page incident report as self-contained HTML")
    q.add_argument("--S", help="COMTRADE record at end S")
    q.add_argument("--R", help="COMTRADE record at end R")
    q.add_argument("--line", help="line definition YAML")
    q.add_argument("-o", "--out", help="output HTML path")
    q.add_argument("--confirm-url", dest="confirm_url",
                   help="base URL of the capture form, e.g. http://dr:8080")
    q.add_argument("--db", default="dranalyser.db",
                   help="register the incident here so it can be confirmed later")
    q.set_defaults(func=cmd_report)

    q = sub.add_parser("stage-a", help="full synthetic acceptance sweep (section 13)")
    q.add_argument("--cases", type=int, default=10000)
    q.add_argument("--workers", type=int, default=None, help="default: cpus - 1")
    q.add_argument("--seed", type=int, default=0)
    q.add_argument("--csv", help="write every case to this CSV")
    q.add_argument("--quiet", action="store_true")
    q.set_defaults(func=cmd_stage_a)

    q = sub.add_parser("confirm", help="record a patrol-confirmed fault location")
    q.add_argument("incident_id")
    q.add_argument("--tower", help="tower number where the fault was found")
    q.add_argument("--km", type=float, help="chainage from the S terminal")
    q.add_argument("--cause")
    q.add_argument("--by", help="who confirmed it")
    q.add_argument("--confidence")
    q.add_argument("--notes")
    q.add_argument("--db", default="dranalyser.db")
    q.set_defaults(func=cmd_confirm)

    q = sub.add_parser("pending", help="incidents with no patrol result yet")
    q.add_argument("--line-id", dest="line_id")
    q.add_argument("--db", default="dranalyser.db")
    q.set_defaults(func=cmd_pending)

    q = sub.add_parser("accuracy", help="measured accuracy against confirmations")
    q.add_argument("--line-id", dest="line_id")
    q.add_argument("--detail", action="store_true", help="list every scored incident")
    q.add_argument("--db", default="dranalyser.db")
    q.set_defaults(func=cmd_accuracy)

    q = sub.add_parser("capture", help="serve the ground-truth capture form")
    q.add_argument("--host", default="0.0.0.0")
    q.add_argument("--port", type=int, default=8080)
    q.add_argument("--db", default="dranalyser.db")
    q.set_defaults(func=cmd_capture)

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

    q = sub.add_parser("standards",
                       help="audit a record and relay settings against the standards pack")
    q.add_argument("record", nargs="?", help="COMTRADE .cfg or .cff record")
    q.add_argument("--line", help="line definition YAML")
    q.add_argument("--rio", help="relay settings export")
    q.add_argument("--end", choices=("S", "R"), default="S")
    q.add_argument("--kv", type=float, help="nominal kV when no line file is supplied")
    q.add_argument("--thermal-mva", type=float, dest="thermal_mva",
                   help="line conductor thermal rating for the RLD calculation")
    q.add_argument("--bay-mva", type=float, dest="bay_mva",
                   help="bay-equipment rating; the lower rating governs")
    q.add_argument("--load-reach-ohm", type=float, dest="load_reach_ohm",
                   help="configured primary-ohm RLD reach to compare")
    q.add_argument("--show-context", action="store_true",
                   help="print normalized source chunks (works without a record)")
    q.add_argument("--asset-type",
                   help="filter context, e.g. line, transformer, busbar, generator")
    q.add_argument("--topic", help="filter context by topic substring")
    q.add_argument("--source", help="filter context by source id")
    q.set_defaults(func=cmd_standards)

    q = sub.add_parser("template", help="write a starter line definition")
    q.add_argument("path")
    q.set_defaults(func=cmd_template)

    q = sub.add_parser("bundle",
                       help="resolve a folder or zip into ONE incident and describe it")
    q.add_argument("path", help="folder or .zip of records for a single fault")
    q.add_argument("--id", help="bundle id (defaults to the folder name)")
    q.add_argument("--line-id", dest="line_id", help="line this incident belongs to")
    q.add_argument("--S", action="append", metavar="FILE",
                   help="file inside the bundle at end S; repeat for Main-1 and Main-2")
    q.add_argument("--R", action="append", metavar="FILE",
                   help="file inside the bundle at end R; repeat for Main-1 and Main-2")
    q.add_argument("--out", help="manifest path (defaults to _asset.yaml in the bundle)")
    q.set_defaults(func=cmd_bundle)

    q = sub.add_parser("workbench",
                       help="serve the local upload-and-analyse workbench")
    q.add_argument("--host", default="127.0.0.1",
                   help="bind address; the default is this machine only. This "
                        "tool has no authentication and serves live protection "
                        "data, so widen it deliberately.")
    q.add_argument("--port", type=int, default=8090)
    q.add_argument("--root", default="out/bundles",
                   help="where uploaded bundles are kept")
    q.add_argument("--registry", default="data/registry",
                   help="directory of line definition YAML files")
    q.set_defaults(func=cmd_workbench)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
