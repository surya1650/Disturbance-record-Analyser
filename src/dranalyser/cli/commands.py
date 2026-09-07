"""Implementations of the dranalyse subcommands.

Kept apart from the argparse wiring in __init__ so that adding a command is
adding a function here, and the entry point stays a table of contents.
"""
from __future__ import annotations

import math
import os
from typing import Dict, List, Optional

import numpy as np

from ..comtrade.conformance import check
from ..comtrade.parser import read_cff, read_comtrade
from ..dsp.pipeline import analyse
from ..faultloc.ensemble import TerminalInput, locate
from ..registry.loader import dump_template, load_line
from ..registry.model import Line

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
    from ..dsp.pipeline import analyse as _an
    from ..synth.generator import SynthSpec, TerminalSpec, generate
    from ..registry.model import uniform_line

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


def cmd_verdict(args) -> int:
    """Protection-performance verdict. Needs no line constants and no far end."""
    from ..registry.rio import read_rio
    from ..rules.engine import apply_rules, load_rules
    from ..rules.features import incident_features

    line: Line = load_line(args.line) if args.line else None
    paths = {"S": args.S, "R": args.R}
    ans, settings = {}, {}
    for end in ("S", "R"):
        p = paths[end]
        if not p:
            continue
        rec = _read_any(p, end=end)
        check(rec, nominal_kv=line.kv if line else None)
        term = line.terminals[end] if line else None
        an = analyse(rec, vt_type=term.it.vt_type if term else "CVT")
        ans[end] = an
        rio = args.rio if (end == "S" and args.rio) else _find_rio(p)
        if rio:
            settings[end] = read_rio(rio)
        print(BAR)
        print("END " + end + " : " + rec.summary())
        print("    settings   : " + (os.path.basename(rio) if rio else "none found"))
        for f in rec.flags:
            print("    " + str(f))

    if not ans:
        print("no records given")
        return 2

    res = None
    if line is not None:
        terms = {e: TerminalInput(analysed=a, end=e, zs1=line.terminals[e].zs1,
                                  zs0=line.terminals[e].zs0,
                                  polarity=line.terminals[e].i_polarity)
                 for e, a in ans.items()}
        res = locate(line, terms)

    z2 = 0.35
    for s in settings.values():
        z = s.zone("Z2")
        if z:
            z2 = z.t1
    feats = incident_features(ans, location=res, line=line, settings=settings,
                              z2_time_s=z2)

    print(BAR)
    print("TIMELINE (ms from fault inception at that terminal)")
    rows = ("start_ms", "trip_ms", "operate_ms", "open_ms", "breaker_ms", "clear_ms",
            "carrier_send_ms", "carrier_recv_ms", "pole_open_a_ms", "pole_open_b_ms",
            "pole_open_c_ms", "dead_time_ms")
    print("    " + format("", "<18") + format("S", ">12") + format("R", ">12"))
    for k in rows:
        sv, rv = feats.get("S_" + k), feats.get("R_" + k)
        fmt = lambda x: ("%12.1f" % x) if isinstance(x, (int, float)) else format("-", ">12")
        print("    " + format(k, "<18") + fmt(sv) + fmt(rv))
    for k in ("fault_type", "zone_operated", "zone_expected", "i_fault_ka",
              "three_pole_trip", "ct_saturation", "zero_seq_voltage", "window_cycles"):
        sv, rv = feats.get("S_" + k), feats.get("R_" + k)
        f2 = lambda x: format("-" if x is None else
                              (("%12.3f" % x) if isinstance(x, float) else str(x)), ">12")
        print("    " + format(k, "<18") + f2(sv) + f2(rv))

    print(BAR)
    print(apply_rules(feats, load_rules(args.rules) if args.rules else None).report())
    if res is not None and res.ok:
        print(BAR)
        print("LOCATION  " + res.mode + "  " + format(res.km_from_S, ".3f")
              + " km from " + line.terminals["S"].substation
              + "  by " + res.method)
    return 0


