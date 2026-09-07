"""Command line entry point.

    dranalyse locate --line line.yaml --S a.cfg --R b.cfg
    dranalyse locate --line line.yaml --S a.cfg              (single-ended)
    dranalyse inspect record.cfg
    dranalyse selftest
    dranalyse template line.yaml

One record gives a single-ended answer, two give a double-ended one, through
the same code path. The per-method table is always printed: a single number
with no method attached is never reported.
"""
from __future__ import annotations

import argparse
import math
import os
import sys
from typing import Dict, List, Optional

import numpy as np

from .comtrade.conformance import check
from .comtrade.parser import read_cff, read_comtrade
from .dsp.pipeline import analyse
from .faultloc.ensemble import TerminalInput, locate
from .registry.loader import dump_template, load_line
from .registry.model import Line

BAR = "=" * 78


def _read_any(path: str, end: str = ""):
    if path.lower().endswith(".cff"):
        return read_cff(path, terminal_end=end)
    return read_comtrade(path, terminal_end=end)


def _find_rio(record_path: str) -> Optional[str]:
    """A settings export sitting next to the record.

    Relays that write a .rio alongside every disturbance record hand over the
    zone reaches, the characteristic and k0 for free, which is otherwise the
    longest-lead-time item in the registry.
    """
    import glob

    d = os.path.dirname(os.path.abspath(record_path))
    base = os.path.splitext(os.path.basename(record_path))[0]
    exact = [os.path.join(d, base + ext) for ext in (".rio", ".RIO", ".Rio")]
    for p in exact:
        if os.path.exists(p):
            return p
    found = sorted(glob.glob(os.path.join(d, "*.rio")) + glob.glob(os.path.join(d, "*.RIO")))
    return found[0] if found else None


def _fmt_flags(rec) -> str:
    if not rec.flags:
        return "    (no conformance findings)"
    return "\n".join("    " + str(f) for f in rec.flags)


def cmd_inspect(args) -> int:
    rec = _read_any(args.record)
    check(rec, nominal_kv=args.kv)
    print(BAR)
    print(rec.summary())
    print("  station    :", rec.station)
    print("  device     :", rec.device_id)
    print("  edition    :", rec.notes.get("edition"), "(rev_year field:",
          repr(rec.rev_year) + ")")
    print("  data       :", rec.notes.get("file_type"), " naming:",
          rec.notes.get("naming"), " nrates:", rec.nrates)
    print("  start      :", rec.start_time)
    print("  trigger    :", rec.trigger_time,
          "(" + format((rec.trigger_offset_s() or 0) * 1000, ".1f") + " ms into the record)")
    print("  channels   :", ", ".join(sorted(rec.analog)))
    um = rec.notes.get("unmapped_channels") or []
    if um:
        print("  unmapped   :", ", ".join(um[:10]))
    print("  digitals   :", len(rec.digital))
    print("  conformance:")
    print(_fmt_flags(rec))

    an = analyse(rec)
    print("  analysis   :")
    print("    frequency        :", format(an.freq, ".3f"), "Hz")
    if an.inception:
        print("    inception        :", format(an.inception.t_refined * 1000, ".2f"),
              "ms into the record")
    print("    fault type       :", an.fault_type,
          "(|I2|/|dI1|=" + format(an.fault_diag.get("r2", 0), ".3f"),
          "|I0|/|dI1|=" + format(an.fault_diag.get("r0", 0), ".3f") + ")")
    if an.t_trip is not None:
        print("    trip asserted    :", format(an.t_trip * 1000, ".2f"), "ms")
    if an.t_open is not None:
        print("    breaker open     :", format(an.t_open * 1000, ".2f"), "ms")
    if an.inception and an.t_trip:
        print("    operating time   :",
              format((an.t_trip - an.inception.t_refined) * 1000, ".1f"), "ms")
    if an.t_trip and an.t_open:
        print("    breaker time     :", format((an.t_open - an.t_trip) * 1000, ".1f"), "ms")
    print("    analysis window  :", format(an.window.t_start * 1000, ".1f"), "-",
          format(an.window.t_end * 1000, ".1f"), "ms  (" +
          format(an.window.cycles, ".2f"), "cycles,", an.window.mode + ")")
    print("    CT saturation    :", an.saturation.detected,
          an.saturation.channels or "")
    return 0


