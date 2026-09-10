"""COMTRADE reader written from the standard, not from an assumption of
conformance.

Every off-the-shelf parser assumes something the real fleet does not provide.
The four real files in this repo's corpus already break three assumptions:

  * rev_year is "2001" on one relay and "1997" on another. Neither is a valid
    COMTRADE revision (1991 / 1999 / 2013), so the edition is inferred from
    the structure of the CFG, never from that field.
  * nrates = 0 on one relay, with the true rate carried only in the DAT
    timestamp column (1200.5 Hz, 24.0 samples/cycle).
  * both DAT files end with a DOS 0x1A byte, which crashes a naive reader.

Handled here: 1991 / 1999 / 2013, ASCII / BINARY / BINARY32 / FLOAT32, the
four-file form and the single-file .CFF, nrates 0 / 1 / n, and P/S scaling.
"""
from __future__ import annotations

import hashlib
import math
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..signals import AnalogMeta, Record

DOS_EOF = "\x1a"
DATE_FORMATS = (
    "%d/%m/%Y,%H:%M:%S.%f", "%d/%m/%y,%H:%M:%S.%f",
    "%m/%d/%Y,%H:%M:%S.%f", "%d/%m/%Y,%H:%M:%S",
    "%Y-%m-%d,%H:%M:%S.%f",
)


class ComtradeError(Exception):
    pass


# --------------------------------------------------------------------------
# channel name mapping
# --------------------------------------------------------------------------
_PHASE_TOKENS = {
    "L1": "A", "L2": "B", "L3": "C",
    "1": "A", "2": "B", "3": "C",
    "N": "N", "E": "N", "G": "N", "0": "N",
}


def _norm(s: str) -> str:
    return re.sub(r"[\s_\-.:]", "", (s or "").strip().upper())


def _last_token(raw_id: str) -> str:
    """The last separator-delimited token of a channel id, I/U/V stripped.

    A vendor prefix defeats any match anchored at the start of the id: ABB
    writes ``LINE1_A_IL1`` and ``LINE1_UL1``, where the phase lives in the
    final token. Only the LAST token is ever considered, never any token --
    the GE D60 writes ``SRC 1  Ia Mag`` for an RMS magnitude channel, which
    is not a waveform and must stay unmapped.
    """
    parts = [p for p in re.split(r"[\s_\-.:]+", (raw_id or "").strip()) if p]
    if len(parts) < 2:
        return ""
    return re.sub(r"^[IUV]", "", _norm(parts[-1]))


def detect_phase_naming(ids: Sequence[str]) -> str:
    """Decide whether this record names phases A/B/C, R/Y/B or L1/L2/L3.

    This matters: in the Indian R/Y/B convention B is BLUE, i.e. phase C,
    while in the IEEE convention B is phase B. Guessing wrong swaps two
    phases, which silently changes the fault type and the location.
    """
    tail = set()
    for i in ids:
        n = re.sub(r"^[IUV]", "", _norm(i))
        for t in (n, _last_token(i)):
            if t:
                tail.add(t[:2] if t[:2] in ("L1", "L2", "L3") else t[:1])
    if {"L1", "L2", "L3"} & tail:
        return "IEC"
    if "R" in tail and "Y" in tail:
        return "RYB"
    return "ABC"


def map_channel(raw_id: str, unit: str, ph_field: str, naming: str) -> Optional[str]:
    """Vendor channel id -> canonical name, or None if unrecognised.

    The unit field is the authority for current vs voltage; the id text is
    used only for the phase. Vendors are far more consistent about units than
    about names.
    """
    u = _norm(unit)
    n = _norm(raw_id)
    if u.startswith("A") or u in ("KA",):
        kind = "I"
    elif u.startswith("V") or u in ("KV",):
        kind = "V"
    elif n.startswith("I"):
        kind = "I"
    elif n.startswith("V") or n.startswith("U"):
        kind = "V"
    else:
        return None

    body = re.sub(r"^[IUV]", "", n)
    ph = _norm(ph_field)
    # The last token is a fallback, tried only after the whole id and the ph
    # field, so no record that maps today can change its mapping.
    for token in (body, ph, _last_token(raw_id)):
        if not token:
            continue
        if token[:2] in ("L1", "L2", "L3"):
            return kind + _PHASE_TOKENS[token[:2]]
        c = token[:1]
        if c in _PHASE_TOKENS:
            return kind + _PHASE_TOKENS[c]
        if naming == "RYB":
            if c == "R":
                return kind + "A"
            if c == "Y":
                return kind + "B"
            if c == "B":
                return kind + "C"
        else:
            if c in ("A", "B", "C"):
                return kind + c
            if c == "R":
                return kind + "A"
            if c == "Y":
                return kind + "B"
    return None


