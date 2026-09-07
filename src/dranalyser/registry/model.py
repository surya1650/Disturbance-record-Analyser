"""Asset & topology registry (PROJECT_CONTEXT.md 11).

Everything downstream reads line constants from here. Nothing else in the
package is allowed to hard-code a line length, an impedance or a k0.
"""
from __future__ import annotations

import cmath
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# --------------------------------------------------------------------------
# k0 / residual-compensation conventions
# --------------------------------------------------------------------------
# The canonical internal form is ALWAYS
#
#       I_loop = I_ph + k0 * 3*I0          with   k0 = (Z0 - Z1) / (3 * Z1)
#
# Relays do not store it that way. The brief's 11 says "k0 mag & angle";
# that field is a trap, because a SIPROTEC stores two *real* ratios and the
# complex k0 derived from them has a non-zero angle that is invisible if you
# copy XE/XL into a "k0 magnitude" box. So the registry stores the vendor's
# native form plus the vendor name, and derives k0. Never enter k0 by hand.
#
# Worked example from the real DHONE 7SA522 RIO file in this repo:
#   RE/RL = 1.020, XE/XL = 0.800, line angle 81 deg
#     -> k0 = 0.806 angle -2.41 deg
#   A naive "k0 = XE/XL = 0.800 angle 0" loses the -2.41 deg entirely, which is
#   worth order 1-2 % of reach on a ground loop.

VENDOR_CONVENTIONS = ("siemens_re_xe", "abb_kn", "alstom_kzn", "sel_k0", "complex_k0")


def k0_from_siemens(re_rl: float, xe_xl: float, line_angle_deg: float) -> complex:
    """SIPROTEC RE/RL and XE/XL (two real ratios) -> complex k0.

    RE/RL = (R0 - R1) / (3*R1),  XE/XL = (X0 - X1) / (3*X1).
    Needs the line angle because the two ratios apply to the resistive and
    reactive parts separately.
    """
    ang = math.radians(line_angle_deg)
    r1, x1 = math.cos(ang), math.sin(ang)
    r0 = r1 * (1.0 + 3.0 * re_rl)
    x0 = x1 * (1.0 + 3.0 * xe_xl)
    z1 = complex(r1, x1)
    z0 = complex(r0, x0)
    return (z0 - z1) / (3.0 * z1)


def k0_from_kn(kn_mag: float, kn_ang_deg: float) -> complex:
    """ABB KN / Alstom kZN are already (Z0-Z1)/(3*Z1) in polar form."""
    return cmath.rect(kn_mag, math.radians(kn_ang_deg))


def k0_from_sel(k0m: float, k0a_deg: float) -> complex:
    """SEL k0M / k0A are also (Z0-Z1)/(3*Z1)."""
    return cmath.rect(k0m, math.radians(k0a_deg))


def k0_from_impedances(z1: complex, z0: complex) -> complex:
    return (z0 - z1) / (3.0 * z1)


@dataclass
class LineSection:
    """One homogeneous stretch of line (11 line_section)."""

    seq: int
    from_km: float
    to_km: float
    r1: float
    x1: float
    r0: float
    x0: float
    b1: float = 0.0
    b0: float = 0.0
    conductor: str = ""

    @property
    def length_km(self) -> float:
        return self.to_km - self.from_km

    @property
    def z1(self) -> complex:
        return complex(self.r1, self.x1) * self.length_km

    @property
    def z0(self) -> complex:
        return complex(self.r0, self.x0) * self.length_km


@dataclass
class InstrumentTransformer:
    ct_ratio: float = 1.0
    vt_ratio: float = 1.0
    vt_type: str = "CVT"
    vt_location: str = "line"
    ct_knee_v: Optional[float] = None
    ct_class: str = ""


@dataclass
class RelaySetting:
    """Versioned settings (11).

    An event is judged against the settings in force at that instant, never
    against the settings in force today.
    """

    effective_from: str = ""
    effective_to: str = ""
    scheme: str = "PUTT"
    z1_reach_pu: float = 0.8
    z2_reach_pu: float = 1.2
    z3_reach_pu: float = 2.0
    z2_time_s: float = 0.35
    z3_time_s: float = 0.8
    line_angle_deg: float = 80.0
    k0_convention: str = "complex_k0"
    k0_params: Dict[str, float] = field(default_factory=dict)

    def k0(self) -> complex:
        c, p = self.k0_convention, self.k0_params
        if c == "siemens_re_xe":
            return k0_from_siemens(
                p["re_rl"], p["xe_xl"], p.get("line_angle_deg", self.line_angle_deg)
            )
        if c in ("abb_kn", "alstom_kzn"):
            return k0_from_kn(p["mag"], p["ang_deg"])
        if c == "sel_k0":
            return k0_from_sel(p["k0m"], p["k0a_deg"])
        if c == "complex_k0":
            return complex(p.get("re", 0.0), p.get("im", 0.0))
        raise ValueError("unknown k0 convention " + repr(c))