def cmd_locate(args) -> int:
    line: Line = load_line(args.line)
    print(BAR)
    print("LINE  ", line.id, "-", line.name)
    print("       ", format(line.kv, ".0f"), "kV,", format(line.length_km, ".3f"), "km,",
          len(line.sections), "section(s),", len(line.towers), "towers")
    print("        Z1 =", format(line.z1.real, ".4f"), "+ j" + format(line.z1.imag, ".4f"),
          "ohm    Z0 =", format(line.z0.real, ".4f"), "+ j" + format(line.z0.imag, ".4f"), "ohm")
    print("        k0 =", format(abs(line.k0_line), ".4f"), "angle",
          format(math.degrees(np.angle(line.k0_line)), "+.3f"), "deg")

    paths = {"S": args.S, "R": args.R}
    terminals: Dict[str, TerminalInput] = {}
    for end in ("S", "R"):
        p = paths[end]
        if not p:
            continue
        rec = _read_any(p, end=end)
        check(rec, nominal_kv=line.kv)
        term = line.terminals[end]
        print(BAR)
        print("END", end, "-", term.substation, ":", rec.summary())
        print(_fmt_flags(rec))
        if rec.blocked():
            print("    -> BLOCKED, this record does not proceed to fault location")
            continue
        an = analyse(rec, vt_type=term.it.vt_type)
        print("    inception " + (format(an.inception.t_refined * 1000, ".2f") + " ms"
                                  if an.inception else "not detected")
              + " | type " + an.fault_type
              + " | window " + format(an.window.cycles, ".2f") + " cyc (" + an.window.mode + ")"
              + " | CT sat " + str(an.saturation.detected))
        clock_good = bool(rec.notes.get("tmq_code"))
        terminals[end] = TerminalInput(analysed=an, end=end, zs1=term.zs1, zs0=term.zs0,
                                       clock_good=clock_good,
                                       polarity=term.i_polarity)

    if not terminals:
        print("\nNo record passed the conformance gate. Nothing to locate.")
        return 2

    res = locate(line, terminals)
    print(BAR)
    print("PER-METHOD TABLE")
    print(res.table())
    print(BAR)
    if not res.ok:
        print("RESULT: no location produced.")
        for c in res.caveats:
            print("  caveat:", c)
        return 3

    print("RESULT  " + res.mode.upper() + "   fault type " + res.fault_type)
    print("  distance   : " + format(res.km_from_S, ".3f") + " km from "
          + line.terminals["S"].substation + "   ("
          + format(res.km_from_R, ".3f") + " km from " + line.terminals["R"].substation + ")")
    print("  interval   : " + format(res.interval_km[0], ".3f") + " to "
          + format(res.interval_km[1], ".3f") + " km  (m = "
          + format(res.m, ".5f") + " pu)")
    print("  method     : " + res.method)
    if res.towers:
        nums = [t.number for t in res.towers]
        print("  towers     : between " + nums[0] + " and " + nums[-1]
              + ", most likely "
              + (res.likely_tower.number if res.likely_tower else "?"))
    print("  disagreement between methods: "
          + format(res.diagnostics.get("method_disagreement_pu", 0) * 100, ".3f")
          + " % of line length")
    for c in res.caveats:
        print("  caveat     : " + c)
    return 0


