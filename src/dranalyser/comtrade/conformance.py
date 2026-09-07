"""Conformance gate (brief section 5.1), as a pure function over a Record.

block = the record does not proceed to fault location.
flag  = it proceeds, and the caveat is printed on the report.
info  = recorded, not shown on page 1.

Nothing is repaired. A wrong ratio is reported, never corrected; a reversed
neutral CT is reported, never flipped.

Four checks here are not in the brief and were added because the real records
in this repo demanded them:

  RATIO-PS    the P/S flag and primary/secondary ratio were actually applied.
              One relay in the corpus writes ps=P with a 1:1 ratio and the
              other ps=S with 800/1; mixing them unnoticed is an 800x error.
  ADC-CLIP    samples pegged at the CFG min/max. This is converter clipping,
              a different defect from magnetic CT saturation, and it is
              trivially detectable from fields already in the CFG.
  I-PRE-RES   pre-fault current expressed in ADC counts. On a range scaled
              for fault current, a lightly loaded line leaves the pre-fault
              current in a handful of counts (11 counts on the real Main-1
              record here), which makes every superimposed-quantity method
              unreliable while leaving negative-sequence E5 untouched.
  TIME-BASIS  whether the record states its time basis at all. With IST at
              UTC+5:30, a half-hour offset is invisible to every other check.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional

import numpy as np

from ..signals import PHASE_CURRENTS, PHASE_VOLTAGES, Flag, Record

SQRT2 = math.sqrt(2.0)
SQRT3 = math.sqrt(3.0)


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(np.asarray(x, dtype=float)))))


def _prefault_slice(rec: Record, cycles: float = 4.0, backoff_cycles: float = 2.0) -> slice:
    """Samples safely before the fault.

    The trigger instant is NOT the inception instant: a relay triggers on its
    own pickup, several milliseconds after the fault starts (6 ms on the real
    Main-1 record here). Ending the window at the trigger therefore lets
    fault samples into the pre-fault statistics and hides exactly the
    conditions this gate exists to find, so the window is backed off.
    """
    spc = rec.fs / rec.line_freq
    n = int(round(cycles * spc))
    off = rec.trigger_offset_s()
    if off is None or off <= 0:
        return slice(0, min(n, rec.n))
    i = int(np.clip(np.searchsorted(rec.t, off) - int(round(backoff_cycles * spc)),
                    1, rec.n))
    return slice(max(0, i - n), i)


def check(
    rec: Record,
    nominal_kv: Optional[float] = None,
    expect_rotation: str = "ABC",
    min_prefault_cycles: float = 2.0,
    balance_tol: float = 0.10,
    min_prefault_counts: float = 20.0,
) -> List[Flag]:
    """Run every gate check and attach the flags to the record."""
    out: List[Flag] = []

    def add(code, sev, msg, **d):
        out.append(rec.add_flag(code, sev, msg, **d))

    # --- CFG/DAT integrity -------------------------------------------------
    declared = int(rec.notes.get("declared_endsamp", 0) or 0)
    if declared and rec.n != declared:
        add("CFG-TRUNC", "block",
            "DAT holds " + str(rec.n) + " samples but the CFG declares "
            + str(declared) + " - record is truncated or padded",
            actual=rec.n, declared=declared)
    if rec.n < 2:
        add("CFG-EMPTY", "block", "record contains no usable samples")
        return out

    # --- channel identification -------------------------------------------
    missing = [c for c in (PHASE_CURRENTS + PHASE_VOLTAGES) if c not in rec.analog]
    if missing:
        add("CH-MISSING", "block",
            "required channels absent after canonical mapping: " + ", ".join(missing),
            missing=missing)
        return out
    if "IN" not in rec.analog:
        add("CH-NO-IN", "info",
            "no measured neutral current; 3I0 is reconstructed as IA+IB+IC, so "
            "the current-balance check cannot run")

    pre = _prefault_slice(rec)
    if pre.stop - pre.start < int(round(min_prefault_cycles * rec.fs / rec.line_freq)):
        add("WIN-PREFAULT", "flag",
            "under " + format(min_prefault_cycles, ".0f")
            + " cycles of pre-fault data; superimposed-quantity methods degrade")

    vrms = {c: _rms(rec.analog[c][pre]) for c in PHASE_VOLTAGES}
    irms = {c: _rms(rec.analog[c][pre]) for c in PHASE_CURRENTS}
    v_ln = float(np.mean(list(vrms.values())))
    v_ll = v_ln * SQRT3

    # --- P/S normalisation actually applied --------------------------------
    for c in PHASE_CURRENTS + PHASE_VOLTAGES:
        m = rec.analog_meta.get(c)
        if m is None:
            continue
        if m.ps == "S" and (not m.secondary or m.primary == m.secondary):
            add("RATIO-PS", "block",
                c + " is flagged secondary (ps=S) but carries no usable ratio "
                "(primary=" + format(m.primary, ".3f") + ", secondary="
                + format(m.secondary, ".3f") + "); values cannot be taken to primary",
                channel=c)

    # --- ratio sanity ------------------------------------------------------
    if nominal_kv:
        err = (v_ll / 1000.0 - nominal_kv) / nominal_kv
        if abs(err) > 0.15:
            sev = "block"
            hint = ""
            for name, factor in (("sqrt(2) - peak vs RMS", SQRT2),
                                 ("sqrt(3) - phase vs line", SQRT3),
                                 ("1/sqrt(2)", 1.0 / SQRT2),
                                 ("1/sqrt(3)", 1.0 / SQRT3)):
                if abs(v_ll / 1000.0 / factor - nominal_kv) / nominal_kv < 0.15:
                    hint = "; the discrepancy is a factor of " + name
                    break
            add("RATIO-V", sev,
                "pre-fault line voltage " + format(v_ll / 1000.0, ".1f")
                + " kV is " + format(err * 100.0, "+.1f") + " % from the nominal "
                + format(nominal_kv, ".0f") + " kV" + hint,
                measured_kv=v_ll / 1000.0, nominal_kv=nominal_kv)
        else:
            add("RATIO-V", "info",
                "pre-fault line voltage " + format(v_ll / 1000.0, ".1f")
                + " kV, " + format(err * 100.0, "+.1f") + " % of nominal",
                measured_kv=v_ll / 1000.0)

    # --- current balance / neutral CT polarity -----------------------------
    if "IN" in rec.analog:
        s = (rec.analog["IA"] + rec.analog["IB"] + rec.analog["IC"])[pre]
        inn = rec.analog["IN"][pre]
        diff, summ = _rms(s - inn), _rms(s + inn)
        ref = max(irms.values())
        if ref > 0 and min(diff, summ) / ref > balance_tol:
            add("I-BALANCE", "flag",
                "pre-fault residual does not close: |IA+IB+IC-IN| is "
                + format(diff / ref * 100.0, ".1f") + " % of phase current",
                residual_pct=diff / ref * 100.0)
        elif summ < diff:
            add("I-POLARITY", "flag",
                "neutral CT polarity appears REVERSED: |IA+IB+IC+IN| ("
                + format(summ, ".2f") + " A) is smaller than |IA+IB+IC-IN| ("
                + format(diff, ".2f") + " A). Not corrected automatically.",
                sum_rms=summ, diff_rms=diff)

    # --- phase rotation ----------------------------------------------------
    rot = _rotation(rec, pre)
    if rot and rot != expect_rotation:
        add("PH-ROTATION", "flag",
            "pre-fault phase rotation reads " + rot + ", expected "
            + expect_rotation, measured=rot)

    # --- peak vs RMS scaling ----------------------------------------------
    for c in PHASE_VOLTAGES:
        peak = float(np.max(np.abs(rec.analog[c][pre])))
        if vrms[c] <= 0:
            continue
        cf = peak / vrms[c]
        if not (1.2 < cf < 1.8):
            add("SCALE-CF", "block",
                c + " crest factor is " + format(cf, ".3f")
                + ", not the 1.414 of a sinusoid; the channel is probably "
                "stored as RMS or scaled by sqrt(2)", channel=c, crest=cf)

    # --- ADC clipping ------------------------------------------------------
    for c, raw in (rec.raw_analog or {}).items():
        m = rec.analog_meta.get(c)
        if m is None:
            continue
        x = np.asarray(raw, dtype=float)
        n_clip = int(np.sum(x >= m.adc_max * 0.999) + np.sum(x <= m.adc_min * 0.999))
        if n_clip >= 3:
            add("ADC-CLIP", "flag",
                c + " has " + str(n_clip) + " samples pegged at the converter "
                "limit; the peak is clipped and the phasor understates it",
                channel=c, n=n_clip)

    # --- pre-fault current resolution -------------------------------------
    for c in PHASE_CURRENTS:
        m = rec.analog_meta.get(c)
        if m is None or not m.a:
            continue
        counts = irms[c] / abs(m.a * (m.primary / m.secondary if m.ps == "S" and m.secondary else 1.0))
        if counts < min_prefault_counts:
            add("I-PRE-RES", "flag",
                c + " pre-fault current is only " + format(counts, ".1f")
                + " ADC counts (" + format(irms[c], ".1f") + " A on a range scaled "
                "for fault current); superimposed-quantity methods (E2, and the "
                "3-phase path of E4/E5) are unreliable. Negative-sequence E5 is "
                "unaffected.", channel=c, counts=counts)
            break

    # --- clock quality -----------------------------------------------------
    tmq = str(rec.notes.get("tmq_code", "") or "")
    if not tmq:
        add("CLK-QUALITY", "flag",
            "no clock-quality code in the record; the synchronised two-ended "
            "method E4 is gated off. E5 does not need it.")
    if rec.time_basis == "unknown":
        add("TIME-BASIS", "flag",
            "record does not state its time basis (IST / UTC / free-running); "
            "trigger timestamps cannot be compared between substations")

    return out


def _rotation(rec: Record, pre: slice) -> Optional[str]:
    """Pre-fault phase rotation from the sign of the negative sequence."""
    from ..dsp.core import sequence, sliding_dft

    n = int(round(rec.fs / rec.line_freq))
    if pre.stop - pre.start < 2 * n:
        return None
    t = rec.t[pre]
    ph = [sliding_dft(rec.analog[c][pre], t, rec.fs, rec.line_freq)
          for c in PHASE_VOLTAGES]
    z, p, ne = sequence(ph[0], ph[1], ph[2])
    good = np.isfinite(p) & np.isfinite(ne)
    if not np.any(good):
        return None
    ratio = float(np.median(np.abs(ne[good]) / np.maximum(np.abs(p[good]), 1e-9)))
    return "ABC" if ratio < 1.0 else "ACB"


def gate(rec: Record, **kw) -> bool:
    """Run check() and return True if the record may proceed."""
    check(rec, **kw)
    return not rec.blocked()
