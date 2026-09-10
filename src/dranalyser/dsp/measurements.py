"""Windowed sample measurements; no inferred CT/VT corrections.

Sample RMS includes DC and harmonics. Fundamental RMS is the median magnitude
of eligible DFT phasors. Neither quantity is derived from the waveform peak.
"""
from __future__ import annotations

import math

import numpy as np


def trigger_reference(rec):
    offset = rec.trigger_offset_s()
    if offset is None or not math.isfinite(offset):
        return None, "trigger timestamp unavailable"
    if not rec.n or not rec.t[0] <= offset <= rec.t[-1]:
        return None, "trigger timestamp outside captured interval"
    return float(offset), "record trigger = 0 ms; independent local time reference"


def relative_ms(t, reference):
    return None if t is None or reference is None else float((t-reference)*1000)


def phase_measurements(an):
    """Measure [window start, window end) on native samples, by phase/channel.

    Do not substitute a whole-record maximum when no fault window is usable.
    Sample RMS is explicitly sample-weighted, including on multi-rate records.
    """
    rec = an.record
    trigger, _ = trigger_reference(rec)
    start, end = float(an.window.t_start), float(an.window.t_end)
    eligible = (an.inception is not None and an.window.mode != "none"
                and math.isfinite(start) and math.isfinite(end) and end > start)
    idx = np.flatnonzero((rec.t >= start) & (rec.t < end)) if eligible else np.array([], dtype=int)
    pidx = an.indices() if eligible else np.array([], dtype=int)
    window = {"start_s": start if math.isfinite(start) else None,
              "end_s": end if math.isfinite(end) else None,
              "start_trigger_ms": relative_ms(start, trigger) if math.isfinite(start) else None,
              "end_trigger_ms": relative_ms(end, trigger) if math.isfinite(end) else None,
              "sample_count": int(idx.size), "mode": an.window.mode,
              "basis": "selected fault window [start, end); native sample-weighted RMS"}
    channels = []
    for name in ("IA", "IB", "IC", "VA", "VB", "VC", "IN", "VN"):
        meta = rec.analog_meta.get(name)
        row = {"channel": name, "phase": {"A": "R", "B": "Y", "C": "B"}.get(name[-1], "neutral"),
               "source_channel": meta.raw_id if meta else name,
               "unit": "A primary" if name.startswith("I") else "V primary",
               "declared_unit": meta.unit if meta else None,
               "declared_ps": meta.ps if meta else None,
               "primary_ratio": meta.primary if meta else None,
               "secondary_ratio": meta.secondary if meta else None,
               "rms": None, "fundamental_rms": None, "peak_abs": None,
               "peak_trigger_ms": None, "peak_local_s": None,
               "samples": 0, "status": "not recorded"}
        values = rec.analog.get(name)
        if values is not None:
            row["status"] = "no usable fault window"
            if idx.size >= 2 and len(values) == rec.n:
                x = np.asarray(values, dtype=float)[idx]
                row["samples"] = int(x.size)
                row["status"] = "non-finite samples" if not np.all(np.isfinite(x)) else "measured"
                if row["status"] == "measured":
                    peak = int(np.argmax(np.abs(x)))
                    amplitude = float(abs(x[peak]))
                    # Scale before squaring to avoid overflow on otherwise finite input.
                    row.update(rms=amplitude*float(np.sqrt(np.mean((x/amplitude)**2))) if amplitude else 0.0,
                               peak_abs=amplitude, peak_local_s=float(rec.t[idx[peak]]),
                               peak_trigger_ms=relative_ms(float(rec.t[idx[peak]]), trigger))
                    phasors = an.ps.phasors.get(name)
                    if phasors is not None and pidx.size:
                        mag = np.abs(np.asarray(phasors)[pidx])
                        if np.all(np.isfinite(mag)):
                            row["fundamental_rms"] = float(np.median(mag))
        channels.append(row)
    return {"window": window, "channels": channels}