def cmd_report(args) -> int:
    """Two-page incident report: page 1 a decision, page 2 the evidence."""
    from ..registry.rio import read_rio
    from ..report import build, render, write
    from ..rules.engine import apply_rules, load_rules
    from ..rules.features import incident_features

    line: Line = load_line(args.line) if args.line else None
    paths = {"S": args.S, "R": args.R}
    ans, settings = {}, {}
    for end in ("S", "R"):
        p = paths[end]
        if not p:
            continue
        rec = _read_any(p, end=end)
        check(rec, nominal_kv=line.kv if line else None)
        if rec.blocked():
            print("END " + end + " BLOCKED by the conformance gate:")
            for fl in rec.flags:
                if fl.severity == "block":
                    print("    " + str(fl))
            continue
        term = line.terminals[end] if line else None
        ans[end] = analyse(rec, vt_type=term.it.vt_type if term else "CVT")
        rio = _find_rio(p)
        if rio:
            settings[end] = read_rio(rio)
    if not ans:
        print("no analysable record given")
        return 2

    loc = None
    if line is not None:
        loc = locate(line, {e: TerminalInput(analysed=a, end=e,
                                             zs1=line.terminals[e].zs1,
                                             zs0=line.terminals[e].zs0,
                                             polarity=line.terminals[e].i_polarity)
                            for e, a in ans.items()})
    z2 = 0.35
    for s in settings.values():
        if s.zone("Z2"):
            z2 = s.zone("Z2").t1
    feats = incident_features(ans, location=loc, line=line, settings=settings,
                              z2_time_s=z2)
    rr = apply_rules(feats, load_rules())
    base = args.confirm_url or ""
    rep = build(ans, feats, rr, location=loc, line=line, settings=settings,
                ground_truth_url=(base.rstrip("/") + "/confirm/" if base else ""))
    if base:
        rep.ground_truth_url = base.rstrip("/") + "/confirm/" + rep.incident_id
    render(rep)
    out = args.out or (rep.incident_id + ".html")
    write(rep, out)

    # Register the incident so the QR on page 1 has something to confirm
    # against. Without this the capture form has no idea the fault happened.
    if args.db:
        from ..groundtruth import Store

        with Store(args.db) as store:
            store.record_incident(
                rep.incident_id, line.id if line else (feats.get("line_id") or "UNKNOWN"),
                fault_time=str(ans[sorted(ans)[0]].record.trigger_time or ""),
                fault_type=feats.get("fault_type"),
                m=(loc.m if loc and loc.ok else None),
                km_from_S=(loc.km_from_S if loc and loc.ok else None),
                line_km=(line.length_km if line else None),
                method=(loc.method if loc and loc.ok else None),
                mode=(loc.mode if loc and loc.ok else None),
                verdict=rr.verdict, report_path=os.path.abspath(out))
        print("registered for confirmation in " + args.db)
    print("VERDICT: " + rr.verdict)
    if loc is not None and loc.ok:
        print("LOCATION: " + format(loc.km_from_S, ".3f") + " km from "
              + (line.terminals["S"].substation if line else "S")
              + " by " + loc.method + " (" + loc.mode + ")")
    print("wrote " + out)
    if not settings:
        print("note: no .rio settings export was found next to the records, so the "
              "R-X diagram and the computed zone are omitted.")
    return 0


def cmd_backtest(args) -> int:
    """Replay an archive and grade it against the relays' own zone decisions."""
    from .. import backtest

    line = load_line(args.line) if args.line else None
    res = backtest.run(args.paths, line=line, nominal_kv=args.kv)
    print(res.report(max_rows=args.rows))
    if args.csv:
        res.to_csv(args.csv)
        print("wrote " + args.csv)
    good, judged = res.agreement()
    if judged and good < judged:
        return 1
    return 0


