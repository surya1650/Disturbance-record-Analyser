"""Canonical in-memory representation of one disturbance record.

Both the COMTRADE parser and the synthetic generator produce this, so every
downstream stage is exercised identically by real and synthetic data.

Units are ALWAYS primary volts and primary amps by the time a Record exists.
Ratio and P/S normalisation happens in the parser, never downstream.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np

# Canonical analog channel names. Everything vendor-specific is mapped to
# these at ingest; nothing downstream may look at a raw vendor channel id.
ANALOG_CANON = ("IA", "IB", "IC", "IN", "VA", "VB", "VC", "VN")
PHASE_CURRENTS = ("IA", "IB", "IC")
PHASE_VOLTAGES = ("VA", "VB", "VC")

SEVERITIES = ("info", "flag", "block")


@dataclass
class Flag:
    """One conformance / quality finding attached to a record.

    A block flag stops the record reaching fault location. A flag is carried
    through to the report as a caveat. Nothing is ever silently repaired.
    """

    code: str
    severity: str
    message: str
    detail: Dict[str, object] = field(default_factory=dict)

    def __str__(self) -> str:
        return "[" + self.severity.upper() + " " + self.code + "] " + self.message


@dataclass
class AnalogMeta:
    raw_id: str
    unit: str
    a: float
    b: float
    primary: float
    secondary: float
    ps: str
    adc_min: float
    adc_max: float
    phase: str = ""
    # True once the parser has scaled this channel to primary units.
    normalised: bool = False


@dataclass
class Record:
    """One disturbance record from one relay."""

    record_id: str
    station: str
    device_id: str
    rev_year: str
    start_time: Optional[datetime]
    trigger_time: Optional[datetime]
    fs: float
    line_freq: float
    t: np.ndarray
    analog: Dict[str, np.ndarray]
    digital: Dict[str, np.ndarray]
    analog_meta: Dict[str, AnalogMeta] = field(default_factory=dict)
    raw_analog: Dict[str, np.ndarray] = field(default_factory=dict)
    flags: List[Flag] = field(default_factory=list)
    source_path: str = ""
    content_hash: str = ""
    # Free-running relay clocks are the norm, not the exception (a 1418 s
    # skew was measured between two relays in one bay in this repo's corpus),
    # so the time basis is recorded and never assumed.
    time_basis: str = "unknown"
    terminal_end: str = ""
    nrates: int = 1
    notes: Dict[str, object] = field(default_factory=dict)

    # ---- convenience -----------------------------------------------------
    @property
    def n(self) -> int:
        return int(self.t.size)

    @property
    def duration_s(self) -> float:
        return float(self.t[-1] - self.t[0]) if self.n > 1 else 0.0

    @property
    def samples_per_cycle(self) -> float:
        return self.fs / self.line_freq

    def has(self, *names: str) -> bool:
        return all(nm in self.analog for nm in names)

    def get(self, name: str) -> Optional[np.ndarray]:
        return self.analog.get(name)

    def blocked(self) -> bool:
        return any(f.severity == "block" for f in self.flags)

    def flag_codes(self) -> List[str]:
        return [f.code for f in self.flags]

    def add_flag(self, code: str, severity: str, message: str, **detail) -> Flag:
        if severity not in SEVERITIES:
            raise ValueError("bad severity " + repr(severity))
        f = Flag(code=code, severity=severity, message=message, detail=detail)
        self.flags.append(f)
        return f

    def trigger_offset_s(self) -> Optional[float]:
        """Seconds from record start to the trigger instant."""
        if self.start_time is None or self.trigger_time is None:
            return None
        return (self.trigger_time - self.start_time).total_seconds()

    def digital_transitions(self, name: str) -> List[tuple]:
        """[(t_seconds, new_state), ...] for one digital channel."""
        d = self.digital.get(name)
        if d is None:
            return []
        idx = np.nonzero(np.diff(d.astype(int)))[0] + 1
        return [(float(self.t[i]), int(d[i])) for i in idx]

    def first_assert(self, *names: str) -> Optional[float]:
        """Earliest time any of the named digital channels goes to 1."""
        best = None
        for nm in names:
            for tt, st in self.digital_transitions(nm):
                if st == 1 and (best is None or tt < best):
                    best = tt
        return best

    def absolute_time(self, t_rel: float) -> Optional[datetime]:
        if self.start_time is None:
            return None
        return self.start_time + timedelta(seconds=float(t_rel))

    def summary(self) -> str:
        parts = [
            self.record_id,
            self.station,
            "fs=" + format(self.fs, ".1f") + "Hz",
            format(self.samples_per_cycle, ".1f") + "smp/cyc",
            str(self.n) + "smp",
            format(self.duration_s * 1000.0, ".0f") + "ms",
        ]
        if self.flags:
            parts.append(str(len(self.flags)) + " flags")
        return "  ".join(parts)
