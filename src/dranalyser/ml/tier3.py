"""Tier 3 - machine learning where the labels are actually plentiful.

Per-relay learned fault location is ruled out: a line sees 1-3 faults a year,
maybe a quarter get a patrol-confirmed location, and the label noise is about
one span, which is the size of the error being corrected. Fitting anything on
five points produces a model that looks excellent on those five and moves the
sixth answer in the wrong direction while carrying the authority of "the
model said so".

These three problems are different. Their labels are generated, not waited
for, so there are as many as the machine will hold:

  fault type          labels come from the synthetic generator, which knows
                      the answer exactly
  CT saturation       labels generated from a CT model, unlimited quantity
  quality anomaly     unsupervised; catches ratio errors, polarity errors and
                      channel-mapping drift as the fleet changes

Every model here is a SECOND OPINION. The physics classifier runs first and
its answer is what the estimators use. Disagreement raises a finding for a
human, and is the signal that either the model or the record is wrong.
"""
from __future__ import annotations

import math
import os
import pickle
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..dsp.pipeline import Analysed

FAULT_CLASSES = ("AG", "BG", "CG", "AB", "BC", "CA", "ABG", "BCG", "CAG", "ABC")

FAULT_FEATURES = (
    "r2", "r0", "ang_i2_di1_cos", "ang_i2_di1_sin",
    "ang_i0_i2_cos", "ang_i0_i2_sin",
    "ia_rel", "ib_rel", "ic_rel", "va_sag", "vb_sag", "vc_sag",
    "i_unbalance", "v_unbalance",
)

SAT_FEATURES = (
    "d3_ratio", "crest", "h2_ratio", "h3_ratio", "half_cycle_area_ratio",
    "peak_flatness",
)


# --------------------------------------------------------------------------
# feature extraction
# --------------------------------------------------------------------------
def fault_features(an: Analysed, idx: Optional[int] = None) -> Dict[str, float]:
    """Features for fault-type classification, from one analysed record."""
    if idx is None:
        idx = int(an.notes.get("classify_idx", an.ps.valid_from + 1))
    i1 = an.phasor("I1", idx)
    i2 = an.phasor("I2", idx)
    i0 = an.phasor("I0", idx)
    di1 = i1 - an.ref.get("I1", 0j)
    d = max(abs(di1), 1e-9)

    def ang(z):
        return (math.cos(np.angle(z)), math.sin(np.angle(z)))

    a_i2 = ang(i2 / di1) if abs(di1) > 1e-12 else (0.0, 0.0)
    a_i0 = ang(i0 / i2) if abs(i2) > 1e-12 else (0.0, 0.0)

    ivals = [abs(an.phasor("I" + p, idx)) for p in "ABC"]
    vvals = [abs(an.phasor("V" + p, idx)) for p in "ABC"]
    vpre = [max(abs(an.ref.get("V" + p, 0j)), 1e-9) for p in "ABC"]
    imax = max(max(ivals), 1e-9)

    return {
        "r2": abs(i2) / d,
        "r0": abs(i0) / d,
        "ang_i2_di1_cos": a_i2[0], "ang_i2_di1_sin": a_i2[1],
        "ang_i0_i2_cos": a_i0[0], "ang_i0_i2_sin": a_i0[1],
        "ia_rel": ivals[0] / imax, "ib_rel": ivals[1] / imax, "ic_rel": ivals[2] / imax,
        "va_sag": vvals[0] / vpre[0], "vb_sag": vvals[1] / vpre[1],
        "vc_sag": vvals[2] / vpre[2],
        "i_unbalance": (max(ivals) - min(ivals)) / imax,
        "v_unbalance": (max(vvals) - min(vvals)) / max(max(vvals), 1e-9),
    }