def cmd_stage_a(args) -> int:
    """The full synthetic acceptance sweep from the brief's section 13."""
    import sys
    import time

    from .. import stagea

    t0 = time.perf_counter()

    def tick(i, n):
        if not args.quiet:
            sys.stderr.write("\r  %d/%d" % (i, n))
            sys.stderr.flush()

    summ = stagea.run(cases=args.cases, workers=args.workers, seed=args.seed,
                      progress=tick)
    if not args.quiet:
        sys.stderr.write("\r")
    print(summ.report())
    print("  elapsed " + format(time.perf_counter() - t0, ".1f") + " s")
    if args.csv:
        summ.to_csv(args.csv)
        print("  wrote " + args.csv)
    return 0 if summ.passed() else 1


def cmd_confirm(args) -> int:
    """Record a patrol-confirmed fault location against an incident."""
    from ..groundtruth import Confirmation, Store

    with Store(args.db) as store:
        if not store.incident(args.incident_id):
            print("unknown incident " + args.incident_id
                  + "; run `dranalyse pending --db " + args.db + "` to list them")
            return 2
        try:
            store.confirm(Confirmation(
                incident_id=args.incident_id, tower_no=args.tower,
                chainage_km=args.km, cause=args.cause or "",
                confirmed_by=args.by or "", confidence=args.confidence or "",
                notes=args.notes or ""))
        except ValueError as exc:
            print("not recorded: " + str(exc))
            return 2
        s = [x for x in store.scored() if x.incident_id == args.incident_id]
        print("recorded.")
        if s and s[0].error_km is not None:
            print("  estimate " + format(s[0].km_estimated, ".3f")
                  + " km, actual " + format(s[0].km_actual, ".3f")
                  + " km, error " + format(s[0].error_km, "+.3f") + " km"
                  + (" (" + format(s[0].error_pct, "+.2f") + " % of line)"
                     if s[0].error_pct is not None else ""))
        print()
        print(store.accuracy_report())
    return 0


def cmd_pending(args) -> int:
    """Incidents with no patrol result yet: the chase list."""
    from ..groundtruth import Store

    with Store(args.db) as store:
        rows = store.pending(args.line_id)
        print(BAR)
        print("AWAITING CONFIRMATION: " + str(len(rows)) + " incident(s)")
        for r in rows:
            print("  " + format(r["incident_id"], "<34") + format(r["line_id"], "<12")
                  + format(r["fault_time"] or "", "<21")
                  + (format(r["km_from_S"], "8.2f") + " km"
                     if r["km_from_S"] is not None else "       -"))
        print(BAR)
        print(store.accuracy_report())
    return 0


def cmd_accuracy(args) -> int:
    """Measured accuracy against patrol confirmations."""
    from ..groundtruth import Store

    with Store(args.db) as store:
        print(store.accuracy_report(args.line_id))
        if args.detail:
            print()
            print("  " + format("incident", "<34") + format("mode", "<14")
                  + format("est km", ">9") + format("actual", ">9")
                  + format("error", ">9") + "  tower  cause")
            for s in store.scored(args.line_id):
                if s.error_km is None:
                    continue
                print("  " + format(s.incident_id, "<34") + format(s.mode, "<14")
                      + format(s.km_estimated, "9.2f") + format(s.km_actual, "9.2f")
                      + format(s.error_km, "+9.2f") + "  "
                      + format(s.tower_no, "<6") + " " + s.cause)
    return 0


def cmd_capture(args) -> int:
    """Serve the ground-truth capture form the report's QR points at."""
    from ..groundtruth import Store
    from ..groundtruth.web import run

    with Store(args.db) as store:
        print("capture form on http://" + (args.host if args.host != "0.0.0.0"
                                           else "localhost") + ":" + str(args.port))
        print("  point --confirm-url at this address when generating reports")
        print("  Ctrl-C to stop")
        run(store, args.host, args.port)
    return 0


def cmd_settings(args) -> int:
    """Read a relay settings export and say what it gives you."""
    from ..registry.rio import read_rio

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


