"""Feature extraction for the conclusions engine.

Produces one flat dictionary per incident. Rules are written against these
names and nothing else, so a protection engineer adding a rule never has to
know how a phasor is estimated or how a vendor spells a channel.

Two conventions that matter:

  * every time is milliseconds FROM FAULT INCEPTION at that terminal, not
    from the start of the record and not from the relay's own clock. The
    clocks in this fleet disagree by up to 1418 s, so anything referenced to
    them is meaningless across terminals.

  * a signal that was never mapped produces <name>_mapped = False, and the
    value is None rather than False. A rule that tests "carrier sent but not
    received" must be able to tell "the carrier did not arrive" from "this
    relay has no carrier channel wired to the recorder", because the first is
    a teleprotection defect and the second is a recording defect, and
    reporting either as the other destroys trust.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from ..dsp.pipeline import Analysed
from ..dsp.measurements import phase_measurements
from ..faultloc.ensemble import LocationResult
from ..registry.model import Line
from ..registry.settings import ProtectionSettings
from .signals import SignalMap, infer_zone_operated, map_signals

MS = 1000.0


def _ms(t: Optional[float], t0: float) -> Optional[float]:
    return None if t is None else (t - t0) * MS


def _phase_interruption(an: Analysed, t_inception: float) -> Dict[str, Optional[float]]:
    """Per-pole current-zero time, measured from the waveform.

    Auxiliary contacts report the mechanism; the current tells you when the
    arc actually went out, and that is what breaker timing is judged on.

    The threshold is a fraction of each phase's OWN level over the fault
    window, and the collapse must persist half a cycle. See the comment at
    the threshold for why an absolute threshold cannot work.
    """
    rec = an.record
    n = max(int(round(rec.fs / an.freq)), 4)
    out: Dict[str, Optional[float]] = {}
    i0 = int(np.searchsorted(rec.t, t_inception))
    for ph in "ABC":
        x = rec.analog.get("I" + ph)
        if x is None:
            out[ph] = None
            continue
        env = np.convolve(np.abs(np.asarray(x, float)), np.ones(n) / n, mode="same")
        peak = float(np.max(env[i0: i0 + 8 * n])) if i0 + n < env.size else 0.0
        if peak <= 0:
            out[ph] = None
            continue
        # Referred to this phase's own level over the fault window, because
        # an interrupted pole does not go to zero: capacitive coupling from
        # the healthy phases leaves a residual that decays over hundreds of
        # milliseconds. On the real record phase A drops from 5609 A to 109 A
        # at interruption and is still at 62 A 120 ms later, so any absolute
        # threshold either misses the interruption or finds it far too late.
        thr = 0.10 * peak
        below = env[i0 + n:] < thr
        if not below.any():
            out[ph] = None
            continue
        # require the collapse to persist half a cycle, so a current zero in
        # normal flow is not mistaken for an interruption
        need = max(n // 2, 2)
        run = 0
        idx = None
        for k in range(below.size):
            run = run + 1 if below[k] else 0
            if run >= need:
                idx = k - need + 1
                break
        out[ph] = float(rec.t[i0 + n + idx]) if idx is not None else None
    return out


def _restrike(an: Analysed, t_open: Optional[float]) -> bool:
    """Current reappearing after interruption: interrupter degradation."""
    if t_open is None:
        return False
    rec = an.record
    n = max(int(round(rec.fs / an.freq)), 4)
    i = int(np.searchsorted(rec.t, t_open))
    for ph in "ABC":
        x = rec.analog.get("I" + ph)
        if x is None:
            continue
        x = np.abs(np.asarray(x, float))
        pre = float(np.max(x[max(0, i - 4 * n): i])) if i > n else 0.0
        after = x[i + n // 2: i + 4 * n]
        if pre > 0 and after.size and float(np.max(after)) > 0.15 * pre:
            return True
    return False


@dataclass
class TerminalFeatures:
    end: str
    available: bool = True
    signals: Optional[SignalMap] = None
    values: Dict[str, Any] = field(default_factory=dict)

    def prefixed(self) -> Dict[str, Any]:
        return {self.end + "_" + k: v for k, v in self.values.items()}


def terminal_features(
    an: Analysed, end: str, settings: Optional[ProtectionSettings] = None,
    ct_ratio: float = 1.0, vt_ratio: float = 1.0, z2_time_s: float = 0.35,
) -> TerminalFeatures:
    rec = an.record
    sm = map_signals(list(rec.digital), rec.notes.get('digital_overrides'))
    t0 = float(an.notes.get("inception_t", 0.0))

    def first(*canon: str) -> Optional[float]:
        chans: List[str] = []
        for c in canon:
            chans.extend(sm.channels(c))
        return rec.first_assert(*chans) if chans else None

    trip_t = first("TRIP", "TRIP_A", "TRIP_B", "TRIP_C", "TRIP_3P")
    start_t = first("START")
    asserts = {k: first(k) for k in ("TRIP_Z2", "TRIP_Z3", "TRIP_Z4")}
    operate = None if trip_t is None else trip_t - t0

    # Single-pole against three-pole tripping. Pole-to-pole timing is only
    # meaningful when all three poles were commanded together; on a
    # single-pole trip the healthy poles open later because they were
    # commanded later, which is correct behaviour and not a discrepancy.
    phase_trips = [first("TRIP_" + p) for p in "ABC"]
    got = [t for t in phase_trips if t is not None]
    three_pole = first("TRIP_3P") is not None or (
        len(got) == 3 and (max(got) - min(got)) * MS <= 5.0)
    single_pole = (not three_pole) and len(got) == 1

    zeros = _phase_interruption(an, t0)
    open_times = [v for v in zeros.values() if v is not None]
    t_open = min(open_times) if open_times else an.t_open
    # Pole discrepancy compares poles that opened in the SAME operation. A
    # single-pole trip followed 80 ms later by a three-phase definitive trip
    # is two operations, and differencing across them invents a half-second
    # discrepancy on a healthy breaker.
    disc = None
    if three_pole and len(open_times) > 1:
        same_op = [t for t in open_times if (t - min(open_times)) * MS <= 100.0]
        if len(same_op) > 1:
            disc = (max(same_op) - min(same_op)) * MS

    # Backup overcurrent and earth fault sit behind the distance zones on a
    # definite-time delay. They are protection in their own right: if one of
    # them cleared the fault then the distance scheme did not, and if one
    # operated at or before the distance trip the grading is wrong.
    oc_pu, oc_tr = first("OC_PICKUP"), first("OC_TRIP")
    ef_pu, ef_tr = first("EF_PICKUP"), first("EF_TRIP")
    backup_trips = [t for t in (oc_tr, ef_tr) if t is not None]
    backup_trip = min(backup_trips) if backup_trips else None

    cs, cr = first("CARRIER_SEND"), first("CARRIER_RECV")
    ar_close = first("AR_CLOSE")
    dead = None
    if ar_close is not None and t_open is not None and ar_close > t_open:
        dead = (ar_close - t_open) * MS

    zapp = None
    if settings is not None and an.indices().size:
        i = int(an.indices()[an.indices().size // 2])
        k0 = settings.k0() or 0j
        va = an.phasor("VA", i)
        ia = an.phasor("IA", i)
        i0 = an.phasor("I0", i)
        loop = ia + k0 * 3.0 * i0
        if abs(loop) > 1e-9:
            zapp = (va / loop) * settings.secondary_to_primary(ct_ratio, vt_ratio) ** -1

    v: Dict[str, Any] = {
        "available": True,
        "fault_type": an.fault_type,
        "freq_hz": an.freq,
        "inception_ms": 0.0,
        "start_ms": _ms(start_t, t0),
        "trip_ms": _ms(trip_t, t0),
        "open_ms": _ms(t_open, t0),
        "operate_ms": None if operate is None else operate * MS,
        "breaker_ms": (None if (trip_t is None or t_open is None)
                       else (t_open - trip_t) * MS),
        "clear_ms": _ms(t_open, t0),
        "zone_operated": infer_zone_operated(asserts, operate, z2_time_s),
        "carrier_send": cs is not None,
        "carrier_send_ms": _ms(cs, t0),
        "carrier_send_mapped": sm.has("CARRIER_SEND"),
        "carrier_recv": cr is not None,
        "carrier_recv_ms": _ms(cr, t0),
        "carrier_recv_mapped": sm.has("CARRIER_RECV"),
        "carrier_fail": first("CARRIER_FAIL") is not None,
        "pole_open_a_ms": _ms(zeros.get("A"), t0),
        "pole_open_b_ms": _ms(zeros.get("B"), t0),
        "pole_open_c_ms": _ms(zeros.get("C"), t0),
        "pole_discrepancy_ms": disc,
        "poles_opened": len(open_times),
        "three_pole_trip": three_pole,
        "single_pole_trip": single_pole,
        "restrike": _restrike(an, t_open),
        "ar_close_ms": _ms(ar_close, t0),
        "ar_lockout": first("AR_LOCKOUT") is not None,
        "ar_block": first("AR_BLOCK") is not None,
        "ar_in_progress": first("AR_IN_PROGRESS") is not None,
        "dead_time_ms": dead,
        "definitive_trip": first("DEFINITIVE_TRIP") is not None,
        "lockout_86": first("LOCKOUT_86") is not None,
        "vt_fail": first("VT_FAIL") is not None,
        "sotf": first("SOTF") is not None,
        "power_swing": first("POWER_SWING") is not None,
        "zone_rev": first("ZONE_REV") is not None,
        "ct_saturation": an.saturation.detected,
        "ct_saturation_channels": ",".join(an.saturation.channels),
        "zero_seq_voltage": an.zero_seq_voltage,
        "window_cycles": an.window.cycles,
        "window_mode": an.window.mode,
        "i2_ratio": float(an.fault_diag.get("r2", 0.0)),
        "i0_ratio": float(an.fault_diag.get("r0", 0.0)),
        "flags": [f.code for f in rec.flags],
        "blocked": rec.blocked(),
        "signals_mapped": len(sm.candidates),
        "signals_unmapped": len(sm.unmapped),
    }

    measured = phase_measurements(an)
    currents = [r for r in measured["channels"] if r["channel"] in ("IA", "IB", "IC")
                and r["status"] == "measured"]
    rms = max((r["rms"] for r in currents), default=None)
    v["i_fault_peak_a"] = max((r["peak_abs"] for r in currents), default=None)
    v["i_fault_ka"] = rms / 1000.0 if rms is not None else None
    v["i_fault_measurement"] = "maximum phase sample RMS in selected fault window"
    v["measurement_window"] = measured["window"]

    # ---- backup overcurrent / earth fault -------------------------------
    v["oc_pickup"] = oc_pu is not None
    v["oc_pickup_ms"] = _ms(oc_pu, t0)
    v["oc_trip"] = oc_tr is not None
    v["oc_trip_ms"] = _ms(oc_tr, t0)
    v["oc_mapped"] = sm.has("OC_TRIP") or sm.has("OC_PICKUP")
    v["ef_pickup"] = ef_pu is not None
    v["ef_pickup_ms"] = _ms(ef_pu, t0)
    v["ef_trip"] = ef_tr is not None
    v["ef_trip_ms"] = _ms(ef_tr, t0)
    v["ef_mapped"] = sm.has("EF_TRIP") or sm.has("EF_PICKUP")
    v["backup_operated"] = backup_trip is not None
    v["backup_trip_ms"] = _ms(backup_trip, t0)
    v["backup_picked_up"] = (oc_pu is not None) or (ef_pu is not None)
    v["backup_grading_ms"] = (None if (backup_trip is None or trip_t is None)
                              else (backup_trip - trip_t) * MS)
    v["backup_before_distance"] = (backup_trip is not None and trip_t is not None
                                   and backup_trip <= trip_t)

    # settings, where the relay export carried them
    v["oc_setting_a"] = None
    v["ef_setting_a"] = None
    v["oc_setting_time_s"] = None
    v["ef_setting_time_s"] = None
    v["oc_stage_disabled"] = None
    v["ef_stage_disabled"] = None
    v["backup_settings_known"] = False
    v["i_fault_over_oc_setting"] = None
    if settings is not None and settings.backup:
        v["backup_settings_known"] = True
        for st in settings.backup:
            k = "oc" if st.kind == "oc" else "ef"
            if v[k + "_setting_a"] is None or (st.enabled and not v[k + "_stage_disabled"]):
                v[k + "_setting_a"] = (st.pickup_primary_a(ct_ratio) if st.enabled else None)
                v[k + "_setting_time_s"] = st.time_s
                v[k + "_stage_disabled"] = not st.enabled
        if v["oc_setting_a"] and rms is not None:
            v["i_fault_over_oc_setting"] = rms / v["oc_setting_a"]

    # These exist whether or not settings were supplied: a rule that names a
    # feature which is merely unavailable must evaluate to False, while a rule
    # that names a feature which does not exist at all must be an error.
    v["z_app_r_sec"] = None
    v["z_app_x_sec"] = None
    v["zone_expected"] = None
    if zapp is not None:
        v["z_app_r_sec"] = zapp.real
        v["z_app_x_sec"] = zapp.imag
        if settings is not None:
            ground = an.fault_type in ("AG", "BG", "CG")
            z = settings.which_zone(zapp, ground=ground)
            v["zone_expected"] = z.name if z else "beyond_all_zones"
    return TerminalFeatures(end=end, signals=sm, values=v)


def incident_features(
    terminals: Dict[str, Analysed],
    location: Optional[LocationResult] = None,
    line: Optional[Line] = None,
    settings: Optional[Dict[str, ProtectionSettings]] = None,
    z2_time_s: float = 0.35,
) -> Dict[str, Any]:
    """One flat feature dictionary for the whole incident."""
    settings = settings or {}
    out: Dict[str, Any] = {}
    tf: Dict[str, TerminalFeatures] = {}
    for end, an in sorted(terminals.items()):
        term = line.terminals.get(end) if line else None
        f = terminal_features(
            an, end, settings.get(end),
            ct_ratio=term.it.ct_ratio if term else 1.0,
            vt_ratio=term.it.vt_ratio if term else 1.0,
            z2_time_s=z2_time_s,
        )
        tf[end] = f
        out.update(f.prefixed())

    # An absent terminal gets the full key set filled with None rather than no
    # keys at all. A missing key is an error in a rule condition, and it must
    # stay one -- that is what catches a typo -- so absence is represented as
    # a present-but-unknown value, which comparisons already treat as False.
    keys = set()
    for f in tf.values():
        keys |= set(f.values)
    for end in ("S", "R"):
        if end in tf:
            continue
        for k in keys:
            out[end + "_" + k] = None
        out[end + "_available"] = False

    out["n_terminals"] = len(tf)
    out["two_ended"] = len(tf) >= 2
    kinds = {f.values["fault_type"] for f in tf.values()}
    out["fault_type"] = sorted(kinds)[0] if kinds else "NONE"
    out["fault_type_agreed"] = len(kinds) <= 1
    out["is_ground_fault"] = out["fault_type"] in ("AG", "BG", "CG", "ABG", "BCG", "CAG")
    out["is_three_phase"] = out["fault_type"] in ("ABC", "ABCG")

    clears = [f.values["clear_ms"] for f in tf.values() if f.values.get("clear_ms")]
    out["clear_asymmetry_ms"] = (max(clears) - min(clears)) if len(clears) > 1 else None
    out["slowest_clear_ms"] = max(clears) if clears else None

    if location is not None and location.ok:
        out["location_available"] = True
        out["m"] = location.m
        out["km_from_S"] = location.km_from_S
        out["km_from_R"] = location.km_from_R
        out["location_mode"] = location.mode
        out["location_method"] = location.method
        out["method_disagreement_pu"] = float(
            location.diagnostics.get("method_disagreement_pu", 0.0))
        out["tower"] = location.likely_tower.number if location.likely_tower else None
    else:
        out["location_available"] = False
        out["m"] = None
        out["location_mode"] = "none"

    if line is not None:
        out["line_id"] = line.id
        out["line_km"] = line.length_km
        out["line_kv"] = line.kv
        out["series_compensated"] = line.series_compensated
    return out