def saturation_features(x: np.ndarray, fs: float, freq: float,
                        lo: int, hi: int) -> Dict[str, float]:
    """Features for CT-saturation detection on one current channel."""
    n = max(int(round(fs / freq)), 4)
    seg = np.asarray(x[lo:hi], dtype=float)
    if seg.size < 2 * n:
        return {k: 0.0 for k in SAT_FEATURES}
    amp = max(float(np.max(np.abs(seg))), 1e-9)
    d3 = seg[3:] - 3.0 * seg[2:-1] + 3.0 * seg[1:-2] - seg[:-3]
    bound = amp * (2.0 * math.sin(math.pi / n)) ** 3

    w = np.fft.rfft(seg[: (seg.size // n) * n] * np.hanning((seg.size // n) * n))
    kf = max(int(round((seg.size // n) * n / n)), 1)
    mag = np.abs(w)
    f1 = float(mag[kf]) if kf < mag.size else 1e-9
    h2 = float(mag[2 * kf]) if 2 * kf < mag.size else 0.0
    h3 = float(mag[3 * kf]) if 3 * kf < mag.size else 0.0

    pos = seg[seg > 0].sum()
    neg = -seg[seg < 0].sum()
    area = min(pos, neg) / max(pos, neg, 1e-9)

    # a saturating CT flattens near the peak: compare the top decile spread
    top = np.sort(np.abs(seg))[-max(seg.size // 10, 2):]
    flat = 1.0 - float(np.std(top) / max(np.mean(top), 1e-9))

    return {
        "d3_ratio": float(np.max(np.abs(d3))) / max(bound, 1e-12),
        "crest": amp / max(float(np.sqrt(np.mean(seg ** 2))), 1e-9),
        "h2_ratio": h2 / max(f1, 1e-9),
        "h3_ratio": h3 / max(f1, 1e-9),
        "half_cycle_area_ratio": area,
        "peak_flatness": flat,
    }


def _vec(d: Dict[str, float], names: Sequence[str]) -> List[float]:
    return [float(d.get(k, 0.0)) for k in names]


# --------------------------------------------------------------------------
# models
# --------------------------------------------------------------------------
@dataclass
class Model:
    kind: str
    features: Tuple[str, ...]
    clf: object = None
    classes: Tuple[str, ...] = ()
    metrics: Dict[str, float] = field(default_factory=dict)

    def predict(self, feats: Dict[str, float]) -> Tuple[str, float]:
        if self.clf is None:
            return ("", 0.0)
        x = np.asarray([_vec(feats, self.features)], dtype=float)
        proba = self.clf.predict_proba(x)[0]
        k = int(np.argmax(proba))
        return (str(self.clf.classes_[k]), float(proba[k]))

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        with open(path, "wb") as fh:
            pickle.dump(self, fh)

    @staticmethod
    def load(path: str) -> "Model":
        with open(path, "rb") as fh:
            return pickle.load(fh)


def _fit(X: np.ndarray, y: np.ndarray, kind: str, features, seed: int = 0) -> Model:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import cross_val_score

    clf = RandomForestClassifier(n_estimators=300, min_samples_leaf=2,
                                 random_state=seed, n_jobs=-1)
    scores = cross_val_score(clf, X, y, cv=min(5, len(set(y.tolist()))), n_jobs=-1) \
        if len(set(y.tolist())) > 1 else np.array([float("nan")])
    clf.fit(X, y)
    imp = dict(zip(features, clf.feature_importances_.tolist()))
    return Model(kind=kind, features=tuple(features), clf=clf,
                 classes=tuple(sorted(set(y.tolist()))),
                 metrics={"cv_accuracy": float(np.nanmean(scores)),
                          "n_samples": float(X.shape[0]),
                          **{"imp_" + k: v for k, v in imp.items()}})


def train_fault_type(n_per_class: int = 60, seed: int = 0, progress=None) -> Model:
    """Train the fault-type classifier on synthetic faults."""
    from ..dsp.pipeline import analyse
    from ..synth.generator import SynthSpec, TerminalSpec, generate

    rng = np.random.default_rng(seed)
    X, y = [], []
    for cls in FAULT_CLASSES:
        for k in range(n_per_class):
            rf = float(rng.uniform(0.2, 40.0)) if cls.endswith("G") or cls in ("AG", "BG", "CG") \
                else float(rng.uniform(0.1, 5.0))
            spec = SynthSpec(
                m=float(rng.uniform(0.03, 0.97)), fault=cls, rf=rf,
                load_angle_deg=float(rng.uniform(-25, 25)),
                source_ratio_R=float(rng.uniform(0.9, 1.1)),
                inception_angle_deg=float(rng.uniform(0, 360)),
                zs1_S=complex(1.0, float(rng.uniform(4, 40))),
                zs1_R=complex(1.5, float(rng.uniform(4, 40))),
                seed=int(rng.integers(0, 10 ** 6)),
                S=TerminalSpec(fs=1000.0, prefault_s=0.12, post_s=0.2,
                               breaker_time_s=0.060,
                               ct_saturation=bool(rng.random() < 0.25)),
                R=TerminalSpec(fs=1200.0, prefault_s=0.14, post_s=0.2,
                               breaker_time_s=0.060, sample_phase=0.37),
            )
            case = generate(spec)
            for end in ("S", "R"):
                try:
                    an = analyse(case.records[end])
                except Exception:
                    continue
                if an.inception is None:
                    continue
                X.append(_vec(fault_features(an), FAULT_FEATURES))
                y.append(cls)
        if progress:
            progress(cls)
    return _fit(np.asarray(X, dtype=float), np.asarray(y), "fault_type", FAULT_FEATURES, seed)


def train_ct_saturation(n_cases: int = 200, seed: int = 0) -> Model:
    """Train the CT-saturation detector on synthetic saturated / clean pairs."""
    from ..synth.generator import SynthSpec, TerminalSpec, generate

    rng = np.random.default_rng(seed + 1)
    X, y = [], []
    for k in range(n_cases):
        sat = bool(k % 2)
        knee = float(rng.uniform(0.4, 3.0)) if sat else 50.0
        spec = SynthSpec(
            m=float(rng.uniform(0.03, 0.97)),
            fault=str(rng.choice(list(FAULT_CLASSES))),
            rf=float(rng.uniform(0.1, 20.0)),
            inception_angle_deg=float(rng.uniform(0, 360)),
            seed=int(rng.integers(0, 10 ** 6)),
            S=TerminalSpec(fs=1000.0, prefault_s=0.12, post_s=0.2,
                           breaker_time_s=0.060, ct_saturation=sat, ct_knee_pu=knee),
            R=TerminalSpec(fs=1200.0, prefault_s=0.14, post_s=0.2, breaker_time_s=0.060),
        )
        case = generate(spec)
        rec = case.records["S"]
        n = int(round(rec.fs / rec.line_freq))
        lo = int(0.12 * rec.fs) + n // 4
        hi = min(lo + 3 * n, rec.n)
        for ch in ("IA", "IB", "IC"):
            f = saturation_features(rec.analog[ch], rec.fs, rec.line_freq, lo, hi)
            X.append(_vec(f, SAT_FEATURES))
            y.append("saturated" if sat else "clean")
    return _fit(np.asarray(X, dtype=float), np.asarray(y), "ct_saturation",
                SAT_FEATURES, seed)


@dataclass
class QualityAnomaly:
    """Unsupervised record-quality outlier detector.

    Fitted on records already known to be good, it flags ratio errors,
    polarity errors and channel-mapping drift as the fleet changes, without
    anyone having to enumerate the failure modes in advance.
    """

    clf: object = None
    features: Tuple[str, ...] = FAULT_FEATURES

    def fit(self, feats: Sequence[Dict[str, float]]) -> "QualityAnomaly":
        from sklearn.ensemble import IsolationForest

        X = np.asarray([_vec(f, self.features) for f in feats], dtype=float)
        self.clf = IsolationForest(n_estimators=200, contamination=0.05,
                                   random_state=0).fit(X)
        return self

    def score(self, f: Dict[str, float]) -> float:
        """More negative is more anomalous."""
        if self.clf is None:
            return 0.0
        return float(self.clf.decision_function(
            np.asarray([_vec(f, self.features)], dtype=float))[0])


def second_opinion(an: Analysed, model: Optional[Model]) -> Optional[str]:
    """Compare the learned fault type against the physics classifier.

    Returns a finding string when they disagree, otherwise None. The physics
    answer is not overridden.
    """
    if model is None or model.clf is None:
        return None
    pred, conf = model.predict(fault_features(an))
    if pred and pred != an.fault_type and conf > 0.7:
        return ("FT-ML fault type disagreement: physics says " + an.fault_type
                + ", the learned classifier says " + pred + " with confidence "
                + format(conf, ".2f") + ". Physics is used; check the record.")
    return None
