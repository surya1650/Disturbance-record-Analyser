"""Zone-decision back-test: validation with no patrol result and no far end.

The insight this rests on is that every disturbance record carries its own
partial ground truth. The relay made a decision -- it tripped, in some zone,
at some time -- and that decision is recorded in the digital channels. The
analyser computes the apparent impedance independently and the settings say
which zone should contain it. If the two disagree, either the analyser is
wrong or the relay is, and both are worth knowing.

That check needs no line length, no far-end record and no patrol
confirmation, so it can run over the whole archive today. Confirmed on the
real corpus: Main-2 measures 1.356 + j2.622 secondary ohm and sits inside
Zone 1, and it tripped in Zone 1; Main-1 measures 1.442 + j3.867 and sits in
Zone 2, and it tripped in Zone 2 -- which is itself explained by the Main-1
VT not passing zero sequence.

What this does NOT establish is distance accuracy. A zone is a wide target.
Agreement here means the measurement chain -- parser, ratios, phasors, loop
selection, k0 -- is sound; it does not mean the location is within 1 %.
"""
from __future__ import annotations

import os
import traceback
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .comtrade.conformance import check
from .comtrade.parser import read_cff, read_comtrade
from .dsp.pipeline import analyse
from .faultloc.ensemble import TerminalInput, locate
from .registry.model import Line
from .registry.settings import ProtectionSettings
from .registry.settings_io import load_settings
from .rules.engine import apply_rules, load_rules
from .rules.features import incident_features

RECORD_EXT = (".cfg", ".cff")


@dataclass
class Outcome:
    """What the analyser and the relay each concluded about one record."""

    path: str
    record_id: str = ""
    station: str = ""
    content_hash: str = ""
    ok: bool = False
    error: str = ""
    blocked: bool = False
    flags: List[str] = field(default_factory=list)
    has_fault: bool = False
    fault_type: str = ""
    i_fault_ka: Optional[float] = None
    operate_ms: Optional[float] = None
    breaker_ms: Optional[float] = None
    clear_ms: Optional[float] = None
    zone_operated: Optional[str] = None
    zone_expected: Optional[str] = None
    z_app_r_sec: Optional[float] = None
    z_app_x_sec: Optional[float] = None
    verdict: str = ""
    findings: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)

    @property
    def zone_comparable(self) -> bool:
        """Both sides produced a zone that can be compared.

        Z1_OR_AIDED is deliberately not resolved into Z1 by the timing alone,
        so it counts as agreement with a computed Z1 and is reported
        separately rather than being silently collapsed.
        """
        return bool(self.zone_operated and self.zone_expected
                    and self.zone_expected != "beyond_all_zones")

    @property
    def zone_agrees(self) -> Optional[bool]:
        if not self.zone_comparable:
            return None
        op, ex = self.zone_operated, self.zone_expected
        if op == "Z1_OR_AIDED":
            return ex in ("Z1", "Z1B")
        return op == ex


