"""Stage-A validation: the synthetic acceptance sweep from the brief's 13.

The criterion is a two-ended error below 0.5 % of line length in 95 % of
clean-data cases, over 10^4 to 10^5 simulated faults sweeping m, fault type,
fault resistance, source impedance ratio, inception angle, CT saturation and
sampling rate.

Two things this is careful about.

First, it reports the sweep BOTH ways: over clean cases, which is what the
criterion is written against, and over everything including saturated CTs,
weak infeed and short windows. Quoting only the clean figure is how a
validation comes to describe a system nobody recognises in the field.

Second, it breaks the error down by condition and prints it beside the
accuracy the brief's 7.4 claims for that condition. A sweep that produces one
number tells you whether you passed; a sweep broken down by condition tells
you which physics you have not handled, and that is the useful output.

The worker is a module-level function and the parameters are plain floats, so
this parallelises across processes on Windows as well as POSIX.
"""
from __future__ import annotations

import math
import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .dsp.pipeline import analyse
from .faultloc.ensemble import TerminalInput, locate
from .registry.model import uniform_line
from .synth.generator import SynthSpec, TerminalSpec, generate

FAULTS = ("AG", "BG", "CG", "AB", "BC", "CA", "ABG", "BCG", "CAG", "ABC")
GROUND = ("AG", "BG", "CG")

# Real relay sampling rates, as samples per cycle at 50 Hz.
SAMPLE_RATES = (600.0, 1000.0, 1200.0, 2000.0, 4800.0)

# What the brief's 7.4 claims for the two-ended method, as % of line length.
CLAIMED = {
    "clean": 0.5,
    "high_rf": 1.0,
    "weak_infeed": 2.0,
    "three_phase": 1.5,
    "short_window": 4.0,
}


@dataclass
class CaseResult:
    seed: int
    m_true: float
    fault: str
    rf: float
    sir_s: float
    sir_r: float
    inception_deg: float
    fs_s: float
    fs_r: float
    saturated: bool
    adc_bits: int
    window_cycles: float
    ok: bool = False
    mode: str = ""
    method: str = ""
    m_est: float = float("nan")
    err_pct: float = float("nan")
    e5_err_pct: float = float("nan")
    single_err_pct: float = float("nan")
    impossible_unflagged: bool = False
    reason: str = ""

    # ---- condition buckets ----------------------------------------------
    @property
    def high_rf(self) -> bool:
        return self.rf > 20.0 if self.fault in GROUND else self.rf > 4.0

    @property
    def weak_infeed(self) -> bool:
        return max(self.sir_s, self.sir_r) > 8.0

    @property
    def three_phase(self) -> bool:
        return self.fault in ("ABC", "ABCG")

    @property
    def short_window(self) -> bool:
        return self.window_cycles < 1.0

    @property
    def clean(self) -> bool:
        """Clean data, as the acceptance criterion means it."""
        return not (self.saturated or self.short_window or self.weak_infeed
                    or self.high_rf)


