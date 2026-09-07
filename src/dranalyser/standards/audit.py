"""Audits derived from the standards in ``standard docs/``.

The source files are summarized in ``project-docs/STANDARDS_CONTEXT.md``.
This module deliberately distinguishes a proven gap from a setting that the
available export cannot expose.  A missing input therefore becomes
``not_evaluable`` rather than a pass or an invented failure.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence

from ..registry.model import Line
from ..registry.settings import ProtectionSettings
from ..rules.signals import map_signals
from ..signals import PHASE_CURRENTS, PHASE_VOLTAGES, Record

FOLD = "FOLD Working Group 3 report (2023)"
APTRANSCO_2014 = "APTRANSCO general distance-protection philosophy"
APTRANSCO_2024 = "APTRANSCO revised distance-relay settings (27 Nov 2024)"
LOAD_SHEET = "Load encroachment Calculations.xlsx"

STATUSES = ("pass", "gap", "not_evaluable")


@dataclass(frozen=True)
class StandardCheck:
    id: str
    title: str
    status: str
    expected: str
    actual: str
    source: str
    action: str = ""

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError("unknown standard-check status " + repr(self.status))

    def __str__(self) -> str:
        label = {"pass": "PASS", "gap": "GAP", "not_evaluable": "NOT EVALUABLE"}[
            self.status
        ]
        text = "[" + label + " " + self.id + "] " + self.title
        if self.actual:
            text += ": " + self.actual
        if self.status != "pass" and self.expected:
            text += " (expected " + self.expected + ")"
        return text


@dataclass
class AuditResult:
    checks: List[StandardCheck] = field(default_factory=list)

    @property
    def gaps(self) -> List[StandardCheck]:
        return [c for c in self.checks if c.status == "gap"]

    @property
    def not_evaluable(self) -> List[StandardCheck]:
        return [c for c in self.checks if c.status == "not_evaluable"]

    @property
    def passes(self) -> List[StandardCheck]:
        return [c for c in self.checks if c.status == "pass"]

    @property
    def status(self) -> str:
        return "GAP" if self.gaps else ("INCOMPLETE" if self.not_evaluable else "PASS")

    def extend(self, checks: Iterable[StandardCheck]) -> None:
        self.checks.extend(checks)

    def report(self, indent: str = "  ") -> str:
        rows = [
            indent + "STANDARD AUDIT: " + self.status + " ("
            + str(len(self.passes)) + " pass, " + str(len(self.gaps)) + " gap, "
            + str(len(self.not_evaluable)) + " not evaluable)"
        ]
        rows.extend(indent + "  " + str(c) for c in self.checks)
        return "\n".join(rows)


def _check(
    check_id: str,
    title: str,
    ok: Optional[bool],
    expected: str,
    actual: str,
    source: str,
    action: str = "",
) -> StandardCheck:
    status = "not_evaluable" if ok is None else ("pass" if ok else "gap")
    return StandardCheck(check_id, title, status, expected, actual, source, action)


def _has_any(mapped, names: Sequence[str]) -> bool:
    return any(mapped.has(name) for name in names)


def _mutual_current_recorded(rec: Record) -> bool:
    raw = [m.raw_id for m in rec.analog_meta.values()]
    raw.extend(str(x) for x in (rec.notes.get("unmapped_channels") or []))
    return any(re.search(r"\bMUT(?:UAL)?\b|\bI\s*M\b|MUTUAL.*COMP", name, re.I)
               for name in raw)


def audit_record(rec: Record, line: Optional[Line] = None) -> AuditResult:
    """Check whether one COMTRADE record contains the WG-3 minimum evidence."""
    result = AuditResult()
    result.checks.append(_check(
        "DR-SAMPLE", "Sampling frequency", rec.fs >= 1000.0,
        ">= 1000 Hz", format(rec.fs, ".1f") + " Hz", FOLD + ", pages 12-14",
        "Increase the relay DR sampling rate where the model permits it.",
    ))

    trigger = rec.trigger_offset_s()
    pre_ok = None if trigger is None else trigger >= 0.500 - 1e-6
    result.checks.append(_check(
        "DR-PRE", "Pre-trigger capture", pre_ok, ">= 500 ms",
        "trigger time unavailable" if trigger is None else format(trigger * 1000.0, ".1f") + " ms",
        FOLD + ", pages 15-16",
        "Set the disturbance-record pre-trigger window to at least 500 ms.",
    ))

    post = None if trigger is None or rec.n < 2 else float(rec.t[-1] - trigger)
    post_ok = None if post is None else post >= 2.500 - 1e-6
    result.checks.append(_check(
        "DR-POST", "Post-trigger capture", post_ok, ">= 2500 ms",
        "trigger time unavailable" if post is None else format(post * 1000.0, ".1f") + " ms",
        FOLD + ", pages 15-16",
        "Set the disturbance-record post-trigger window to at least 2500 ms.",
    ))

    expected_analog = list(PHASE_CURRENTS + PHASE_VOLTAGES) + ["IN", "VN"]
    missing_analog = [name for name in expected_analog if name not in rec.analog]
    result.checks.append(_check(
        "DR-ANALOG", "Line-protection analog channels", not missing_analog,
        "IA, IB, IC, IN, VA, VB, VC and VN",
        "complete" if not missing_analog else "missing " + ", ".join(missing_analog),
        FOLD + ", tables 4, 10 and 11 (pages 28-32)",
        "Configure the missing neutral or phase quantities in the relay DR.",
    ))

    mapped = map_signals(list(rec.digital))
    groups = (
        ("protection start", ("START", "Z1", "Z2", "Z3", "Z4")),
        ("protection trip", ("TRIP", "TRIP_A", "TRIP_B", "TRIP_C", "TRIP_3P",
                             "TRIP_Z2", "TRIP_Z3", "TRIP_Z4")),
        ("zone indication", ("Z1", "Z2", "Z3", "Z4", "TRIP_Z2", "TRIP_Z3", "TRIP_Z4")),
        ("breaker position", ("CB_OPEN_A", "CB_OPEN_B", "CB_OPEN_C",
                              "ANY_POLE_DEAD", "ALL_POLE_DEAD")),
        ("auto-reclose", ("AR_INITIATE", "AR_IN_PROGRESS", "AR_CLOSE", "AR_BLOCK", "AR_FAIL")),
        ("carrier", ("CARRIER_SEND", "CARRIER_RECV", "CARRIER_FAIL")),
        ("VT supervision", ("VT_FAIL",)),
        ("relay health", ("RELAY_FAIL",)),
        ("time synchronization", ("TIME_SYNC_FAIL",)),
        ("LAN health", ("LAN_FAIL",)),
    )
    missing_groups = [label for label, names in groups if not _has_any(mapped, names)]
    result.checks.append(_check(
        "DR-DIGITAL", "Line-protection digital evidence", not missing_groups,
        "start, trip, zone, breaker, AR, carrier, VT, relay, time-sync and LAN status",
        "complete" if not missing_groups else "missing " + ", ".join(missing_groups),
        FOLD + ", tables 5, 6, 8, 9 and 11 (pages 28-32)",
        "Add the missing status signals to the relay disturbance recorder.",
    ))

    if line is not None and line.double_circuit:
        result.checks.append(_check(
            "DR-MUTUAL-I", "Mutual-compensation current channel",
            _mutual_current_recorded(rec), "IM recorded for a parallel line",
            "recorded" if _mutual_current_recorded(rec) else "not found",
            FOLD + ", tables 4 and 10; " + APTRANSCO_2024 + ", page 5",
            "Record the mutual current and confirm physical CT-neutral compensation.",
        ))
    return result


def load_encroachment_min_ohm(
    kv: float,
    thermal_rating_mva: float,
    line_angle_deg: float,
    *,
    bay_rating_mva: Optional[float] = None,
    min_voltage_pu: float = 0.85,
    emergency_factor: float = 1.5,
    load_angle_deg: float = 30.0,
) -> float:
    """Primary phase-phase RLD reach from the supplied calculation workbook."""
    if kv <= 0 or thermal_rating_mva <= 0:
        raise ValueError("kv and thermal_rating_mva must be positive")
    rating = min(thermal_rating_mva, bay_rating_mva) if bay_rating_mva else thermal_rating_mva
    z_load = ((min_voltage_pu * kv) ** 2 * math.cos(math.radians(load_angle_deg))
              / (emergency_factor * rating))
    denominator = math.cos(math.radians(90.0 - line_angle_deg))
    if abs(denominator) < 1e-9:
        raise ValueError("line angle makes the load-encroachment safety factor singular")
    safety = math.cos(math.radians(load_angle_deg + 90.0 - line_angle_deg)) / denominator
    return z_load * safety


def audit_settings(
    settings: Optional[ProtectionSettings],
    line: Optional[Line] = None,
    *,
    terminal_end: str = "S",
    configured_load_reach_primary_ohm: Optional[float] = None,
    thermal_rating_mva: Optional[float] = None,
    bay_rating_mva: Optional[float] = None,
) -> AuditResult:
    """Audit settings exposed by a RIO file, without treating omissions as passes."""
    result = AuditResult()
    if settings is None:
        result.checks.append(_check(
            "SETTINGS-EXPORT", "Relay settings evidence", None, "RIO or equivalent export",
            "not supplied", APTRANSCO_2014 + " and " + APTRANSCO_2024,
            "Supply the settings export that was effective at the event time.",
        ))
        return result

    terminal = line.terminals.get(terminal_end) if line is not None else None
    ct = terminal.it.ct_ratio if terminal else None
    vt = terminal.it.vt_ratio if terminal else None
    z1 = settings.zone("Z1")
    if line is None or ct is None or vt is None or z1 is None:
        result.checks.append(_check(
            "SET-Z1", "Zone 1 reach", None, "80% of protected-line Z1",
            "line, instrument ratios or Z1 characteristic unavailable", APTRANSCO_2014,
        ))
    else:
        actual_z1 = settings.zone_reach_primary("Z1", ct, vt)
        expected = 0.80 * line.z1
        err = None if actual_z1 is None or abs(expected) == 0 else abs(actual_z1) / abs(expected) - 1.0
        result.checks.append(_check(
            "SET-Z1", "Zone 1 reach", None if err is None else abs(err) <= 0.05,
            format(abs(expected), ".3f") + " primary ohm (80% of line Z1)",
            "unavailable" if actual_z1 is None else format(abs(actual_z1), ".3f")
            + " primary ohm (" + format(err * 100.0, "+.1f") + "%)",
            APTRANSCO_2014,
            "Review the Z1 reach, line impedance and CT/VT ratios.",
        ))

    for name, minimum, source in (("Z2", 0.35, APTRANSCO_2024 + ", pages 1-2"),
                                  ("Z3", 0.70, APTRANSCO_2024 + ", pages 1-2")):
        zone = settings.zone(name)
        result.checks.append(_check(
            "SET-" + name + "-TIME", name + " time delay",
            None if zone is None else zone.t1 >= minimum - 1e-6,
            ">= " + format(minimum, ".2f") + " s",
            "zone not present" if zone is None else format(zone.t1, ".3f") + " s",
            source, "Review time grading against adjacent protection.",
        ))

    reverse = [z for z in settings.zones if z.reverse]
    reverse_zone = min(reverse, key=lambda z: abs(z.t1 - 0.35)) if reverse else None
    result.checks.append(_check(
        "SET-REVERSE", "Reverse-zone direction and delay",
        False if reverse_zone is None else abs(reverse_zone.t1 - 0.35) <= 0.03,
        "reverse-looking zone at 0.35 s",
        "no reverse zone" if reverse_zone is None else reverse_zone.name + " at "
        + format(reverse_zone.t1, ".3f") + " s",
        APTRANSCO_2024 + ", pages 1-2",
        "Configure the reverse reach for local-bus backup and verify its direction.",
    ))

    k0 = settings.k0()
    result.checks.append(_check(
        "SET-K0", "Zero-sequence compensation evidence", None if k0 is None else True,
        "enabled with the relay-native compensation values",
        "not exposed by export" if k0 is None else format(abs(k0), ".4f") + " at "
        + format(math.degrees(math.atan2(k0.imag, k0.real)), "+.2f") + " deg",
        APTRANSCO_2014,
        "Confirm the native k0/KN/RE-RL/XE-XL values rather than copying a magnitude alone.",
    ))

    if thermal_rating_mva is None or line is None:
        result.checks.append(_check(
            "SET-RLD", "Load-encroachment reach", None,
            "workbook formula using minimum voltage and emergency loading",
            "line voltage or thermal rating unavailable", LOAD_SHEET + " and "
            + APTRANSCO_2024 + ", page 4",
        ))
    else:
        target = load_encroachment_min_ohm(
            line.kv, thermal_rating_mva, settings.line_angle_deg,
            bay_rating_mva=bay_rating_mva,
        )
        err = (None if configured_load_reach_primary_ohm is None else
               configured_load_reach_primary_ohm / target - 1.0)
        result.checks.append(_check(
            "SET-RLD", "Load-encroachment reach", None if err is None else abs(err) <= 0.05,
            format(target, ".2f") + " primary ohm",
            "configured reach not supplied" if err is None else
            format(configured_load_reach_primary_ohm, ".2f") + " primary ohm ("
            + format(err * 100.0, "+.1f") + "%)",
            LOAD_SHEET + " and " + APTRANSCO_2024 + ", page 4",
            "Use the lower of conductor and bay thermal ratings and verify CT/VT conversion.",
        ))
    return result
