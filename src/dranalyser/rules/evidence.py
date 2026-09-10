"""Per-relay observations, retaining raw points and independent time bases.

No Boolean 'did not operate' is inferred from missing records or points. No
cross-record alignment or causal ordering is inferred from two trigger zeros.
"""
from __future__ import annotations

import numpy as np

from ..dsp.measurements import phase_measurements, relative_ms, trigger_reference
from ..dsp.clock_quality import clock_quality
from .signals import CANONICAL, map_signals
from .stages import stage_evidence

TRIP_SIGNALS = ("TRIP", "TRIP_A", "TRIP_B", "TRIP_C", "TRIP_3P", "TRIP_Z2", "TRIP_Z3", "TRIP_Z4",
                "OC_TRIP", "EF_TRIP", "DEFINITIVE_TRIP")


def point_observation(rec, name, trigger):
    values = np.asarray(rec.digital[name])
    base = {"channel": name, "state": "insufficient samples", "initially_active": False,
            "assertions_ms": [], "assertions_s": [], "intervals": []}
    if values.size != rec.n or values.size < 2 or not np.all(np.isin(values, [0, 1])):
        return base
    values = values.astype(bool)
    rises = np.flatnonzero(np.diff(values.astype(int)) == 1)+1
    base.update(state="assertion observed" if rises.size else
                "active at capture start" if values[0] else "no assertion observed",
                initially_active=bool(values[0]),
                assertions_s=[float(rec.t[i]) for i in rises],
                assertions_ms=[relative_ms(float(rec.t[i]), trigger) for i in rises])
    on = 0 if values[0] else None
    for i in range(1, values.size):
        if values[i] and not values[i-1]:
            on = i
        elif not values[i] and values[i-1]:
            base["intervals"].append(_interval(rec, on, i, trigger, on == 0, False))
            on = None
    if on is not None:
        base["intervals"].append(_interval(rec, on, rec.n-1, trigger, on == 0, True))
    return base


def _interval(rec, start, end, trigger, open_start, open_end):
    return {"start_s": float(rec.t[start]), "end_s": float(rec.t[end]),
            "start_ms": relative_ms(float(rec.t[start]), trigger),
            "end_ms": relative_ms(float(rec.t[end]), trigger),
            "onset_unknown": open_start, "continues_at_capture_end": open_end}


def relay_evidence(an, file_name="", end="", role="", relay_id="", protection_system="unknown"):
    rec = an.record
    trigger, time_note = trigger_reference(rec)
    onset = float(an.inception.t_refined) if an.inception is not None else None
    sm = map_signals(list(rec.digital), rec.notes.get('digital_overrides'))
    signals = []
    for canonical in CANONICAL:
        points = [point_observation(rec, name, trigger) for name in sm.channels(canonical)]
        # Different raw points mapped to the same meaning need review; preserve
        # them all instead of choosing a shorter name as proof of operation.
        review = len(points) > 1 and any(not np.array_equal(rec.digital[p["channel"]],
                                                          rec.digital[points[0]["channel"]]) for p in points[1:])
        states = {p["state"] for p in points}
        state = ("mapping review required" if review else "assertion observed" if "assertion observed" in states
                 else "active at capture start" if "active at capture start" in states
                 else "insufficient samples" if "insufficient samples" in states
                 else "no assertion observed" if points else "not recorded / unmapped")
        signals.append({"signal": canonical, "state": state, "points": points})
    trips = [s for s in signals if s["signal"] in TRIP_SIGNALS and s["points"]]
    states = {s["state"] for s in trips}
    trip_state = ("mapping review required" if "mapping review required" in states else
                  "assertion observed" if "assertion observed" in states else
                  "active at capture start" if "active at capture start" in states else
                  "insufficient samples" if "insufficient samples" in states else
                  "no assertion observed" if trips else "not recorded / unmapped")
    # A pre-existing active trip does not supply a new onset or operating time.
    rises = sorted(t for s in trips for p in s["points"] for t in p["assertions_s"]
                   if onset is not None and t >= onset)
    already_active = any(p["initially_active"] for s in trips for p in s["points"])
    operate = (relative_ms(rises[0], onset) if rises and not already_active
               and trip_state != "mapping review required" else None)
    return {"file": file_name or rec.record_id, "end": end or rec.terminal_end, "role": role,
            "relay_id": relay_id or "unknown", "protection_system": protection_system,
            "device_id": rec.device_id, "station": rec.station, "status": "analysed",
            "record_hash": rec.content_hash, "fault_type": an.fault_type,
            'clock_quality': clock_quality(rec), 'stages': stage_evidence(an, signals, trigger),
            'channel_mapping': rec.notes.get('channel_mapping', {}),
            'channel_inventory': rec.notes.get('channel_inventory', []),
            "trigger_time": rec.trigger_time.isoformat() if rec.trigger_time else None,
            "start_time": rec.start_time.isoformat() if rec.start_time else None,
            "trigger_offset_s": trigger, "time_note": time_note,
            "digital_time_resolution_ms": 1000/rec.fs if rec.fs > 0 else None,
            "inception_local_s": onset, "inception_trigger_ms": relative_ms(onset, trigger),
            "trip_state": trip_state, "operate_ms": operate,
            "operate_basis": "first observed trip edge after detected inception; local record only",
            "measurements": phase_measurements(an), "signals": signals,
            "unmapped_digital": sm.unmapped, "ignored_digital": sm.ignored,
            "flags": [str(f) for f in rec.flags], "ct_saturation": an.saturation.detected,
            "clipped_channels": list(an.clipping),
            "caveat": "Observations cover this recording only. A trip command does not prove breaker opening."}


def terminal_evidence(records):
    out = []
    for end in ("S", "R"):
        rows = [r for r in records if r.get("end") == end]
        usable = [r for r in rows if r.get("status") == "analysed"]
        states = sorted({r["trip_state"] for r in usable})
        out.append({"end": end, "records": len(rows), "analysed": len(usable), "trip_states": states,
                    "summary": "record unavailable; operation unknown" if not rows else
                    "no usable record; operation unknown" if not usable else
                    "trip observations differ between relays; review evidence" if len(states) > 1 else states[0]})
    return out