def _sample(rng: np.random.Generator, seed: int) -> Dict[str, Any]:
    fault = FAULTS[int(rng.integers(0, len(FAULTS)))]
    ground = fault in GROUND
    # log-uniform fault resistance: arc resistance spans decades, and a
    # uniform draw would put almost every case at the high end
    rf = float(np.exp(rng.uniform(math.log(0.1), math.log(60.0 if ground else 5.0))))
    z1 = complex(0.030, 0.400) * 100.0
    sir_s = float(np.exp(rng.uniform(math.log(0.1), math.log(30.0))))
    sir_r = float(np.exp(rng.uniform(math.log(0.1), math.log(30.0))))
    ang = math.radians(85.0)
    zs_s = abs(z1) * sir_s * complex(math.cos(ang), math.sin(ang))
    zs_r = abs(z1) * sir_r * complex(math.cos(ang), math.sin(ang))
    # a Zone 2 trip in a fifth of cases, which lengthens the window
    z2 = rng.random() < 0.2
    trip = float(rng.uniform(0.30, 0.45)) if z2 else float(rng.uniform(0.015, 0.030))
    return {
        "seed": seed,
        "m": float(rng.uniform(0.02, 0.98)),
        "fault": fault,
        "rf": rf,
        "sir_s": sir_s,
        "sir_r": sir_r,
        "zs1_S": zs_s, "zs0_S": zs_s * 2.5,
        "zs1_R": zs_r, "zs0_R": zs_r * 2.5,
        "load_angle": float(rng.uniform(-30.0, 30.0)),
        "inception_deg": float(rng.uniform(0.0, 360.0)),
        "fs_s": float(SAMPLE_RATES[int(rng.integers(0, len(SAMPLE_RATES)))]),
        "fs_r": float(SAMPLE_RATES[int(rng.integers(0, len(SAMPLE_RATES)))]),
        "sat_s": bool(rng.random() < 0.10),
        "sat_r": bool(rng.random() < 0.10),
        "adc_bits": int(rng.choice([12, 14, 16])),
        "noise_pct": float(rng.uniform(0.02, 0.25)),
        "trip_s": trip,
        "trip_r": trip + float(rng.uniform(-0.004, 0.004)),
        "cb_s": float(rng.uniform(0.040, 0.080)),
        "cb_r": float(rng.uniform(0.040, 0.080)),
        "clock_offset": float(rng.uniform(-2000.0, 2000.0)),
    }


def run_case(p: Dict[str, Any]) -> CaseResult:
    """One synthetic incident, end to end. Safe to call in a worker process."""
    spec = SynthSpec(
        m=p["m"], fault=p["fault"], rf=p["rf"], seed=p["seed"],
        load_angle_deg=p["load_angle"], inception_angle_deg=p["inception_deg"],
        zs1_S=p["zs1_S"], zs0_S=p["zs0_S"], zs1_R=p["zs1_R"], zs0_R=p["zs0_R"],
        S=TerminalSpec(fs=p["fs_s"], prefault_s=0.12, post_s=0.25,
                       trip_delay_s=p["trip_s"], breaker_time_s=p["cb_s"],
                       ct_saturation=p["sat_s"], adc_bits=p["adc_bits"],
                       noise_pct=p["noise_pct"]),
        R=TerminalSpec(fs=p["fs_r"], prefault_s=0.16, post_s=0.25,
                       trip_delay_s=p["trip_r"], breaker_time_s=p["cb_r"],
                       ct_saturation=p["sat_r"], adc_bits=p["adc_bits"],
                       noise_pct=p["noise_pct"], sample_phase=0.37,
                       clock_offset_s=p["clock_offset"]),
    )
    res = CaseResult(
        seed=p["seed"], m_true=p["m"], fault=p["fault"], rf=p["rf"],
        sir_s=p["sir_s"], sir_r=p["sir_r"], inception_deg=p["inception_deg"],
        fs_s=p["fs_s"], fs_r=p["fs_r"], saturated=bool(p["sat_s"] or p["sat_r"]),
        adc_bits=p["adc_bits"], window_cycles=0.0)
    try:
        case = generate(spec)
        line = uniform_line("SA", "stage-a", spec.kv, spec.line_km, spec.z1_per_km,
                            spec.z0_per_km, spec.zs1_S, spec.zs0_S,
                            spec.zs1_R, spec.zs0_R)
        ans = {e: analyse(case.records[e]) for e in ("S", "R")}
        res.window_cycles = min(a.window.cycles for a in ans.values())
        terms = {e: TerminalInput(analysed=ans[e], end=e,
                                  zs1=spec.zs1_S if e == "S" else spec.zs1_R,
                                  zs0=spec.zs0_S if e == "S" else spec.zs0_R)
                 for e in ("S", "R")}
        loc = locate(line, terms)
        res.ok = bool(loc.ok)
        res.mode, res.method = loc.mode, loc.method
        if loc.ok:
            res.m_est = loc.m
            res.err_pct = abs(loc.m - p["m"]) * 100.0
            # an m outside the line must always arrive with a caveat
            outside = not (-0.02 <= loc.m <= 1.02)
            res.impossible_unflagged = bool(outside and not loc.caveats)
        for e in loc.estimates:
            if e.method == "E5" and e.ok:
                res.e5_err_pct = abs(e.m - p["m"]) * 100.0
            if e.method == "E1@S" and e.ok:
                res.single_err_pct = abs(e.m - p["m"]) * 100.0
        if not loc.ok:
            res.reason = "; ".join(loc.caveats)[:120]
    except Exception as exc:                          # noqa: BLE001
        res.ok = False
        res.reason = type(exc).__name__ + ": " + str(exc)[:100]
    return res


