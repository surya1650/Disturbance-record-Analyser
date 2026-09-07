"""Cross-check two relays that watched the same fault from the same bus.

Main-1 and Main-2 in one bay measure the same primary current through the
same CT core group and the same VT. They should agree. When they do, the
measurement chain is corroborated by something independent of the analyser.
When they do not, one of them is wrong and the incident report must say so
rather than quietly using whichever record the operator happened to mark
primary.

This is not a hypothetical. On event 15665 at Garividi the GE D60 and the
MiCOM P444 measure the same 305-310 A of negative-sequence current and the
same 2019 / 2024 A of fault current, yet their measured negative-sequence
source impedance differs by a factor of seven and by 75 degrees. Before this
check that disagreement was invisible: it depended entirely on which file was
passed as --R.

**Every threshold below is project policy, not standards-derived.** No
standard states how closely two relays in one bay must agree. They are set
wide enough that ordinary differences -- different sample rates, different
anti-alias filters, a window placed a cycle apart -- do not trip them, and
tight enough to catch a wiring or scaling fault.
"""
from __future__ import annotations

import cmath
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import numpy as np

# Project policy, see the module docstring.
I_TOLERANCE = 0.10          # 10 % on a current magnitude
ZS2_RATIO = 2.0             # a factor of two in |Zs2|
ZS2_ANGLE_DEG = 30.0        # or 30 degrees of argument
ZS2_MAX_SCATTER = 0.10      # a Zs2 noisier than this is not compared at all
PHASES = ("IA", "IB", "IC")


@dataclass
class Measure:
    """What one record says about the fault, in terms two relays can share."""

    file: str = ""
    ok: bool = False
    why: str = ""
    fault_type: str = ""
    i_prefault_a: float = float("nan")
    i_fault_a: float = float("nan")
    zs2: Optional[complex] = None
    zs2_scatter: float = float("nan")

    def zs2_text(self) -> str:
        if self.zs2 is None:
            return "-"
        return (format(abs(self.zs2), ".2f") + " ohm at "
                + format(math.degrees(cmath.phase(self.zs2)), ".1f") + " deg")


@dataclass
class Disagreement:
    code: str
    severity: str               # info | investigate
    text: str


def measure(an, file_name: str = "") -> Measure:
    """Reduce one analysed record to the quantities two relays can be compared on."""
    m = Measure(file=file_name)
    idx = an.indices()
    if len(idx) == 0:
        m.why = "no usable analysis window"
        return m
    m.fault_type = an.fault_type

    ref1 = an.ref.get("I1")
    if ref1 is not None:
        m.i_prefault_a = float(abs(ref1))

    # The 90th percentile of the fundamental on the worst phase, not the
    # median (which a long window dilutes back towards load current) and not
    # the maximum (which one saturated sample can set).
    peaks = []
    for ph in PHASES:
        if ph not in an.ps.phasors:
            continue
        vals = np.abs(np.asarray(an.ps.phasors[ph])[idx])
        if vals.size:
            peaks.append(float(np.percentile(vals, 90)))
    if peaks:
        m.i_fault_a = max(peaks)

    # Zs2 = -V2/I2 with currents positive from bus into the line: the
    # negative-sequence voltage at the bus is the drop across the source
    # branch. Needs no line constants, which is what makes it usable as a
    # cross-check before the registry knows anything about the line.
    if "V2" in an.ps.phasors and "I2" in an.ps.phasors:
        v2 = np.asarray(an.ps.phasors["V2"])[idx]
        i2 = np.asarray(an.ps.phasors["I2"])[idx]
        big = np.abs(i2) > 0.05 * (np.abs(i2).max() or 1.0)
        if big.sum() >= 4:
            z = -v2[big] / i2[big]
            zm = complex(float(np.median(z.real)), float(np.median(z.imag)))
            if abs(zm) > 0:
                m.zs2 = zm
                m.zs2_scatter = float(np.median(np.abs(z - zm)) / abs(zm))

    m.ok = True
    return m


def _ratio_off(a: float, b: float, tol: float) -> bool:
    if not (math.isfinite(a) and math.isfinite(b)):
        return False
    big = max(abs(a), abs(b))
    if big <= 0:
        return False
    return abs(a - b) / big > tol


def compare(end: str, measures: Sequence[Measure]) -> List[Disagreement]:
    """Compare every record at one terminal against the primary (the first)."""
    out: List[Disagreement] = []
    usable = [m for m in measures if m.ok]
    if len(usable) < 2:
        return out
    primary, others = usable[0], usable[1:]

    for other in others:
        pair = "end " + end + ": " + primary.file + " and " + other.file

        if primary.fault_type and other.fault_type \
                and primary.fault_type != other.fault_type:
            out.append(Disagreement(
                "XR-01", "investigate",
                pair + " disagree on the fault type (" + primary.fault_type
                + " against " + other.fault_type
                + "). Two relays on one bus saw one fault; one of them is "
                  "reading the wrong channels."))

        if _ratio_off(primary.i_prefault_a, other.i_prefault_a, I_TOLERANCE):
            out.append(Disagreement(
                "XR-02", "investigate",
                pair + " disagree on pre-fault load current ("
                + format(primary.i_prefault_a, ".1f") + " A against "
                + format(other.i_prefault_a, ".1f")
                + " A). Same line, same instant: suspect a CT ratio."))

        if _ratio_off(primary.i_fault_a, other.i_fault_a, I_TOLERANCE):
            out.append(Disagreement(
                "XR-03", "investigate",
                pair + " disagree on fault current ("
                + format(primary.i_fault_a, ".1f") + " A against "
                + format(other.i_fault_a, ".1f") + " A)."))

        if (primary.zs2 is not None and other.zs2 is not None
                and primary.zs2_scatter <= ZS2_MAX_SCATTER
                and other.zs2_scatter <= ZS2_MAX_SCATTER):
            ratio = max(abs(primary.zs2), abs(other.zs2)) / \
                min(abs(primary.zs2), abs(other.zs2))
            dang = abs(math.degrees(cmath.phase(primary.zs2 / other.zs2)))
            if ratio > ZS2_RATIO or dang > ZS2_ANGLE_DEG:
                out.append(Disagreement(
                    "XR-04", "investigate",
                    pair + " disagree on the measured negative-sequence source "
                    "impedance (" + primary.zs2_text() + " against "
                    + other.zs2_text() + ", a factor of " + format(ratio, ".1f")
                    + " and " + format(dang, ".0f")
                    + " degrees). They share a bus, so they should agree; "
                      "suspect the voltage input on one of them."))

    return out


def corroborate(by_end: Dict[str, List[Measure]]) -> List[Disagreement]:
    found: List[Disagreement] = []
    for end in sorted(by_end):
        found.extend(compare(end, by_end[end]))
    return found