def cmd_selftest(args) -> int:
    """Stage-A style check that the estimator chain still meets its target."""
    from .dsp.pipeline import analyse as _an
    from .synth.generator import SynthSpec, TerminalSpec, generate
    from .registry.model import uniform_line

    errs: List[float] = []
    n_two = 0
    faults = ["AG", "BG", "CG", "AB", "BC", "CA", "BCG", "ABC"]
    for i, m in enumerate(np.linspace(0.05, 0.95, args.cases)):
        ft = faults[i % len(faults)]
        rf = 25.0 if ft in ("AG", "BG", "CG") else 2.0
        spec = SynthSpec(
            m=float(m), fault=ft, rf=rf, seed=i,
            S=TerminalSpec(fs=1000.0, prefault_s=0.12, post_s=0.25, breaker_time_s=0.060),
            R=TerminalSpec(fs=1200.0, prefault_s=0.16, post_s=0.25, breaker_time_s=0.060,
                           sample_phase=0.37, clock_offset_s=1418.0),
        )
        case = generate(spec)
        line = uniform_line("SELFTEST", "selftest", spec.kv, spec.line_km,
                            spec.z1_per_km, spec.z0_per_km,
                            spec.zs1_S, spec.zs0_S, spec.zs1_R, spec.zs0_R)
        terms = {e: TerminalInput(analysed=_an(case.records[e]), end=e,
                                  zs1=spec.zs1_S if e == "S" else spec.zs1_R,
                                  zs0=spec.zs0_S if e == "S" else spec.zs0_R)
                 for e in ("S", "R")}
        res = locate(line, terms)
        if res.ok:
            errs.append(abs(res.m - spec.m) * 100.0)
            if res.mode == "two-ended":
                n_two += 1
    a = np.asarray(errs)
    print(BAR)
    print("SELFTEST  " + str(len(errs)) + "/" + str(args.cases) + " cases located, "
          + str(n_two) + " two-ended")
    print("  mean error : " + format(float(np.mean(a)), ".4f") + " % of line length")
    print("  p90        : " + format(float(np.percentile(a, 90)), ".4f") + " %")
    print("  p95        : " + format(float(np.percentile(a, 95)), ".4f") + " %")
    print("  max        : " + format(float(np.max(a)), ".4f") + " %")
    ok = float(np.percentile(a, 95)) < 0.5
    print("  Stage-A criterion (two-ended error < 0.5 % in 95 % of clean cases): "
          + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def cmd_settings(args) -> int:
    """Read a relay settings export and say what it gives you."""
    from .registry.rio import read_rio

    s = read_rio(args.rio)
    print(BAR)
    print(s.summary())
    for w in s.warnings:
        print("  warning:", w)
    if args.ct and args.vt:
        k = s.secondary_to_primary(args.ct, args.vt)
        print(BAR)
        print("With CT " + format(args.ct, ".0f") + "/1 and VT "
              + format(args.vt, ".0f") + ":1, secondary x "
              + format(k, ".3f") + " gives primary ohm")
        for z in s.zones:
            r = s.zone_reach_primary(z.name, args.ct, args.vt)
            if r is None:
                continue
            print("   " + format(z.name, "<5") + format(r.real, "8.3f") + " + j"
                  + format(r.imag, "7.3f") + " primary ohm"
                  + ("   REVERSE" if z.reverse else "")
                  + ("   overreach" if z.overreach else ""))
        z1 = s.implied_line_z1(args.ct, args.vt, args.reach)
        z0 = s.implied_line_z0(args.ct, args.vt, args.reach)
        if z1 is not None:
            print(BAR)
            print("Line constants IMPLIED by the Zone 1 setting, assuming Z1 is "
                  + format(args.reach * 100, ".0f") + " % of the line:")
            print("   Z1 = " + format(z1.real, ".3f") + " + j" + format(z1.imag, ".3f")
                  + " ohm      Z0 = " + format(z0.real, ".3f") + " + j"
                  + format(z0.imag, ".3f") + " ohm")
            if args.ohm_per_km:
                print("   at " + format(args.ohm_per_km, ".3f") + " ohm/km that is a "
                      + "line of " + format(z1.imag / args.ohm_per_km, ".1f") + " km")
            print("   This is NOT a survey. If the real line length disagrees, the "
                  "Zone 1\n   reach setting is what is wrong, and that is a finding "
                  "in itself.")
    return 0


def cmd_template(args) -> int:
    dump_template(args.path)
    print("wrote line template to", args.path)
    return 0


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