@dataclass
class Relay:
    id: str
    make: str = ""
    model: str = ""
    function: str = "main1"
    retrieval: str = "iec61850"
    settings: List[RelaySetting] = field(default_factory=list)

    def setting_at(self, when: str = "") -> Optional[RelaySetting]:
        if not self.settings:
            return None
        if not when:
            return self.settings[-1]
        c = [
            s
            for s in self.settings
            if s.effective_from <= when and (not s.effective_to or when < s.effective_to)
        ]
        return c[-1] if c else self.settings[-1]


@dataclass
class Terminal:
    end: str
    substation: str
    it: InstrumentTransformer = field(default_factory=InstrumentTransformer)
    zs1: complex = 0j
    zs0: complex = 0j
    relays: List[Relay] = field(default_factory=list)
    # +1 = current positive from bus INTO the line, which is what every
    # equation in faultloc assumes. A flipped CT here is silent, not an error.
    i_polarity: int = 1


@dataclass
class Tower:
    number: str
    chainage_km: float
    lat: Optional[float] = None
    lon: Optional[float] = None


@dataclass
class Line:
    id: str
    name: str
    kv: float
    sections: List[LineSection]
    terminals: Dict[str, Terminal]
    towers: List[Tower] = field(default_factory=list)
    double_circuit: bool = False
    series_compensated: bool = False

    @property
    def length_km(self) -> float:
        return sum(s.length_km for s in self.sections)

    @property
    def z1(self) -> complex:
        return sum((s.z1 for s in self.sections), 0j)

    @property
    def z0(self) -> complex:
        return sum((s.z0 for s in self.sections), 0j)

    @property
    def k0_line(self) -> complex:
        return k0_from_impedances(self.z1, self.z0)

    def m_to_km(self, m: float) -> float:
        """m is per unit of total series REACTANCE, not of length (7.3)."""
        total_x = sum(s.z1.imag for s in self.sections)
        if total_x <= 0:
            raise ValueError("line " + self.id + " has non-positive total reactance")
        target = m * total_x
        acc = 0.0
        for s in self.sections:
            sx = s.z1.imag
            last = s is self.sections[-1]
            if acc + sx >= target or last:
                frac = (target - acc) / sx if sx else 0.0
                return s.from_km + frac * s.length_km
            acc += sx
        return self.length_km

    def km_to_m(self, km: float) -> float:
        total_x = sum(s.z1.imag for s in self.sections)
        acc = 0.0
        for s in self.sections:
            if km <= s.to_km or s is self.sections[-1]:
                frac = (km - s.from_km) / s.length_km if s.length_km else 0.0
                return (acc + frac * s.z1.imag) / total_x
            acc += s.z1.imag
        return 1.0

    def towers_near(self, km: float, half_width_km: float) -> List[Tower]:
        return [t for t in self.towers if abs(t.chainage_km - km) <= half_width_km]

    def nearest_tower(self, km: float) -> Optional[Tower]:
        if not self.towers:
            return None
        return min(self.towers, key=lambda t: abs(t.chainage_km - km))


def uniform_line(
    line_id: str,
    name: str,
    kv: float,
    length_km: float,
    z1_per_km: complex,
    z0_per_km: complex,
    zs1_S: complex = 0j,
    zs0_S: complex = 0j,
    zs1_R: complex = 0j,
    zs0_R: complex = 0j,
    tower_span_km: float = 0.35,
) -> Line:
    """Single-section line, for tests and synthetics."""
    sec = LineSection(
        seq=1,
        from_km=0.0,
        to_km=length_km,
        r1=z1_per_km.real,
        x1=z1_per_km.imag,
        r0=z0_per_km.real,
        x0=z0_per_km.imag,
    )
    n = int(length_km / tower_span_km) + 1
    towers = [Tower(number=str(i + 1), chainage_km=i * tower_span_km) for i in range(n)]
    return Line(
        id=line_id,
        name=name,
        kv=kv,
        sections=[sec],
        towers=towers,
        terminals={
            "S": Terminal(end="S", substation="S", zs1=zs1_S, zs0=zs0_S),
            "R": Terminal(end="R", substation="R", zs1=zs1_R, zs0=zs0_R),
        },
    )
