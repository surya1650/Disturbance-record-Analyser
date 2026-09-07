"""Vendor-neutral protection settings -- what the analyser consumes.

Nothing outside `registry/settings_io/` may name a vendor-specific settings
type. A Siemens `.rio` is one importer among several; the fleet is mixed, and
before this module `RioSettings` was imported directly by the back-test, the
report renderer, the rules engine and the CLI, so a second vendor could not be
added without touching all four. `scripts/check_architecture.py` enforces the
rule now.

Units
-----
Everything here is SECONDARY ohm, referred to the rating line (VT secondary
volts, CT secondary amps, frequency). Converting to primary is

    Z_primary = Z_secondary * (VT_ratio / CT_ratio)

and getting that ratio upside down is a factor of 6.25 on this fleet, so the
conversion lives in one place and is never open-coded by a caller.

Characteristics
---------------
`Characteristic` is an interface, not a polygon. Siemens draws polygons, ABB
and SEL draw mho circles, and a quadrilateral is a polygon with a tilted
reactance line. Baking the polygon in would have put the Siemens assumption
one layer deeper than the importer.
"""
from __future__ import annotations

import cmath
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .model import (RelaySetting, k0_from_impedances, k0_from_kn,
                    k0_from_sel, k0_from_siemens)


class SettingsError(Exception):
    pass


# SIPROTEC writes 2^31/100 for a stage that is not set. A stage carrying it is
# disabled, not set to 21 MA, and reporting it as a threshold would be absurd
# in one direction and dangerous in the other.
DISABLED_SENTINEL = 21474836.47
SENTINEL_TOL = 0.05


@dataclass
class Provenance:
    """Where a settings object came from. A settings file is evidence."""

    path: str = ""
    fmt: str = ""                 # "rio", "scl", "sel-txt", ...
    importer: str = ""
    sha256: str = ""
    parsed_at: str = ""
    warnings: List[str] = field(default_factory=list)


@dataclass
class BackupStage:
    """A backup overcurrent or earth-fault stage.

    A distance relay carries definite-time backup overcurrent and earth-fault
    elements behind the distance zones, graded to let distance clear first.
    They are protection in their own right: if one of them cleared the fault,
    the distance scheme did not, and that is a finding.

    Most exports carry the PICKUP but not the time delay -- delays live in the
    relay parameter set, so they come from the registry YAML. A stage with no
    known delay is still worth reporting on; it just cannot be graded.
    """

    id: str                       # "I>>", "I>", "IE>>", "IE>"
    kind: str                     # "oc" | "ef"
    pickup_secondary_a: float
    enabled: bool = True
    time_s: Optional[float] = None
    directional: Optional[bool] = None

    def pickup_primary_a(self, ct_ratio: float) -> float:
        return self.pickup_secondary_a * ct_ratio

    def describe(self, ct_ratio: float = 1.0) -> str:
        if not self.enabled:
            return self.id + " not set (disabled)"
        s = self.id + " " + format(self.pickup_secondary_a, ".3f") + " A sec"
        if ct_ratio and ct_ratio != 1.0:
            s += " = " + format(self.pickup_primary_a(ct_ratio), ".0f") + " A pri"
        s += ", t = " + (format(self.time_s, ".3f") + " s" if self.time_s is not None
                         else "not in the settings export")
        return s


class Characteristic:
    """One tripping characteristic, in secondary ohm.

    Implementations must answer `contains`, which is the only question the
    zone decision actually asks, plus the reach quantities the report draws.
    """

    kind: str = "phase"           # "phase" | "earth"

    def contains(self, z: complex) -> bool:
        raise NotImplementedError

    @property
    def reach_x(self) -> float:
        raise NotImplementedError

    @property
    def reach_r(self) -> float:
        raise NotImplementedError

    def reach_at_angle(self, line_angle_deg: float) -> complex:
        raise NotImplementedError

    def centroid(self) -> Tuple[float, float]:
        raise NotImplementedError

    def outline(self, n: int = 48) -> List[Tuple[float, float]]:
        """(R, X) points for drawing. A curve is sampled; a polygon is exact."""
        raise NotImplementedError


@dataclass
class PolygonChar(Characteristic):
    """A tripping polygon, as (R, X) vertices. Siemens and most quad relays."""

    kind: str = "phase"
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

    def outline(self, n: int = 48) -> List[Tuple[float, float]]:
        return list(self.vertices)


