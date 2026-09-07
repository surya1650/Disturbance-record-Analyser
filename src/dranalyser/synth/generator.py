"""Synthetic two-terminal fault generator with known m.

This is the test oracle. It is deliberately built FIRST and depends on
nothing else in the package, so every other stage (parser, DSP, estimators,
ML) can be graded against a known truth from the first hour.

Model
-----
Phase-domain, three-phase, two-source, single line section:

      Es --[Zsrc_S]--+--[ m * Zline ]--(F)--[ (1-m) * Zline ]--+--[Zsrc_R]-- Er
                     S                                          R

Sequence impedances are converted to a 3x3 phase matrix via
    Zself = (Z0 + 2*Z1)/3      Zmutual = (Z0 - Z1)/3
(assuming Z2 == Z1, which is true for lines).

The fault is a general star: each faulted phase connects through rf to a
common node, which connects to ground through rg. rg = None means the star
point floats, which is how phase-phase and ungrounded three-phase faults are
represented. Kron-eliminating the star node gives a 3x3 fault admittance,
so one code path covers AG/BG/CG/AB/BC/CA/ABG/BCG/CAG/ABC.

Realism layers applied on top of the phasor solution, each independently
switchable so a test can isolate what it is measuring:
  * decaying DC offset on currents, sized for current continuity at inception
  * CVT subsidence transient on voltages
  * CT saturation (flux-based, per phase)
  * white noise and ADC quantisation
  * per-terminal breaker opening at a current zero
  * INDEPENDENT time origin and sample rate per terminal, which is what
    makes the unsynchronised estimator E5 honestly testable
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np

from ..signals import AnalogMeta, Record

A = np.exp(2j * np.pi / 3.0)

FAULT_PHASES: Dict[str, Tuple[Tuple[int, ...], bool]] = {
    # name: (phase indices involved, involves_ground)
    "AG": ((0,), True),
    "BG": ((1,), True),
    "CG": ((2,), True),
    "AB": ((0, 1), False),
    "BC": ((1, 2), False),
    "CA": ((2, 0), False),
    "ABG": ((0, 1), True),
    "BCG": ((1, 2), True),
    "CAG": ((2, 0), True),
    "ABC": ((0, 1, 2), False),
    "ABCG": ((0, 1, 2), True),
}


def seq_to_phase_matrix(z1: complex, z0: complex) -> np.ndarray:
    """3x3 phase impedance matrix of a balanced element (Z2 == Z1)."""
    zs = (z0 + 2.0 * z1) / 3.0
    zm = (z0 - z1) / 3.0
    return np.array(
        [[zs, zm, zm], [zm, zs, zm], [zm, zm, zs]], dtype=complex
    )


def phase_to_seq(v: np.ndarray) -> np.ndarray:
    """[Va,Vb,Vc] -> [V0,V1,V2]."""
    t = np.array(
        [[1.0, 1.0, 1.0], [1.0, A, A * A], [1.0, A * A, A]], dtype=complex
    ) / 3.0
    return t @ v


def fault_admittance(kind: str, rf: float, rg: Optional[float]) -> np.ndarray:
    """3x3 fault admittance for a general star fault (Kron-reduced).

    rf is the resistance of EACH faulted-phase leg; rg is the star-point to
    ground resistance (0.0 = solidly grounded, None = floating star).
    """
    if kind not in FAULT_PHASES:
        raise ValueError("unknown fault type " + repr(kind))
    phases, grounded = FAULT_PHASES[kind]
    y = 1.0 / max(rf, 1e-9)
    yf = np.zeros((3, 3), dtype=complex)
    if grounded and (rg is not None) and rg <= 1e-9:
        # star point solidly at ground: each leg is independent to ground
        for p in phases:
            yf[p, p] = y
        return yf
    yg = 0.0 if (rg is None or not grounded) else 1.0 / max(rg, 1e-9)
    yn = len(phases) * y + yg
    for i in phases:
        for j in phases:
            yf[i, j] = (y if i == j else 0.0) - y * y / yn
    return yf


@dataclass
class TerminalSpec:
    """How one terminal records the event."""

    fs: float = 1000.0
    # Time from fault inception to the first sample of the record, i.e. how
    # much pre-fault the relay captured. Deliberately different per terminal.
    prefault_s: float = 0.10
    post_s: float = 0.20
    # Free-running clock error, seconds. E5 must be immune to this.
    clock_offset_s: float = 0.0
    # Fraction of a sample by which this terminal's grid is shifted, so the
    # two records do not share sample instants even at equal fs.
    sample_phase: float = 0.0
    trip_delay_s: float = 0.020
    breaker_time_s: float = 0.040
    ct_saturation: bool = False
    ct_knee_pu: float = 12.0
    adc_bits: int = 12
    adc_full_scale_i: float = 40000.0
    adc_full_scale_v: float = 600000.0
    noise_pct: float = 0.05
    cvt_transient: bool = True
    vt_type: str = "CVT"


@dataclass
class SynthSpec:
    """Everything that defines one synthetic incident."""

    m: float = 0.35
    fault: str = "AG"
    rf: float = 1.0
    rg: Optional[float] = 0.0
    kv: float = 220.0
    line_km: float = 100.0
    z1_per_km: complex = complex(0.030, 0.400)
    z0_per_km: complex = complex(0.250, 1.200)
    zs1_S: complex = complex(1.0, 12.0)
    zs0_S: complex = complex(2.0, 20.0)
    zs1_R: complex = complex(1.5, 18.0)
    zs0_R: complex = complex(3.0, 30.0)
    load_angle_deg: float = 12.0
    source_ratio_R: float = 1.0
    freq: float = 50.0
    inception_angle_deg: float = 0.0
    dc_offset: bool = True
    seed: int = 0
    S: TerminalSpec = field(default_factory=TerminalSpec)
    R: TerminalSpec = field(
        default_factory=lambda: TerminalSpec(fs=1200.0, prefault_s=0.14, sample_phase=0.37)
    )

    @property
    def z1_line(self) -> complex:
        return self.z1_per_km * self.line_km

    @property
    def z0_line(self) -> complex:
        return self.z0_per_km * self.line_km


@dataclass
class SynthTruth:
    """Ground truth carried alongside the records, for assertions only."""

    m: float
    km_from_S: float
    fault: str
    rf: float
    z1_line: complex
    z0_line: complex
    phasors: Dict[str, complex]
    clock_offset_s: float


@dataclass
class SynthCase:
    truth: SynthTruth
    records: Dict[str, Record]

    def record(self, end: str) -> Record:
        return self.records[end]


def _solve_phasors(spec: SynthSpec) -> Dict[str, np.ndarray]:
    """Steady-state pre-fault and fault phasors at both terminals.

    Returns RMS phasors, currents positive from bus INTO the line at both
    ends (the convention every estimator in faultloc assumes).
    """
    zl = seq_to_phase_matrix(spec.z1_line, spec.z0_line)
    zss = seq_to_phase_matrix(spec.zs1_S, spec.zs0_S)
    zsr = seq_to_phase_matrix(spec.zs1_R, spec.zs0_R)
    m = spec.m

    vph = spec.kv * 1000.0 / math.sqrt(3.0)
    ang = np.array([0.0, -2.0 * np.pi / 3.0, 2.0 * np.pi / 3.0])
    es = vph * np.exp(1j * (ang + math.radians(spec.load_angle_deg)))
    er = vph * spec.source_ratio_R * np.exp(1j * ang)

    # pre-fault
    ztot = zss + zl + zsr
    ipre = np.linalg.solve(ztot, es - er)          # S -> R, into line at S
    vf_pre = es - (zss + m * zl) @ ipre

    # Thevenin at the fault point
    za = zss + m * zl                              # F back through S
    zb = zsr + (1.0 - m) * zl                      # F back through R
    zth = np.linalg.inv(np.linalg.inv(za) + np.linalg.inv(zb))

    yf = fault_admittance(spec.fault, spec.rf, spec.rg)
    ifault = np.linalg.solve(np.eye(3) + yf @ zth, yf @ vf_pre)

    vf = vf_pre - zth @ ifault
    dis = np.linalg.solve(za, zth @ ifault)
    dir_ = np.linalg.solve(zb, zth @ ifault)

    is_ = ipre + dis
    ir = -ipre + dir_
    vs = vf + (m * zl) @ is_
    vr = vf + ((1.0 - m) * zl) @ ir

    return {
        "IS_pre": ipre,
        "IR_pre": -ipre,
        "VS_pre": es - zss @ ipre,
        "VR_pre": er + zsr @ ipre,
        "IS": is_,
        "IR": ir,
        "VS": vs,
        "VR": vr,
        "VF": vf,
        "IF": ifault,
        "ZA": za,
        "ZB": zb,
    }


def _wave(phasor: complex, t: np.ndarray, w: float) -> np.ndarray:
    """RMS phasor -> instantaneous samples."""
    return math.sqrt(2.0) * np.real(phasor * np.exp(1j * w * t))


def _ct_saturate(i: np.ndarray, fs: float, knee: float) -> np.ndarray:
    """Flux-based CT saturation.

    Integrate the secondary current to get flux; once |flux| exceeds the
    knee the core cannot support further flux, so the output collapses
    towards zero for the rest of that half cycle. Crude but it produces the
    right signature: clipped peaks, missing area, a large third difference.
    """
    out = i.copy()
    flux = 0.0
    dt = 1.0 / fs
    for k in range(i.size):
        flux += i[k] * dt
        # flux decays back through the magnetising branch between saturations
        flux *= 0.999
        if abs(flux) > knee:
            excess = (abs(flux) - knee) / knee
            out[k] = i[k] * math.exp(-6.0 * excess)
            flux = math.copysign(knee, flux)
    return out


def _quantise(x: np.ndarray, bits: int, full_scale: float) -> np.ndarray:
    if bits <= 0:
        return x
    lsb = 2.0 * full_scale / (2 ** bits)
    return np.round(x / lsb) * lsb


def _build_record(
    end: str,
    spec: SynthSpec,
    ts: TerminalSpec,
    ph: Dict[str, np.ndarray],
    rng: np.random.Generator,
) -> Record:
    w = 2.0 * np.pi * spec.freq
    dt = 1.0 / ts.fs
    n = int(round((ts.prefault_s + ts.post_s) * ts.fs))
    # record-local time; inception sits at t = prefault_s
    t = (np.arange(n) + ts.sample_phase) * dt
    t0 = ts.prefault_s
    # inception angle is imposed by shifting the common phase reference
    phi0 = math.radians(spec.inception_angle_deg)

    ipre = ph["IS_pre"] if end == "S" else ph["IR_pre"]
    vpre = ph["VS_pre"] if end == "S" else ph["VR_pre"]
    ifl = ph["IS"] if end == "S" else ph["IR"]
    vfl = ph["VS"] if end == "S" else ph["VR"]
    za = ph["ZA"] if end == "S" else ph["ZB"]

    post = t >= t0
    tau = max(abs(za[0, 0].imag) / (w * max(abs(za[0, 0].real), 1e-6)), 1e-4)

    analog: Dict[str, np.ndarray] = {}
    names_i = ("IA", "IB", "IC")
    names_v = ("VA", "VB", "VC")

    for k in range(3):
        pre_w = _wave(ipre[k] * np.exp(1j * phi0), t, w)
        flt_w = _wave(ifl[k] * np.exp(1j * phi0), t, w)
        sig = np.where(post, flt_w, pre_w)
        if spec.dc_offset:
            # current is continuous through inception in an inductive circuit
            k0 = float(
                math.sqrt(2.0) * np.real(ipre[k] * np.exp(1j * (w * t0 + phi0)))
                - math.sqrt(2.0) * np.real(ifl[k] * np.exp(1j * (w * t0 + phi0)))
            )
            sig = sig + np.where(post, k0 * np.exp(-(t - t0) / tau), 0.0)
        analog[names_i[k]] = sig

        pre_v = _wave(vpre[k] * np.exp(1j * phi0), t, w)
        flt_v = _wave(vfl[k] * np.exp(1j * phi0), t, w)
        vsig = np.where(post, flt_v, pre_v)
        if ts.cvt_transient and ts.vt_type.upper() == "CVT":
            # subsidence transient: decaying sub-synchronous ring on the step
            step = float(
                math.sqrt(2.0) * np.real(vpre[k] * np.exp(1j * (w * t0 + phi0)))
                - math.sqrt(2.0) * np.real(vfl[k] * np.exp(1j * (w * t0 + phi0)))
            )
            ring = (
                step
                * np.exp(-(t - t0) / 0.012)
                * np.cos(2.0 * np.pi * 33.0 * (t - t0))
            )
            vsig = vsig + np.where(post, ring, 0.0)
        analog[names_v[k]] = vsig

    # breaker opening: current forced to zero from the first current zero
    # after the trip + breaker time, per phase
    t_open = t0 + ts.trip_delay_s + ts.breaker_time_s
    cb_open = np.zeros(n, dtype=np.int8)
    for k in range(3):
        sig = analog[names_i[k]]
        idx = np.nonzero(t >= t_open)[0]
        if idx.size:
            j = idx[0]
            while j + 1 < n and sig[j] * sig[j + 1] > 0:
                j += 1
            sig[j:] = 0.0
            cb_open[j:] = 1

    analog["IN"] = analog["IA"] + analog["IB"] + analog["IC"]
    analog["VN"] = analog["VA"] + analog["VB"] + analog["VC"]

    if ts.ct_saturation:
        knee = ts.ct_knee_pu * float(np.max(np.abs(np.array([ipre[0], ipre[1], ipre[2]])))) / ts.fs
        knee = max(knee, 1e-3)
        for nm in names_i:
            analog[nm] = _ct_saturate(analog[nm], ts.fs, knee)
        analog["IN"] = analog["IA"] + analog["IB"] + analog["IC"]

    for nm, fsv in list(zip(names_i + ("IN",), [ts.adc_full_scale_i] * 4)) + list(
        zip(names_v + ("VN",), [ts.adc_full_scale_v] * 4)
    ):
        x = analog[nm]
        if ts.noise_pct > 0:
            scale = ts.noise_pct / 100.0 * max(float(np.max(np.abs(x))), 1e-9)
            x = x + rng.normal(0.0, scale, x.size)
        analog[nm] = _quantise(x, ts.adc_bits, fsv)

    digital = {
        "START": (t >= t0 + 0.004).astype(np.int8),
        "TRIP": (t >= t0 + ts.trip_delay_s).astype(np.int8),
        "Z1": (t >= t0 + ts.trip_delay_s).astype(np.int8),
        "CB_OPEN": cb_open,
        "CARRIER_SEND": (t >= t0 + ts.trip_delay_s).astype(np.int8),
        "CARRIER_RECV": (t >= t0 + ts.trip_delay_s + 0.008).astype(np.int8),
    }

    base = datetime(2026, 4, 9, 3, 5, 0)
    start = base + timedelta(seconds=ts.clock_offset_s)
    meta = {
        nm: AnalogMeta(
            raw_id=nm,
            unit="A" if nm.startswith("I") else "V",
            a=1.0,
            b=0.0,
            primary=1.0,
            secondary=1.0,
            ps="P",
            adc_min=-(2 ** (ts.adc_bits - 1)),
            adc_max=2 ** (ts.adc_bits - 1) - 1,
            phase=nm[-1],
            normalised=True,
        )
        for nm in analog
    }

    return Record(
        record_id="SYNTH-" + end,
        station="SYNTH-" + end,
        device_id="synth",
        rev_year="2013",
        start_time=start,
        trigger_time=start + timedelta(seconds=t0),
        fs=ts.fs,
        line_freq=spec.freq,
        t=t,
        analog=analog,
        digital=digital,
        analog_meta=meta,
        terminal_end=end,
        time_basis="synthetic",
        notes={"inception_t": t0},
    )


def generate(spec: SynthSpec) -> SynthCase:
    """Build one synthetic incident: two records plus the ground truth."""
    ph = _solve_phasors(spec)
    rng = np.random.default_rng(spec.seed)
    recs = {
        "S": _build_record("S", spec, spec.S, ph, rng),
        "R": _build_record("R", spec, spec.R, ph, rng),
    }
    v2s = phase_to_seq(ph["VS"])[2]
    v2r = phase_to_seq(ph["VR"])[2]
    i2s = phase_to_seq(ph["IS"])[2]
    i2r = phase_to_seq(ph["IR"])[2]
    truth = SynthTruth(
        m=spec.m,
        km_from_S=spec.m * spec.line_km,
        fault=spec.fault,
        rf=spec.rf,
        z1_line=spec.z1_line,
        z0_line=spec.z0_line,
        phasors={"V2S": v2s, "V2R": v2r, "I2S": i2s, "I2R": i2r},
        clock_offset_s=spec.R.clock_offset_s - spec.S.clock_offset_s,
    )
    return SynthCase(truth=truth, records=recs)


def sweep(
    ms: List[float],
    faults: List[str],
    rfs: List[float],
    base: Optional[SynthSpec] = None,
    **overrides,
) -> List[SynthCase]:
    """Cartesian sweep used by the Stage-A acceptance test."""
    import copy

    out: List[SynthCase] = []
    seed = 0
    for m in ms:
        for f in faults:
            for rf in rfs:
                s = copy.deepcopy(base) if base else SynthSpec()
                s.m, s.fault, s.rf, s.seed = m, f, rf, seed
                for k, v in overrides.items():
                    setattr(s, k, v)
                out.append(generate(s))
                seed += 1
    return out
