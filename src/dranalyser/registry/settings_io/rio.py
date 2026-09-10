"""Importer for Siemens/OMICRON .rio protection-settings files.

Settings arrive WITH the disturbance record. On the corpus this project was
built from, the relay exports a .rio next to every DR, carrying the complete
distance characteristic: zone reaches, polygon vertices, line angle, the
residual-compensation ratios and the source impedance.

That matters more than it sounds. The brief assumes settings reach the
registry through a workbook filled in by substation engineers, which is the
longest-lead-time item in the whole project. Wherever a .rio exists, most of
that sheet fills itself, and it fills itself with what the relay is ACTUALLY
running rather than with what someone believes it is running.

This is one importer among several. Everything it produces is the
vendor-neutral `ProtectionSettings` of `registry/settings.py`; nothing outside
this package may name a vendor-specific type.

Polygon vertices are (R, X) pairs in secondary ohm. A START vertex opens the
outline, LINE vertices continue it, CLOSE returns to START.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import re
from typing import Dict, List, Optional

from ..settings import (DISABLED_SENTINEL, SENTINEL_TOL, BackupStage,
                        PolygonChar, ProtectionSettings, Provenance,
                        SettingsError, Zone)

NUM = r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?"

FORMAT = "rio"
EXTENSIONS = (".rio",)


class RioError(SettingsError):
    pass


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


def confidence(text: str, path: str = "") -> float:
    """How sure this importer is that the file is its own format.

    Sniffing is by content, never by extension alone: a .txt exported from
    the same tool is still a RIO, and a .rio that is really an XML is not.
    """
    up = text[:4000].upper()
    score = 0.0
    if re.search(r"^\s*DEVICE\b", up, re.M):
        score += 0.5
    if "TRIPCHAR" in up:
        score += 0.3
    if re.search(r"^\s*RATING\b", up, re.M):
        score += 0.1
    if re.search(r"^\s*LINEANGLE\b", up, re.M):
        score += 0.1
    if path.lower().endswith(EXTENSIONS) and score > 0:
        score += 0.05
    return min(score, 1.0)


def parse_rio(text: str, source_path: str = "") -> ProtectionSettings:
    raw_text = text.replace("\x00", "").replace("\r", "")
    lines = [ln.rstrip() for ln in raw_text.splitlines()]
    s = ProtectionSettings(
        vendor="Siemens", model="SIPROTEC",
        provenance=Provenance(
            path=source_path, fmt=FORMAT, importer=__name__,
            sha256=hashlib.sha256(text.encode("latin-1", "replace")).hexdigest(),
            parsed_at=_dt.datetime.now().isoformat(timespec="seconds")))

    zone: Optional[Zone] = None
    char: Optional[PolygonChar] = None
    saw_device = False
    re_rl: Optional[float] = None
    xe_xl: Optional[float] = None
    seen: Dict[str, object] = {}
    timed_zones = set()
    parsed_angle = False

    for ln in lines:
        t = ln.strip()
        if not t:
            continue
        up = _key(t)
        head = up.split(" ")[0]
        if head and head not in seen:
            parts = t.split(None, 1)
            seen[head] = parts[1].strip() if len(parts) > 1 else ""

        if up.startswith("DEVICE"):
            s.device = t.split(None, 1)[1].strip() if len(t.split(None, 1)) > 1 else ""
            saw_device = True
        elif up.startswith("SUBSTATION"):
            s.substation = t.split(None, 1)[1].strip() if len(t.split(None, 1)) > 1 else ""
        elif up.startswith("FEEDER"):
            s.feeder = t.split(None, 1)[1].strip() if len(t.split(None, 1)) > 1 else ""
            s.line_hint = s.feeder
        elif up.startswith("RATING"):
            v = _nums(t)
            if len(v) >= 3:
                s.vt_secondary_v, s.ct_secondary_a, s.frequency = v[0], v[1], v[2]
        elif up.startswith("LINEANGLE"):
            v = _nums(t)
            if v:
                s.line_angle_deg = v[0]
                parsed_angle = True
        elif up.startswith("RE/RL"):
            v = _nums(t)
            if v:
                re_rl = v[0]
        elif up.startswith("XE/XL"):
            v = _nums(t)
            if v:
                xe_xl = v[0]
        elif up.startswith("ZS"):
            v = _nums(t)
            if len(v) >= 2:
                s.zs_secondary = complex(v[0], v[1])
        elif up.startswith("DIRCHAR"):
            v = _nums(t)
            if len(v) >= 2:
                s.dirchar_deg = (v[0], v[1])
        elif head in ("I>>", "I>", "IE>>", "IE>", "3I0>>", "3I0>"):
            v = _nums(t)
            if v:
                enabled = abs(v[0] - DISABLED_SENTINEL) > SENTINEL_TOL
                s.backup.append(BackupStage(
                    id=head, kind="ef" if head.startswith(("IE", "3I0")) else "oc",
                    pickup_secondary_a=v[0], enabled=enabled,
                    time_s=v[1] if len(v) > 1 else None))
        elif up.startswith("IMPCORR"):
            s.impedance_correction = "TRUE" in up
        elif up.startswith("BEGIN ZONE"):
            zone = Zone(name="", overreach="OVERREACH" in up)
        elif up.startswith("END ZONE"):
            if zone is not None:
                if not zone.name:
                    zone.name = "Z" + str(len(s.zones) + 1)
                s.zones.append(zone)
                if id(zone) not in timed_zones:
                    s.unknown.append('zone.' + zone.name + '.time1')
            zone, char = None, None
        elif zone is not None and up.startswith("NAME"):
            parts = t.split(None, 1)
            zone.name = parts[1].strip() if len(parts) > 1 else ""
        elif zone is not None and up.startswith("TIME1"):
            v = _nums(t)
            if v:
                zone.t1 = v[0]
                timed_zones.add(id(zone))
        elif zone is not None and up.startswith("TIMEM"):
            v = _nums(t)
            if v:
                zone.tm = v[0]
        elif up.startswith("BEGIN TRIPCHAR-EARTH"):
            char = PolygonChar(kind="earth")
        elif up.startswith("BEGIN TRIPCHAR"):
            char = PolygonChar(kind="phase")
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
    if not parsed_angle:
        s.unknown.append('line_angle_deg')

    s.raw = seen
    s.scheme = "PUTT" if s.zone("Z1B") else "STEP"
    if re_rl is not None and xe_xl is not None:
        s.k0_convention = "siemens_re_xe"
        s.k0_params = {"re_rl": re_rl, "xe_xl": xe_xl}
    else:
        s.unknown.append("k0")
        s.provenance.warnings.append(
            "no RE/RL and XE/XL in the file; k0 cannot be derived and must "
            "come from the settings sheet")
    if not s.zones:
        s.unknown.append("zones")
        s.provenance.warnings.append("no zones parsed from the RIO file")
    return s


def read_rio(path: str) -> ProtectionSettings:
    with open(path, "r", encoding="latin-1") as fh:
        return parse_rio(fh.read(), source_path=path)


# The importer contract the registry in settings_io/__init__.py expects.
load = read_rio