# --------------------------------------------------------------------------
def _pct(vals: Sequence[float], q: float) -> float:
    a = sorted(v for v in vals if math.isfinite(v))
    if not a:
        return float("nan")
    return a[min(int(q / 100.0 * len(a)), len(a) - 1)]


@dataclass
class Summary:
    results: List[CaseResult] = field(default_factory=list)

    def subset(self, name: str) -> List[CaseResult]:
        if name == "all":
            return [r for r in self.results if r.ok]
        return [r for r in self.results if r.ok and getattr(r, name)]

    def stats(self, rows: Sequence[CaseResult]) -> Dict[str, float]:
        e = [r.err_pct for r in rows if math.isfinite(r.err_pct)]
        if not e:
            return {"n": 0}
        return {"n": len(e), "mean": sum(e) / len(e), "p50": _pct(e, 50),
                "p90": _pct(e, 90), "p95": _pct(e, 95), "max": max(e)}

    def passed(self) -> bool:
        s = self.stats(self.subset("clean"))
        no_silent = not any(r.impossible_unflagged for r in self.results if r.ok)
        return bool(s.get("n") and s["p95"] < 0.5 and no_silent)

    def report(self) -> str:
        bar = "=" * 78
        n = len(self.results)
        ok = [r for r in self.results if r.ok]
        rows = [bar, "STAGE-A SWEEP over " + str(n) + " synthetic incidents",
                "  located " + str(len(ok)) + ", failed " + str(n - len(ok))]
        bad = [r for r in self.results if not r.ok][:4]
        for r in bad:
            rows.append("     seed " + str(r.seed) + " " + r.fault + ": " + r.reason)

        rows.append("")
        rows.append("ERROR AS % OF LINE LENGTH")
        rows.append("  " + format("subset", "<16") + format("n", ">7")
                    + format("mean", ">8") + format("p50", ">8") + format("p90", ">8")
                    + format("p95", ">8") + format("max", ">9") + "   brief 7.4")
        for name, label in (("clean", "clean data"), ("all", "everything"),
                            ("high_rf", "high Rf"), ("weak_infeed", "weak infeed"),
                            ("three_phase", "three-phase"),
                            ("short_window", "short window"),
                            ("saturated", "CT saturated")):
            s = self.stats(self.subset(name))
            if not s.get("n"):
                continue
            claim = CLAIMED.get(name)
            rows.append("  " + format(label, "<16") + format(s["n"], "7d")
                        + format(s["mean"], "8.3f") + format(s["p50"], "8.3f")
                        + format(s["p90"], "8.3f") + format(s["p95"], "8.3f")
                        + format(s["max"], "9.3f")
                        + ("   <= " + format(claim, ".1f") + " %" if claim else ""))

        rows.append("")
        rows.append("BY FAULT TYPE")
        for ft in FAULTS:
            s = self.stats([r for r in ok if r.fault == ft])
            if s.get("n"):
                rows.append("  " + format(ft, "<16") + format(s["n"], "7d")
                            + format(s["mean"], "8.3f") + format(s["p50"], "8.3f")
                            + format(s["p90"], "8.3f") + format(s["p95"], "8.3f")
                            + format(s["max"], "9.3f"))

        rows.append("")
        rows.append("BY SAMPLE RATE, clean cases -- samples per cycle at the slower end")
        buckets: Dict[float, List[CaseResult]] = {}
        for r in self.subset("clean"):
            buckets.setdefault(round(min(r.fs_s, r.fs_r) / 50.0), []).append(r)
        for spc in sorted(buckets):
            s = self.stats(buckets[spc])
            if s.get("n"):
                rows.append("  " + format(str(spc) + " smp/cyc", "<16")
                            + format(s["n"], "7d") + format(s["mean"], "8.3f")
                            + format(s["p50"], "8.3f") + format(s["p90"], "8.3f")
                            + format(s["p95"], "8.3f") + format(s["max"], "9.3f"))

        rows.append("")
        rows.append("TWO-ENDED AGAINST SINGLE-ENDED, same incidents")
        both = [r for r in ok if math.isfinite(r.e5_err_pct)
                and math.isfinite(r.single_err_pct)]
        if both:
            e5 = [r.e5_err_pct for r in both]
            se = [r.single_err_pct for r in both]
            rows.append("  E5 two-ended    n=" + format(len(e5), "<6")
                        + " mean " + format(sum(e5) / len(e5), "7.3f")
                        + "  p95 " + format(_pct(e5, 95), "7.3f"))
            rows.append("  E1 single-ended n=" + format(len(se), "<6")
                        + " mean " + format(sum(se) / len(se), "7.3f")
                        + "  p95 " + format(_pct(se, 95), "7.3f"))
            better = sum(1 for r in both if r.e5_err_pct < r.single_err_pct)
            rows.append("  two-ended is closer on " + str(better) + "/" + str(len(both))
                        + " incidents (" + format(100.0 * better / len(both), ".1f") + " %)")

        silent = [r for r in self.results if r.impossible_unflagged]
        rows.append("")
        rows.append("  impossible m returned without a caveat: " + str(len(silent))
                    + (" -- FAIL" if silent else ""))
        s = self.stats(self.subset("clean"))
        rows.append("")
        rows.append("STAGE-A CRITERION  two-ended error < 0.5 % of line in 95 % of "
                    "clean cases")
        rows.append("  clean p95 = " + format(s.get("p95", float("nan")), ".4f")
                    + " %   ->  " + ("PASS" if self.passed() else "FAIL"))
        rows.append(bar)
        return "\n".join(rows)

    def to_csv(self, path: str) -> None:
        import csv

        rows = [asdict(r) for r in self.results]
        if not rows:
            return
        extra = ["clean", "high_rf", "weak_infeed", "three_phase", "short_window"]
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]) + extra)
            w.writeheader()
            for r, obj in zip(rows, self.results):
                r.update({k: getattr(obj, k) for k in extra})
                w.writerow(r)


def run(cases: int = 10000, workers: Optional[int] = None, seed: int = 0,
        progress=None) -> Summary:
    rng = np.random.default_rng(seed)
    params = [_sample(rng, seed * 1000003 + i) for i in range(cases)]
    workers = workers if workers is not None else max((os.cpu_count() or 2) - 1, 1)
    out: List[CaseResult] = []
    if workers <= 1:
        for i, p in enumerate(params):
            out.append(run_case(p))
            if progress and i % 500 == 0:
                progress(i, cases)
    else:
        chunk = max(1, cases // (workers * 8))
        with ProcessPoolExecutor(max_workers=workers) as ex:
            for i, r in enumerate(ex.map(run_case, params, chunksize=chunk)):
                out.append(r)
                if progress and i % 500 == 0:
                    progress(i, cases)
    return Summary(results=out)
