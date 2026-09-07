"""Reader for Siemens/OMICRON .rio protection-settings files.

Settings arrive WITH the disturbance record. On the corpus this project was
built from, the relay exports a .rio next to every DR, carrying the complete
distance characteristic: zone reaches, polygon vertices, line angle, the
residual-compensation ratios and the source impedance.

That matters more than it sounds. The brief assumes settings reach the
registry through a workbook filled in by substation engineers, which is the
longest-lead-time item in the whole project. Wherever a .rio exists, most of
that sheet fills itself, and it fills itself with what the relay is ACTUALLY
running rather than with what someone believes it is running.

Units
-----
Everything in the file is SECONDARY ohm, referred to the RATING line
(VT secondary volts, CT secondary amps, frequency). Converting to primary is

    Z_primary = Z_secondary * (VT_ratio / CT_ratio)

and getting that ratio upside down is a factor of 6.25 on this corpus, so the
conversion lives here and is never open-coded by a caller.

Polygon vertices are (R, X) pairs. A START vertex opens the outline, LINE
vertices continue it, CLOSE returns to START.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .model import RelaySetting, k0_from_siemens

NUM = r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?"


class RioError(Exception):
    pass


@dataclass
class ZoneCharacteristic:
    """One tripping polygon, in secondary ohm, as (R, X) vertices."""

    kind: str                       # "phase" | "earth"
    vertices: List[Tuple[float, float]] = field(default_factory=list)

    @property
    def reach_x(self) -> float:
        """Reactive reach: the top of the polygon."""
        return max((x for _, x in self.vertices), default=0.0)

    @property
    def reach_r(self) -> float:
        return max((r for r, _ in self.vertices), default=0.0)

    def reach_at_angle(self, line_angle_deg: float) -> complex:
        """Reach along the line angle, which is what the setting means.

        The polygon carries a vertex on the line angle itself (on the real
        corpus Z1 has (0.554, 3.500) against an 81 degree line, and
        3.500/tan(81) = 0.554 exactly). Deriving it from the reactive reach
        rather than trusting vertex order works for any polygon shape.
        """
        x = self.reach_x
        a = math.radians(line_angle_deg)
        if math.sin(a) <= 0:
            return complex(0.0, x)
        return complex(x / math.tan(a), x)

    def centroid(self) -> Tuple[float, float]:
        """Area centroid of the closed polygon (shoelace)."""
        p = self.vertices
        n = len(p)
        if n < 3:
            return (0.0, 0.0)
        a = cr = cx = 0.0
        for i in range(n):
            r1, x1 = p[i]
            r2, x2 = p[(i + 1) % n]
            cross = r1 * x2 - r2 * x1
            a += cross
            cr += (r1 + r2) * cross
            cx += (x1 + x2) * cross
        if abs(a) < 1e-12:
            return (sum(r for r, _ in p) / n, sum(x for _, x in p) / n)
        return (cr / (3.0 * a), cx / (3.0 * a))

    def contains(self, z: complex) -> bool:
        """Ray-casting point-in-polygon for an apparent impedance."""
        pts = self.vertices
        if len(pts) < 3:
            return False
        r, x = z.real, z.imag
        inside = False
        n = len(pts)
        for i in range(n):
            r1, x1 = pts[i]
            r2, x2 = pts[(i + 1) % n]
            if (x1 > x) != (x2 > x):
                t = (x - x1) / (x2 - x1) if x2 != x1 else 0.0
                if r < r1 + t * (r2 - r1):
                    inside = not inside
        return inside


@dataclass
class RioZone:
    name: str
    t1: float = 0.0
    tm: float = 0.0
    overreach: bool = False
    phase: Optional[ZoneCharacteristic] = None
    earth: Optional[ZoneCharacteristic] = None

    def characteristic(self, ground: bool) -> Optional[ZoneCharacteristic]:
        return (self.earth or self.phase) if ground else (self.phase or self.earth)

    @property
    def reverse(self) -> bool:
        """True for a reverse-looking zone.

        Tested on the polygon centroid rather than on the reactive reach: a
        reverse zone can still have a vertex above the R axis (the real Z5
        here reaches +0.725 while sitting mostly at -0.910), so a max-X test
        would call it forward.
        """
        c = self.phase or self.earth
        if c is None or len(c.vertices) < 3:
            return False
        return c.centroid()[1] < 0.0


@dataclass
class RioSettings:
    device: str = ""
    substation: str = ""
    feeder: str = ""
    vt_secondary_v: float = 110.0
    ct_secondary_a: float = 1.0
    frequency: float = 50.0
    line_angle_deg: float = 80.0
    re_rl: Optional[float] = None
    xe_xl: Optional[float] = None
    zs_secondary: complex = 0j
    dirchar_deg: Tuple[float, float] = (0.0, 0.0)
    impedance_correction: bool = False
    zones: List[RioZone] = field(default_factory=list)
    source_path: str = ""
    warnings: List[str] = field(default_factory=list)

    # ---- lookups --------------------------------------------------------
    def zone(self, name: str) -> Optional[RioZone]:
        n = name.strip().upper()
        for z in self.zones:
            if z.name.strip().upper() == n:
                return z
        return None

    @property
    def forward_zones(self) -> List[RioZone]:
        return [z for z in self.zones if not z.reverse]

    # ---- units ----------------------------------------------------------
    def secondary_to_primary(self, ct_ratio: float, vt_ratio: float) -> float:
        if ct_ratio <= 0:
            raise RioError("ct_ratio must be positive")
        return vt_ratio / ct_ratio

    def zone_reach_primary(self, name: str, ct_ratio: float, vt_ratio: float,
                           ground: bool = False) -> Optional[complex]:
        z = self.zone(name)
        if z is None:
            return None
        c = z.characteristic(ground)
        if c is None:
            return None
        return c.reach_at_angle(self.line_angle_deg) * self.secondary_to_primary(
            ct_ratio, vt_ratio)

    # ---- derived protection quantities ----------------------------------
    def k0(self) -> Optional[complex]:
        """Complex residual compensation from the two real SIPROTEC ratios."""
        if self.re_rl is None or self.xe_xl is None:
            return None
        return k0_from_siemens(self.re_rl, self.xe_xl, self.line_angle_deg)

    def implied_line_z1(self, ct_ratio: float, vt_ratio: float,
                        z1_reach_fraction: float = 0.80) -> Optional[complex]:
        """Line Z1 implied by the Zone 1 setting.

        NOT a survey. It assumes Zone 1 is set to the stated fraction of the
        line, which is the usual 80 % but must be confirmed. It is still far
        better than a guessed value, because it is consistent by construction
        with the zone the relay actually operated in.
        """
        reach = self.zone_reach_primary("Z1", ct_ratio, vt_ratio)
        if reach is None or z1_reach_fraction <= 0:
            return None
        return reach / z1_reach_fraction

    def implied_line_z0(self, ct_ratio: float, vt_ratio: float,
                        z1_reach_fraction: float = 0.80) -> Optional[complex]:
        z1 = self.implied_line_z1(ct_ratio, vt_ratio, z1_reach_fraction)
        k0 = self.k0()
        if z1 is None or k0 is None:
            return None
        return z1 * (1.0 + 3.0 * k0)

    def which_zone(self, z_apparent_secondary: complex,
                   ground: bool = False) -> Optional[RioZone]:
        """The fastest forward zone whose characteristic contains the point.

        This is what makes the relay's own trip decision usable as ground
        truth: the analyser computes the apparent impedance, this says which
        zone should have operated, and the record's digital channels say which
        one did.
        """
        cands = [z for z in self.forward_zones
                 if (c := z.characteristic(ground)) is not None and c.contains(
                     z_apparent_secondary)]
        if not cands:
            return None
        return min(cands, key=lambda z: (z.t1, z.characteristic(ground).reach_x))

    # ---- registry bridge -------------------------------------------------
    def to_relay_setting(self, ct_ratio: float, vt_ratio: float,
                         line_z1_primary: Optional[complex] = None,
                         effective_from: str = "") -> RelaySetting:
        """Build a registry RelaySetting from the file.

        Reaches are expressed per unit of line when the line impedance is
        known, and left as ohms otherwise. k0 is carried in the vendor's
        native form so that the registry derives it rather than storing a
        hand-typed number.
        """
        k = self.secondary_to_primary(ct_ratio, vt_ratio)

        def pu(name: str) -> Optional[float]:
            r = self.zone_reach_primary(name, ct_ratio, vt_ratio)
            if r is None or line_z1_primary is None or abs(line_z1_primary) == 0:
                return None
            return abs(r) / abs(line_z1_primary)

        z2 = self.zone("Z2")
        z3 = self.zone("Z3")
        params: Dict[str, float] = {}
        conv = "complex_k0"
        if self.re_rl is not None and self.xe_xl is not None:
            conv = "siemens_re_xe"
            params = {"re_rl": self.re_rl, "xe_xl": self.xe_xl,
                      "line_angle_deg": self.line_angle_deg}

        rs = RelaySetting(
            effective_from=effective_from,
            scheme="PUTT" if self.zone("Z1B") else "STEP",
            z1_reach_pu=pu("Z1") if pu("Z1") is not None else 0.8,
            z2_reach_pu=pu("Z2") if pu("Z2") is not None else 1.2,
            z3_reach_pu=pu("Z3") if pu("Z3") is not None else 2.0,
            z2_time_s=z2.t1 if z2 else 0.35,
            z3_time_s=z3.t1 if z3 else 0.8,
            line_angle_deg=self.line_angle_deg,
            k0_convention=conv,
            k0_params=params,
        )
        rs.reach_ohm_primary = {
            z.name: self.zone_reach_primary(z.name, ct_ratio, vt_ratio)
            for z in self.zones
        }
        rs.secondary_to_primary = k
        return rs

    def summary(self) -> str:
        rows = ["RIO settings  " + self.device + "  " + self.substation.strip(),
                "  rating           : " + format(self.vt_secondary_v, ".1f") + " V, "
                + format(self.ct_secondary_a, ".1f") + " A, "
                + format(self.frequency, ".0f") + " Hz (secondary)",
                "  line angle       : " + format(self.line_angle_deg, ".1f") + " deg"]
        if self.re_rl is not None:
            k0 = self.k0()
            rows.append("  RE/RL, XE/XL     : " + format(self.re_rl, ".3f") + ", "
                        + format(self.xe_xl, ".3f") + "  ->  k0 = "
                        + format(abs(k0), ".4f") + " angle "
                        + format(math.degrees(math.atan2(k0.imag, k0.real)), "+.3f") + " deg")
        rows.append("  source Z (sec)   : " + format(self.zs_secondary.real, ".3f")
                    + " + j" + format(self.zs_secondary.imag, ".3f"))
        rows.append("  zones            :")
        for z in self.zones:
            c = z.phase or z.earth
            rows.append("     " + format(z.name, "<5")
                        + ("overreach " if z.overreach else "")
                        + ("REVERSE " if z.reverse else "")
                        + "t=" + format(z.t1, ".3f") + " s   X reach "
                        + format(c.reach_x if c else 0.0, "7.3f") + " sec ohm"
                        + ("   (earth X " + format(z.earth.reach_x, ".3f") + ")"
                           if z.earth else ""))
        return "\n".join(rows)


# --------------------------------------------------------------------------
# parsing
# --------------------------------------------------------------------------
def _nums(line: str) -> List[float]:
    """Numbers in the VALUE part of a line, not in its keyword.

    The keyword itself can contain digits: "TIME1  0.000" would otherwise
    yield 1.0 as the first number and every zone would read as a one-second
    zone. So the first whitespace-delimited token is dropped first.
    """
    parts = line.strip().split(None, 1)
    return [float(x) for x in re.findall(NUM, parts[1])] if len(parts) > 1 else []


def _key(line: str) -> str:
    """Upper-cased line with runs of whitespace collapsed.

    The real file writes "BEGIN      TRIPCHAR" with padding but
    "BEGIN TRIPCHAR-EARTH" with one space. Matching on the raw text drops the
    phase polygon silently and leaves the earth polygon standing in for it,
    which is invisible on this corpus for the reactive reach (they are equal)
    and badly wrong for the resistive extent (6.034 against 18.034 on Z1).
    """
    return re.sub(r"\s+", " ", line.strip().upper())


def parse_rio(text: str, source_path: str = "") -> RioSettings:
    raw = text.replace("\x00", "").replace("\r", "")
    lines = [ln.rstrip() for ln in raw.splitlines()]
    s = RioSettings(source_path=source_path)

    zone: Optional[RioZone] = None
    char: Optional[ZoneCharacteristic] = None
    saw_device = False

    for ln in lines:
        t = ln.strip()
        if not t:
            continue
        up = _key(t)

        if up.startswith("DEVICE"):
            s.device = t.split(None, 1)[1].strip() if len(t.split(None, 1)) > 1 else ""
            saw_device = True
        elif up.startswith("SUBSTATION"):
            s.substation = t.split(None, 1)[1].strip() if len(t.split(None, 1)) > 1 else ""
        elif up.startswith("FEEDER"):
            s.feeder = t.split(None, 1)[1].strip() if len(t.split(None, 1)) > 1 else ""
        elif up.startswith("RATING"):
            v = _nums(t)
            if len(v) >= 3:
                s.vt_secondary_v, s.ct_secondary_a, s.frequency = v[0], v[1], v[2]
        elif up.startswith("LINEANGLE"):
            v = _nums(t)
            if v:
                s.line_angle_deg = v[0]
        elif up.startswith("RE/RL"):
            v = _nums(t)
            if v:
                s.re_rl = v[0]
        elif up.startswith("XE/XL"):
            v = _nums(t)
            if v:
                s.xe_xl = v[0]
        elif up.startswith("ZS"):
            v = _nums(t)
            if len(v) >= 2:
                s.zs_secondary = complex(v[0], v[1])
        elif up.startswith("DIRCHAR"):
            v = _nums(t)
            if len(v) >= 2:
                s.dirchar_deg = (v[0], v[1])
        elif up.startswith("IMPCORR"):
            s.impedance_correction = "TRUE" in up
        elif up.startswith("BEGIN ZONE"):
            zone = RioZone(name="", overreach="OVERREACH" in up)
        elif up.startswith("END ZONE"):
            if zone is not None:
                if not zone.name:
                    zone.name = "Z" + str(len(s.zones) + 1)
                s.zones.append(zone)
            zone, char = None, None
        elif zone is not None and up.startswith("NAME"):
            parts = t.split(None, 1)
            zone.name = parts[1].strip() if len(parts) > 1 else ""
        elif zone is not None and up.startswith("TIME1"):
            v = _nums(t)
            if v:
                zone.t1 = v[0]
        elif zone is not None and up.startswith("TIMEM"):
            v = _nums(t)
            if v:
                zone.tm = v[0]
        elif up.startswith("BEGIN TRIPCHAR-EARTH"):
            char = ZoneCharacteristic(kind="earth")
        elif up.startswith("BEGIN TRIPCHAR"):
            char = ZoneCharacteristic(kind="phase")
        elif up.startswith("END TRIPCHAR-EARTH"):
            if zone is not None and char is not None:
                zone.earth = char
            char = None
        elif up.startswith("END TRIPCHAR"):
            if zone is not None and char is not None:
                zone.phase = char
            char = None
        elif char is not None and (up.startswith("START") or up.startswith("LINE")):
            v = _nums(t)
            if len(v) >= 2:
                char.vertices.append((v[0], v[1]))
        elif char is not None and up.startswith("CLOSE"):
            pass

    if not saw_device:
        raise RioError("not a RIO file: no DEVICE line found")
    if not s.zones:
        s.warnings.append("no zones parsed from the RIO file")
    if s.re_rl is None or s.xe_xl is None:
        s.warnings.append("no RE/RL and XE/XL in the file; k0 cannot be derived "
                          "and must come from the settings sheet")
    return s


def read_rio(path: str) -> RioSettings:
    with open(path, "r", encoding="latin-1") as fh:
        return parse_rio(fh.read(), source_path=path)