# --------------------------------------------------------------------------
# CFG
# --------------------------------------------------------------------------
@dataclass
class CfgAnalog:
    index: int
    ch_id: str
    ph: str
    ccbm: str
    uu: str
    a: float
    b: float
    skew: float
    minv: float
    maxv: float
    primary: float = 1.0
    secondary: float = 1.0
    ps: str = "P"


@dataclass
class Cfg:
    station: str
    device_id: str
    rev_year_raw: str
    edition: int
    n_analog: int
    n_digital: int
    analogs: List[CfgAnalog]
    digitals: List[str]
    line_freq: float
    nrates: int
    rates: List[Tuple[float, int]]
    start_time: Optional[datetime]
    trigger_time: Optional[datetime]
    file_type: str
    timemult: float
    time_code: str = ""
    tmq_code: str = ""
    leapsec: str = ""
    warnings: List[str] = None
    local_code: str = ""

    @property
    def total_samples(self) -> int:
        return self.rates[-1][1] if self.rates else 0


def _f(x: str, default: float = 0.0) -> float:
    x = (x or "").strip()
    if not x:
        return default
    try:
        return float(x)
    except ValueError:
        return default


def _parse_time(s: str) -> Optional[datetime]:
    s = (s or "").strip()
    if not s:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def parse_cfg(text: str) -> Cfg:
    lines = [ln.rstrip("\r\n") for ln in text.replace(DOS_EOF, "").splitlines()]
    lines = [ln for ln in lines if ln.strip()]
    if len(lines) < 4:
        raise ComtradeError("CFG has too few lines")
    warn: List[str] = []

    head = [x.strip() for x in lines[0].split(",")]
    station = head[0] if head else ""
    device = head[1] if len(head) > 1 else ""
    rev_raw = head[2] if len(head) > 2 else ""

    counts = [x.strip() for x in lines[1].split(",")]
    if len(counts) < 3:
        raise ComtradeError("CFG channel-count line is malformed: " + lines[1])
    na = int(re.sub(r"[^0-9]", "", counts[1]) or 0)
    nd = int(re.sub(r"[^0-9]", "", counts[2]) or 0)

    analogs: List[CfgAnalog] = []
    for i in range(na):
        f = [x.strip() for x in lines[2 + i].split(",")]
        if len(f) < 10:
            raise ComtradeError("analog channel line " + str(i + 1) + " is short")
        analogs.append(CfgAnalog(
            index=int(_f(f[0], i + 1)), ch_id=f[1], ph=f[2], ccbm=f[3], uu=f[4],
            a=_f(f[5], 1.0), b=_f(f[6]), skew=_f(f[7]),
            minv=_f(f[8], -32768.0), maxv=_f(f[9], 32767.0),
            primary=_f(f[10], 1.0) if len(f) > 10 else 1.0,
            secondary=_f(f[11], 1.0) if len(f) > 11 else 1.0,
            ps=(f[12].strip().upper()[:1] if len(f) > 12 and f[12].strip() else "P"),
        ))
    n_fields = len([x for x in lines[2].split(",")]) if na else 13

    digitals = []
    for i in range(nd):
        f = [x.strip() for x in lines[2 + na + i].split(",")]
        digitals.append(f[1] if len(f) > 1 else "D" + str(i + 1))

    j = 2 + na + nd
    lf = _f(lines[j], 50.0)
    nrates = int(_f(lines[j + 1], 1))
    j += 2
    rates: List[Tuple[float, int]] = []
    for k in range(max(nrates, 1)):
        f = [x.strip() for x in lines[j + k].split(",")]
        rates.append((_f(f[0]), int(_f(f[1])) if len(f) > 1 else 0))
    j += max(nrates, 1)

    start = _parse_time(lines[j]) if j < len(lines) else None
    trig = _parse_time(lines[j + 1]) if j + 1 < len(lines) else None
    ftype = lines[j + 2].strip().upper() if j + 2 < len(lines) else "ASCII"
    timemult = _f(lines[j + 3], 1.0) if j + 3 < len(lines) else 1.0
    if timemult <= 0:
        timemult = 1.0

    time_code = local_code = tmq = leap = ""
    if j + 4 < len(lines):
        parts = [x.strip() for x in lines[j + 4].split(",")]
        time_code = parts[0] if parts else ""
        local_code = parts[1] if len(parts) > 1 else ""
    if j + 5 < len(lines):
        parts = [x.strip() for x in lines[j + 5].split(",")]
        tmq = parts[0] if parts else ""
        leap = parts[1] if len(parts) > 1 else ""

    # Edition inferred from structure, never from rev_year: the corpus
    # carries "2001" and "1997", neither of which is a real revision.
    if time_code or tmq:
        edition = 2013
    elif n_fields >= 13:
        edition = 1999
    else:
        edition = 1991
    if rev_raw not in ("1991", "1999", "2013", ""):
        warn.append("non-standard rev_year " + repr(rev_raw)
                    + "; edition inferred from structure as " + str(edition))
    if nrates == 0:
        warn.append("nrates=0: sampling rate is not stated in the CFG and is "
                    "derived from the DAT timestamp column")

    return Cfg(station=station, device_id=device, rev_year_raw=rev_raw,
               edition=edition, n_analog=na, n_digital=nd, analogs=analogs,
               digitals=digitals, line_freq=lf, nrates=nrates, rates=rates,
               start_time=start, trigger_time=trig, file_type=ftype,
               timemult=timemult, time_code=time_code, tmq_code=tmq,
               leapsec=leap, warnings=warn, local_code=local_code)