@dataclass
class MhoChar(Characteristic):
    """A self-polarised mho circle: through the origin, diameter `diameter`.

    ABB and SEL state a reach and a characteristic (torque) angle, which is
    the diameter as a phasor. The circle passes through the origin, so the
    centre is at half the diameter and the radius is half its magnitude.

    The maths is standard, not inferred from any file: for a circle through
    the origin with diameter D at angle theta, a ray leaving the origin at
    angle a leaves the circle at |D|*cos(a - theta).
    """

    kind: str = "phase"
    diameter: complex = 0j

    @property
    def centre(self) -> complex:
        return self.diameter / 2.0

    @property
    def radius(self) -> float:
        return abs(self.diameter) / 2.0

    @property
    def reach_x(self) -> float:
        return self.centre.imag + self.radius

    @property
    def reach_r(self) -> float:
        return self.centre.real + self.radius

    def reach_at_angle(self, line_angle_deg: float) -> complex:
        a = math.radians(line_angle_deg)
        theta = cmath.phase(self.diameter) if self.diameter else 0.0
        mag = abs(self.diameter) * math.cos(a - theta)
        if mag <= 0:
            return 0j
        return cmath.rect(mag, a)

    def centroid(self) -> Tuple[float, float]:
        return (self.centre.real, self.centre.imag)

    def contains(self, z: complex) -> bool:
        if self.radius <= 0:
            return False
        return abs(z - self.centre) <= self.radius

    def outline(self, n: int = 48) -> List[Tuple[float, float]]:
        c, r = self.centre, self.radius
        return [(c.real + r * math.cos(2 * math.pi * i / n),
                 c.imag + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def quad_char(reach_x: float, r_right: float, r_left: float,
              tilt_deg: float = 0.0, kind: str = "phase") -> PolygonChar:
    """A quadrilateral, as the polygon it is.

    Deliberately a builder returning `PolygonChar` rather than a third
    geometry: a quad IS a polygon, and `contains` for it is the same
    ray-casting test. Inventing separate maths would add a way to be wrong
    without adding a capability.

    `tilt_deg` droops the reactance line, positive downwards to the right,
    which is how a quad avoids overreach on a resistive fault.
    """
    t = math.tan(math.radians(tilt_deg))
    return PolygonChar(kind=kind, vertices=[
        (-r_left, 0.0),
        (r_right, 0.0),
        (r_right, reach_x - r_right * t),
        (-r_left, reach_x + r_left * t),
    ])


@dataclass
class Zone:
    name: str
    t1: float = 0.0
    tm: float = 0.0
    overreach: bool = False
    phase: Optional[Characteristic] = None
    earth: Optional[Characteristic] = None

    def characteristic(self, ground: bool) -> Optional[Characteristic]:
        return (self.earth or self.phase) if ground else (self.phase or self.earth)

    @property
    def reverse(self) -> bool:
        """True for a reverse-looking zone.

        Tested on the centroid rather than on the reactive reach: a reverse
        zone can still reach above the R axis (the real Z5 here reaches +0.725
        while sitting mostly at -0.910), so a max-X test would call it forward.
        """
        c = self.phase or self.earth
        if c is None:
            return False
        try:
            return c.centroid()[1] < 0.0
        except (NotImplementedError, IndexError):
            return False


@dataclass
class ProtectionSettings:
    """What one relay is actually running, as the analyser needs it."""

    device: str = ""
    vendor: str = ""
    model: str = ""
    substation: str = ""
    feeder: str = ""
    line_hint: str = ""
    vt_secondary_v: float = 110.0
    ct_secondary_a: float = 1.0
    frequency: float = 50.0
    line_angle_deg: float = 80.0

    # k0 is NEVER a typed-in number. The importer records the vendor's native
    # convention and its parameters; the conversion lives in registry/model.py
    # and is shared with the line registry.
    k0_convention: str = ""
    k0_params: Dict[str, float] = field(default_factory=dict)

    zs_secondary: complex = 0j
    dirchar_deg: Tuple[float, float] = (0.0, 0.0)
    impedance_correction: bool = False
    zones: List[Zone] = field(default_factory=list)
    backup: List[BackupStage] = field(default_factory=list)
    scheme: str = ""

    provenance: Provenance = field(default_factory=Provenance)
    # Everything the importer saw, untouched. A settings file is evidence:
    # what was not understood stays visible rather than being dropped.
    raw: Dict[str, object] = field(default_factory=dict)
    # Fields the importer could not determine, so consumers can treat them as
    # unavailable -- the same discipline the rules engine uses with `requires`.
    unknown: List[str] = field(default_factory=list)

    # ---- Siemens-native ratios, read-only conveniences -------------------
    @property
    def re_rl(self) -> Optional[float]:
        return self.k0_params.get("re_rl")

    @property
    def xe_xl(self) -> Optional[float]:
        return self.k0_params.get("xe_xl")

    @property
    def source_path(self) -> str:
        return self.provenance.path

    @property
    def warnings(self) -> List[str]:
        return self.provenance.warnings

    # ---- lookups --------------------------------------------------------
    def zone(self, name: str) -> Optional[Zone]:
        n = name.strip().upper()
        for z in self.zones:
            if z.name.strip().upper() == n:
                return z
        return None

    def stage(self, stage_id: str) -> Optional[BackupStage]:
        for b in self.backup:
            if b.id == stage_id:
                return b
        return None

    @property
    def enabled_backup(self) -> List[BackupStage]:
        return [b for b in self.backup if b.enabled]

    @property
    def forward_zones(self) -> List[Zone]:
        return [z for z in self.zones if not z.reverse]

    # ---- units ----------------------------------------------------------
    def secondary_to_primary(self, ct_ratio: float, vt_ratio: float) -> float:
        if ct_ratio <= 0:
            raise SettingsError("ct_ratio must be positive")
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
        """Complex residual compensation, from the vendor's native form."""
        p, conv = self.k0_params, self.k0_convention
        try:
            if conv == "siemens_re_xe":
                return k0_from_siemens(p["re_rl"], p["xe_xl"],
                                       p.get("line_angle_deg", self.line_angle_deg))
            if conv == "abb_kn":
                return k0_from_kn(p["kn_mag"], p["kn_ang_deg"])
            if conv == "sel_k0":
                return k0_from_sel(p["k0m"], p["k0a_deg"])
            if conv == "impedances":
                return k0_from_impedances(complex(p["r1"], p["x1"]),
                                          complex(p["r0"], p["x0"]))
            if conv == "complex_k0":
                return complex(p["k0_real"], p["k0_imag"])
        except KeyError:
            return None
        return None

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
                   ground: bool = False) -> Optional[Zone]:
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
        """Build a registry RelaySetting from the settings export.

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
        params = dict(self.k0_params)
        conv = self.k0_convention or "complex_k0"
        if conv == "siemens_re_xe":
            params.setdefault("line_angle_deg", self.line_angle_deg)

        rs = RelaySetting(
            effective_from=effective_from,
            scheme=self.scheme or ("PUTT" if self.zone("Z1B") else "STEP"),
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
        head = (self.vendor + " " + self.model).strip() or self.provenance.fmt.upper()
        rows = [(head + " settings  " + self.device + "  "
                 + self.substation.strip()).strip(),
                "  rating           : " + format(self.vt_secondary_v, ".1f") + " V, "
                + format(self.ct_secondary_a, ".1f") + " A, "
                + format(self.frequency, ".0f") + " Hz (secondary)",
                "  line angle       : " + format(self.line_angle_deg, ".1f") + " deg"]
        k0 = self.k0()
        if k0 is not None:
            native = ", ".join(k + "=" + format(v, ".3f")
                               for k, v in sorted(self.k0_params.items()))
            rows.append("  k0 (" + self.k0_convention + ")  : " + native
                        + "  ->  " + format(abs(k0), ".4f") + " angle "
                        + format(math.degrees(cmath.phase(k0)), "+.3f") + " deg")
        rows.append("  source Z (sec)   : " + format(self.zs_secondary.real, ".3f")
                    + " + j" + format(self.zs_secondary.imag, ".3f"))
        if self.backup:
            rows.append("  backup stages    :")
            for b in self.backup:
                rows.append("     " + b.describe())
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
        if self.unknown:
            rows.append("  not determined   : " + ", ".join(sorted(self.unknown)))
        return "\n".join(rows)