@dataclass
class BacktestResult:
    outcomes: List[Outcome] = field(default_factory=list)
    duplicates: List[Tuple[str, str]] = field(default_factory=list)

    # ---- aggregates -----------------------------------------------------
    @property
    def analysed(self) -> List[Outcome]:
        return [o for o in self.outcomes if o.ok]

    @property
    def faults(self) -> List[Outcome]:
        return [o for o in self.analysed if o.has_fault]

    def zone_confusion(self) -> Dict[Tuple[str, str], int]:
        out: Dict[Tuple[str, str], int] = {}
        for o in self.faults:
            if o.zone_comparable:
                k = (str(o.zone_operated), str(o.zone_expected))
                out[k] = out.get(k, 0) + 1
        return out

    def agreement(self) -> Tuple[int, int]:
        judged = [o for o in self.faults if o.zone_agrees is not None]
        return sum(1 for o in judged if o.zone_agrees), len(judged)

    def finding_counts(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for o in self.analysed:
            for f in o.findings:
                out[f] = out.get(f, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: -kv[1]))

    def skipped_counts(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for o in self.analysed:
            for f in o.skipped:
                out[f] = out.get(f, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: -kv[1]))

    def flag_counts(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for o in self.outcomes:
            for f in set(o.flags):
                out[f] = out.get(f, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: -kv[1]))

    # ---- reporting ------------------------------------------------------
    def report(self, max_rows: int = 40) -> str:
        bar = "=" * 78
        n_ok, n_tot = len(self.analysed), len(self.outcomes)
        rows = [bar, "BACK-TEST over " + str(n_tot) + " records"]
        if self.duplicates:
            rows.append("  " + str(len(self.duplicates))
                        + " duplicate records skipped (identical content hash)")
        failed = [o for o in self.outcomes if not o.ok]
        rows.append("  analysed " + str(n_ok) + ", failed " + str(len(failed))
                    + ", with a fault " + str(len(self.faults)))
        for o in failed[:6]:
            rows.append("     FAILED " + os.path.basename(o.path) + ": " + o.error)

        rows.append("")
        rows.append("ZONE DECISION -- computed against the zone that operated")
        good, judged = self.agreement()
        if judged:
            rows.append("  agreement " + str(good) + "/" + str(judged) + "  ("
                        + format(100.0 * good / judged, ".1f") + " %)")
            for (op, ex), n in sorted(self.zone_confusion().items(),
                                      key=lambda kv: -kv[1]):
                mark = "ok " if (op == "Z1_OR_AIDED" and ex in ("Z1", "Z1B")) or op == ex \
                    else "XX "
                rows.append("     " + mark + "operated " + format(op, "<12")
                            + " computed " + format(ex, "<12") + " x" + str(n))
        else:
            rows.append("  no record had both a zone decision and relay settings.")
            rows.append("  A .rio settings export next to each record is what enables this.")

        rows.append("")
        rows.append("PROTECTION TIMING (records with a fault)")
        for label, attr in (("relay operating time", "operate_ms"),
                            ("breaker time", "breaker_ms"),
                            ("total clearing time", "clear_ms")):
            vals = sorted(v for v in (getattr(o, attr) for o in self.faults)
                          if v is not None)
            if not vals:
                continue
            mid = vals[len(vals) // 2]
            rows.append("  " + format(label, "<22") + "n=" + format(len(vals), "<4")
                        + " min " + format(vals[0], "6.1f")
                        + "  median " + format(mid, "6.1f")
                        + "  max " + format(vals[-1], "6.1f") + " ms")

        counts = self.finding_counts()
        if counts:
            rows.append("")
            rows.append("FINDINGS BY FREQUENCY -- the fleet-health view")
            for k, n in list(counts.items())[:15]:
                rows.append("  " + format(k, "<10") + "x" + str(n))
        skipped = self.skipped_counts()
        if skipped:
            rows.append("")
            rows.append("RULES THAT COULD NOT BE JUDGED -- recording gaps to fix")
            for k, n in list(skipped.items())[:10]:
                rows.append("  " + format(k, "<10") + "x" + str(n))
        flags = self.flag_counts()
        if flags:
            rows.append("")
            rows.append("CONFORMANCE FLAGS")
            for k, n in list(flags.items())[:12]:
                rows.append("  " + format(k, "<14") + "x" + str(n))

        rows.append("")
        rows.append("PER RECORD")
        head = ("  " + format("record", "<26") + format("type", "<6")
                + format("kA", ">6") + format("op", ">7") + format("cb", ">7")
                + "  " + format("operated", "<12") + format("computed", "<12")
                + "verdict")
        rows.append(head)
        for o in self.outcomes[:max_rows]:
            if not o.ok:
                rows.append("  " + format(o.record_id or os.path.basename(o.path), "<26")
                            + "ERROR " + o.error[:40])
                continue
            f = lambda v, w=7, p=1: (format(v, str(w) + "." + str(p) + "f")
                                     if isinstance(v, float) else format("-", ">" + str(w)))
            agree = o.zone_agrees
            mark = "" if agree is None else ("  ok" if agree else "  <-- MISMATCH")
            # The classifier always names a type; on a record with no fault
            # that name is an artefact of load unbalance and printing it
            # invites someone to believe there was an AB fault.
            rows.append("  " + format(o.record_id[:25], "<26")
                        + format((o.fault_type or "-") if o.has_fault else "-", "<6")
                        + f(o.i_fault_ka, 6) + f(o.operate_ms) + f(o.breaker_ms)
                        + "  " + format(str(o.zone_operated or "-"), "<12")
                        + format(str(o.zone_expected or "-"), "<12")
                        + (o.verdict or "-") + mark)
        if len(self.outcomes) > max_rows:
            rows.append("  ... " + str(len(self.outcomes) - max_rows) + " more")
        rows.append(bar)
        return "\n".join(rows)

    def to_csv(self, path: str) -> None:
        import csv

        cols = ["path", "record_id", "station", "content_hash", "ok", "error",
                "blocked", "has_fault", "fault_type", "i_fault_ka", "operate_ms",
                "breaker_ms", "clear_ms", "zone_operated", "zone_expected",
                "zone_agrees", "z_app_r_sec", "z_app_x_sec", "verdict"]
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(cols + ["findings", "skipped", "flags"])
            for o in self.outcomes:
                w.writerow([getattr(o, c, "") if c != "zone_agrees" else o.zone_agrees
                            for c in cols]
                           + ["|".join(o.findings), "|".join(o.skipped),
                              "|".join(o.flags)])


# --------------------------------------------------------------------------
def discover(paths: Sequence[str]) -> List[str]:
    """Every COMTRADE record under the given files or directories."""
    out: List[str] = []
    for p in paths:
        if os.path.isfile(p):
            if p.lower().endswith(RECORD_EXT):
                out.append(p)
            continue
        for root, _dirs, files in os.walk(p):
            for f in sorted(files):
                if f.lower().endswith(RECORD_EXT):
                    out.append(os.path.join(root, f))
    return sorted(set(out))


def _find_rio(record_path: str) -> Optional[str]:
    import glob

    d = os.path.dirname(os.path.abspath(record_path))
    base = os.path.splitext(os.path.basename(record_path))[0]
    for cand in (os.path.join(d, base + ext) for ext in (".rio", ".RIO")):
        if os.path.exists(cand):
            return cand
    found = sorted(glob.glob(os.path.join(d, "*.rio"))
                   + glob.glob(os.path.join(d, "*.RIO")))
    return found[0] if found else None


def run(paths: Sequence[str], line: Optional[Line] = None,
        nominal_kv: Optional[float] = None,
        min_fault_ka: float = 0.5) -> BacktestResult:
    """Replay every record found under `paths`.

    Records that contain no fault are analysed and reported, not skipped: a
    trigger with no fault is itself worth counting, and silently dropping
    records is how a back-test comes to flatter itself.
    """
    res = BacktestResult()
    rules = load_rules()
    seen: Dict[str, str] = {}
    kv = nominal_kv if nominal_kv is not None else (line.kv if line else None)

    for path in discover(paths):
        o = Outcome(path=path)
        try:
            rec = (read_cff(path, terminal_end="S") if path.lower().endswith(".cff")
                   else read_comtrade(path, terminal_end="S"))
            o.record_id, o.station = rec.record_id, rec.station
            o.content_hash = rec.content_hash
            if rec.content_hash in seen:
                res.duplicates.append((path, seen[rec.content_hash]))
                continue
            seen[rec.content_hash] = path

            check(rec, nominal_kv=kv)
            o.flags = rec.flag_codes()
            o.blocked = rec.blocked()
            if o.blocked:
                o.ok, o.error = True, ""
                res.outcomes.append(o)
                continue

            an = analyse(rec)
            rio_path = _find_rio(path)
            settings: Optional[ProtectionSettings] = (load_settings(rio_path)
                                                     if rio_path else None)

            loc = None
            if line is not None:
                loc = locate(line, {"S": TerminalInput(
                    analysed=an, end="S", zs1=line.terminals["S"].zs1,
                    zs0=line.terminals["S"].zs0)})
            z2 = 0.35
            if settings is not None and settings.zone("Z2"):
                z2 = settings.zone("Z2").t1
            ct = line.terminals["S"].it.ct_ratio if line else 1.0
            vt = line.terminals["S"].it.vt_ratio if line else 1.0
            feats = incident_features(
                {"S": an}, location=loc, line=line,
                settings={"S": settings} if settings else None, z2_time_s=z2)

            o.fault_type = feats.get("S_fault_type") or ""
            o.i_fault_ka = feats.get("S_i_fault_ka")
            o.has_fault = bool(o.i_fault_ka and o.i_fault_ka >= min_fault_ka
                               and feats.get("S_trip_ms") is not None)
            o.operate_ms = feats.get("S_operate_ms")
            o.breaker_ms = feats.get("S_breaker_ms")
            o.clear_ms = feats.get("S_clear_ms")
            o.zone_operated = feats.get("S_zone_operated")
            o.zone_expected = feats.get("S_zone_expected")
            o.z_app_r_sec = feats.get("S_z_app_r_sec")
            o.z_app_x_sec = feats.get("S_z_app_x_sec")

            rr = apply_rules(feats, rules)
            o.verdict = rr.verdict
            o.findings = [f.rule_id for f in rr.findings]
            o.skipped = [s.rule_id for s in rr.skipped]
            o.ok = True
        except Exception as exc:                       # noqa: BLE001
            o.ok = False
            o.error = type(exc).__name__ + ": " + str(exc)
            o.__dict__["_traceback"] = traceback.format_exc()
        res.outcomes.append(o)
    return res