# --------------------------------------------------------------------------
# DAT
# --------------------------------------------------------------------------
def _read_ascii(text: str, na: int, nd: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    rows = [ln for ln in text.replace(DOS_EOF, "").splitlines() if ln.strip()]
    ncol = 2 + na + nd
    out = np.zeros((len(rows), ncol), dtype=np.float64)
    for i, ln in enumerate(rows):
        f = ln.split(",")
        for k in range(min(ncol, len(f))):
            v = f[k].strip()
            out[i, k] = float(v) if v else 0.0
    return out[:, 0], out[:, 1], out[:, 2:]


def _read_binary(buf: bytes, na: int, nd: int, kind: str):
    dmap = {"BINARY": ("<i2", 2), "BINARY32": ("<i4", 4), "FLOAT32": ("<f4", 4)}
    if kind not in dmap:
        raise ComtradeError("unsupported DAT type " + repr(kind))
    dt, width = dmap[kind]
    ndw = (nd + 15) // 16
    rec = 8 + na * width + ndw * 2
    n = len(buf) // rec
    if n == 0:
        raise ComtradeError("binary DAT is empty or truncated")
    arr = np.frombuffer(buf[: n * rec], dtype=np.uint8).reshape(n, rec)
    smp = arr[:, 0:4].copy().view("<u4").reshape(n)
    ts = arr[:, 4:8].copy().view("<u4").reshape(n)
    ana = arr[:, 8 : 8 + na * width].copy().view(dt).reshape(n, na).astype(np.float64)
    dig = np.zeros((n, nd), dtype=np.float64)
    if nd:
        words = arr[:, 8 + na * width :].copy().view("<u2").reshape(n, ndw)
        for k in range(nd):
            dig[:, k] = (words[:, k // 16] >> (k % 16)) & 1
    return smp.astype(np.float64), ts.astype(np.float64), np.hstack([ana, dig])


# --------------------------------------------------------------------------
# top level
# --------------------------------------------------------------------------
def _derive_time(cfg: Cfg, ts_col: np.ndarray, n: int) -> Tuple[np.ndarray, float, List[str]]:
    """Sample times in seconds, and the effective rate.

    nrates >= 1 is authoritative. nrates == 0 means the rate lives only in
    the timestamp column, and the column is in microseconds scaled by
    timemult. A least-squares fit is used rather than a first difference,
    because vendors round the increment (833 us for a nominal 1200 Hz gives
    1200.5 Hz if you take the reciprocal of one interval).
    """
    warn: List[str] = []
    if cfg.nrates >= 1 and cfg.rates and cfg.rates[0][0] > 0:
        if cfg.nrates == 1:
            fs = cfg.rates[0][0]
            return np.arange(n) / fs, fs, warn
        t = np.zeros(n)
        idx, prev_end, prev_t = 0, 0, 0.0
        for rate, endsamp in cfg.rates:
            end = min(int(endsamp), n)
            cnt = end - prev_end
            if cnt <= 0 or rate <= 0:
                continue
            t[prev_end:end] = prev_t + np.arange(cnt) / rate
            prev_t = t[end - 1] + 1.0 / rate
            prev_end = end
        warn.append("multi-rate record (" + str(cfg.nrates)
                    + " rates); phasor estimation uses the rate of the fault segment")
        eff = max(r for r, _ in cfg.rates if r > 0)
        return t, eff, warn

    t = ts_col.astype(float) * cfg.timemult * 1e-6
    if n > 2 and np.ptp(t) > 0:
        k = np.arange(n)
        slope = float(np.polyfit(k, t, 1)[0])
        fs = 1.0 / slope if slope > 0 else cfg.line_freq * 20.0
        warn.append("rate derived from the DAT timestamp column: "
                    + format(fs, ".1f") + " Hz")
        return k * slope, fs, warn
    fs = cfg.line_freq * 20.0
    warn.append("no usable rate information; assuming " + format(fs, ".0f") + " Hz")
    return np.arange(n) / fs, fs, warn


def read_comtrade(
    cfg_path: str, dat_path: Optional[str] = None, terminal_end: str = "", *, channel_mapping=None
) -> Record:
    """Read a four-file-form COMTRADE record into a canonical Record."""
    with open(cfg_path, "r", encoding="latin-1") as fh:
        cfg = parse_cfg(fh.read())
    if dat_path is None:
        base, _ = os.path.splitext(cfg_path)
        for cand in (base + ".DAT", base + ".dat", base + ".Dat"):
            if os.path.exists(cand):
                dat_path = cand
                break
    if dat_path is None or not os.path.exists(dat_path):
        raise ComtradeError("no DAT file found next to " + cfg_path)
    return _assemble(cfg, open(dat_path, "rb").read(), cfg_path, dat_path, terminal_end, channel_mapping)


def read_cff(path: str, terminal_end: str = "", *, channel_mapping=None) -> Record:
    """Read the 2013 single-file .CFF form."""
    raw = open(path, "rb").read()
    text = raw.decode("latin-1")
    m = re.search(r"---\s*file type:\s*CFG[^\r\n]*[\r\n]+", text, re.I)
    d = re.search(r"---\s*file type:\s*DAT([^\r\n]*)[\r\n]+", text, re.I)
    if not m or not d:
        raise ComtradeError("not a CFF file: missing file-type separators")
    cfg = parse_cfg(text[m.end() : d.start()])
    kind = d.group(1).upper()
    if "BINARY32" in kind:
        cfg.file_type = "BINARY32"
    elif "FLOAT32" in kind:
        cfg.file_type = "FLOAT32"
    elif "BINARY" in kind:
        cfg.file_type = "BINARY"
    else:
        cfg.file_type = "ASCII"
    payload = raw[d.end() :] if cfg.file_type != "ASCII" else text[d.end() :].encode("latin-1")
    return _assemble(cfg, payload, path, path, terminal_end, channel_mapping)


def _assemble(cfg: Cfg, dat_bytes: bytes, cfg_path: str, dat_path: str,
              terminal_end: str, channel_mapping=None) -> Record:
    from .channel_review import channel_plan
    review = channel_mapping or {}
    na, nd = cfg.n_analog, cfg.n_digital
    ftype = cfg.file_type.strip().upper()
    if ftype.startswith("ASCII"):
        smp, ts, cols = _read_ascii(dat_bytes.decode("latin-1"), na, nd)
    else:
        smp, ts, cols = _read_binary(dat_bytes, na, nd, ftype)
    n = cols.shape[0]
    t, fs, twarn = _derive_time(cfg, ts, n)

    naming = detect_phase_naming([a.ch_id for a in cfg.analogs])
    targets, digital_keys, inventory, digital_overrides = channel_plan(cfg, naming, map_channel, review)
    analog: Dict[str, np.ndarray] = {}
    raw_analog: Dict[str, np.ndarray] = {}
    meta: Dict[str, AnalogMeta] = {}
    unmapped: List[str] = []

    for i, ch in enumerate(cfg.analogs):
        canon = targets[i]
        if canon is None or canon in analog:
            unmapped.append(ch.ch_id.strip())
            continue
        raw = cols[:, i]
        vals = raw * ch.a + ch.b
        # P/S is the difference between a value already in primary units and
        # one in secondary units needing the ratio. Getting this wrong is an
        # 800x current error on the real Siemens record in this corpus.
        if ch.ps == "S" and ch.secondary:
            vals = vals * (ch.primary / ch.secondary)
        if _norm(ch.uu).startswith("K"):
            vals = vals * 1000.0
        analog[canon] = vals
        raw_analog[canon] = raw
        meta[canon] = AnalogMeta(
            raw_id=ch.ch_id.strip(), unit=ch.uu.strip(), a=ch.a, b=ch.b,
            primary=ch.primary, secondary=ch.secondary, ps=ch.ps,
            adc_min=ch.minv, adc_max=ch.maxv, phase=canon[-1], normalised=True,
        )

    digital: Dict[str, np.ndarray] = {}
    for k, name in enumerate(digital_keys):
        digital[name] = cols[:, na + k].astype(np.int8)

    h = hashlib.sha256()
    h.update(open(cfg_path, "rb").read())
    if dat_path != cfg_path:
        h.update(dat_bytes)
    digest = h.hexdigest()
    if review and review.get('record_hash') != digest:
        raise ValueError('Reviewed channel mapping belongs to a different recording hash; review it again.')

    rec = Record(
        record_id=os.path.splitext(os.path.basename(cfg_path))[0],
        station=cfg.station, device_id=cfg.device_id, rev_year=cfg.rev_year_raw,
        start_time=cfg.start_time, trigger_time=cfg.trigger_time,
        fs=fs, line_freq=cfg.line_freq, t=t, analog=analog, digital=digital,
        analog_meta=meta, raw_analog=raw_analog, source_path=cfg_path,
        content_hash=digest, terminal_end=terminal_end, nrates=cfg.nrates,
        notes={"edition": cfg.edition, "file_type": ftype, "naming": naming,
               "unmapped_channels": unmapped, "n_analog": na, "n_digital": nd,
               "tmq_code": cfg.tmq_code, "time_code": cfg.time_code,
               "local_code": cfg.local_code, "leapsec": cfg.leapsec,
               "declared_endsamp": cfg.total_samples, 'channel_inventory': inventory,
               'channel_mapping': review, 'digital_overrides': digital_overrides},
    )
    for w in list(cfg.warnings or []) + twarn:
        rec.add_flag("CT-INFO", "info", w)
    if review:
        rec.add_flag('CH-REVIEW', 'flag', 'Explicit channel mapping applied to original record '+digest+
                     '; '+str(review.get('reason', ''))+'; '+str(review.get('analog', {}))+'; '+str(review.get('digital', {})))
    if unmapped:
        rec.add_flag("CH-UNMAPPED", "info",
                     str(len(unmapped)) + " analog channels not mapped to the "
                     "canonical schema: " + ", ".join(unmapped[:6]))
    return rec
