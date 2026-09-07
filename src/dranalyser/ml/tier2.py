"""Tier 2 - hierarchical residual correction, pooled across the fleet.

GATED. This model does not fit, and does not ship, until the fleet has at
least 100 patrol-confirmed events. Below that it returns the physics answer
unchanged and says why. That is deliberate: a per-line fit on five confirmed
faults will look excellent on those five and move the sixth in the wrong
direction while carrying the authority of a model.

Structure
---------
residual  e = m_true - m_model   in per unit of line length.

  fixed effects   features available at prediction time -- fault type,
                  estimated R_F, source-impedance ratio at each end,
                  pre-fault load angle, m itself (catches reach
                  non-linearity), |I2|/|I1|, saturation flags, window length
                  in cycles, season.

  random effects  per line, TWO parameters: a scalar correction on X1 per km
                  and a scalar correction on the k0 magnitude. Two, not
                  thousands. A line with one confirmed fault contributes
                  almost nothing and shrinks to the fleet mean; a line with
                  fifteen gets a real correction.

  output          a corrected distance WITH a posterior interval. The
                  interval is the product, not the point estimate.

Partial pooling is done explicitly (a James-Stein / empirical-Bayes shrink
towards the fleet mean) rather than through a sampler, so the correction each
line receives is a number a protection engineer can read and argue with.

Guardrails, non-negotiable:
  (a) the correction is capped at min(2 % of line length, 1.5 km). The brief
      says 2 %; on a 300 km line that is 6 km, about twenty spans, which is
      not a guardrail, so the absolute cap is added.
  (b) the raw physics estimate is always carried alongside the corrected one.
  (c) validation is leave-one-LINE-out, never a random split, and the model
      ships only if it beats the raw two-ended estimate on held-out lines.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

MIN_GROUND_TRUTH = 100
CAP_FRACTION = 0.02
CAP_KM = 1.5

FIXED_FEATURES = (
    "m", "m_sq", "rf_ohm", "sir_S", "sir_R", "load_angle_deg",
    "r2_over_r1", "sat_S", "sat_R", "window_cycles", "is_ground", "is_three_phase",
    "season_sin", "season_cos",
)


@dataclass
class GroundTruthEvent:
    """One patrol-confirmed incident. The scarcest data in the system."""

    line_id: str
    m_true: float
    m_model: float
    line_km: float
    features: Dict[str, float] = field(default_factory=dict)
    two_ended: bool = True


@dataclass
class Correction:
    m_raw: float
    m_corrected: float
    delta_pu: float
    interval_pu: Tuple[float, float]
    capped: bool
    applied: bool
    reason: str

    def report(self, line_km: float) -> str:
        if not self.applied:
            return "Tier 2 not applied: " + self.reason
        return ("Tier 2 residual correction: raw "
                + format(self.m_raw * line_km, ".3f") + " km -> corrected "
                + format(self.m_corrected * line_km, ".3f") + " km ("
                + format(self.delta_pu * line_km * 1000.0, "+.0f") + " m"
                + (", CAPPED" if self.capped else "") + "), 90 % interval "
                + format(self.interval_pu[0] * line_km, ".3f") + " to "
                + format(self.interval_pu[1] * line_km, ".3f") + " km")


@dataclass
class ResidualModel:
    beta: Optional[np.ndarray] = None
    line_effect: Dict[str, float] = field(default_factory=dict)
    line_n: Dict[str, int] = field(default_factory=dict)
    sigma_within: float = 0.0
    sigma_between: float = 0.0
    fitted: bool = False
    n_events: int = 0
    reason: str = "not fitted"
    ridge: float = 1.0

    # ---- fitting ---------------------------------------------------------
    def fit(self, events: Sequence[GroundTruthEvent],
            min_events: int = MIN_GROUND_TRUTH) -> "ResidualModel":
        self.n_events = len(events)
        if len(events) < min_events:
            self.fitted = False
            self.reason = ("gated: " + str(len(events)) + " confirmed events, "
                           + str(min_events) + " required. Below that a fit "
                           "memorises rather than generalises.")
            return self

        X = np.asarray([_row(e) for e in events], dtype=float)
        y = np.asarray([e.m_true - e.m_model for e in events], dtype=float)
        Xc = np.hstack([np.ones((X.shape[0], 1)), X])

        # ridge-regularised fixed effects
        A = Xc.T @ Xc + self.ridge * np.eye(Xc.shape[1])
        A[0, 0] -= self.ridge                      # do not penalise the intercept
        self.beta = np.linalg.solve(A, Xc.T @ y)
        resid = y - Xc @ self.beta

        # empirical-Bayes per-line shrinkage of the leftover residual
        by: Dict[str, List[float]] = {}
        for e, r in zip(events, resid):
            by.setdefault(e.line_id, []).append(float(r))
        means = {k: float(np.mean(v)) for k, v in by.items()}
        self.line_n = {k: len(v) for k, v in by.items()}
        self.sigma_within = float(np.std(resid)) or 1e-6
        self.sigma_between = max(float(np.std(list(means.values()))), 1e-9)

        tau2, s2 = self.sigma_between ** 2, self.sigma_within ** 2
        self.line_effect = {}
        for k, mu in means.items():
            n = self.line_n[k]
            shrink = tau2 / (tau2 + s2 / n)        # 0 = fleet mean, 1 = own mean
            self.line_effect[k] = shrink * mu
        self.fitted = True
        self.reason = ("fitted on " + str(len(events)) + " confirmed events across "
                       + str(len(by)) + " lines")
        return self

    # ---- prediction ------------------------------------------------------
    def correct(self, m_raw: float, line_id: str, line_km: float,
                features: Dict[str, float]) -> Correction:
        if not self.fitted or self.beta is None:
            return Correction(m_raw=m_raw, m_corrected=m_raw, delta_pu=0.0,
                              interval_pu=(m_raw, m_raw), capped=False,
                              applied=False, reason=self.reason)
        x = np.concatenate([[1.0], _row_from(features, m_raw)])
        delta = float(x @ self.beta) + self.line_effect.get(line_id, 0.0)

        cap = min(CAP_FRACTION, CAP_KM / max(line_km, 1e-6))
        capped = abs(delta) > cap
        if capped:
            delta = math.copysign(cap, delta)

        m_new = float(np.clip(m_raw + delta, 0.0, 1.0))
        half = 1.645 * self.sigma_within
        if self.line_n.get(line_id, 0) < 3:
            half *= 1.5           # a line with almost no history gets a wider band
        return Correction(m_raw=m_raw, m_corrected=m_new, delta_pu=delta,
                          interval_pu=(max(m_new - half, 0.0), min(m_new + half, 1.0)),
                          capped=capped, applied=True, reason=self.reason)

    def line_report(self) -> str:
        if not self.fitted:
            return "Tier 2: " + self.reason
        rows = ["Tier 2 residual model - " + self.reason,
                "  within-line sigma  : " + format(self.sigma_within, ".4f") + " pu",
                "  between-line sigma : " + format(self.sigma_between, ".4f") + " pu",
                "  per-line corrections (shrunk towards the fleet mean):"]
        for k in sorted(self.line_effect, key=lambda z: -abs(self.line_effect[z]))[:12]:
            rows.append("    " + format(k, "<16") + " n=" + format(self.line_n[k], "<4")
                        + " effect " + format(self.line_effect[k] * 100.0, "+.3f") + " % of line")
        return "\n".join(rows)


def _row_from(f: Dict[str, float], m: float) -> np.ndarray:
    g = dict(f)
    g["m"] = m
    g["m_sq"] = m * m
    return np.asarray([float(g.get(k, 0.0)) for k in FIXED_FEATURES], dtype=float)


def _row(e: GroundTruthEvent) -> np.ndarray:
    return _row_from(e.features, e.m_model)


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------
MIN_RELATIVE_GAIN = 0.10


@dataclass
class Validation:
    mae_raw_pu: float
    mae_model_pu: float
    p90_raw_pu: float
    p90_model_pu: float
    n_lines: int
    n_events: int
    ships: bool
    relative_gain: float = 0.0
    gain_ci_low: float = 0.0
    reason: str = ""

    def report(self, mean_line_km: float = 100.0) -> str:
        return "\n".join([
            "Leave-one-line-out validation over " + str(self.n_events)
            + " events, " + str(self.n_lines) + " lines",
            "  baseline (raw two-ended)  MAE " + format(self.mae_raw_pu * 100, ".3f")
            + " %   p90 " + format(self.p90_raw_pu * 100, ".3f") + " %",
            "  Tier 2 corrected          MAE " + format(self.mae_model_pu * 100, ".3f")
            + " %   p90 " + format(self.p90_model_pu * 100, ".3f") + " %",
            "  relative gain             " + format(self.relative_gain * 100, ".1f")
            + " %  (5th pct of paired bootstrap: "
            + format(self.gain_ci_low * 100, "+.1f") + " %)",
            "  ships: " + ("YES" if self.ships else "NO - " + self.reason),
        ])


def leave_one_line_out(events: Sequence[GroundTruthEvent],
                       min_events: int = MIN_GROUND_TRUTH) -> Validation:
    """The only honest validation for this problem.

    A random split leaks the same line's events across train and test and
    flatters the model badly, because the per-line random effect is exactly
    what is being tested.
    """
    lines = sorted({e.line_id for e in events})
    raw, mod = [], []
    for held in lines:
        train = [e for e in events if e.line_id != held]
        test = [e for e in events if e.line_id == held]
        m = ResidualModel().fit(train, min_events=min_events)
        for e in test:
            raw.append(abs(e.m_true - e.m_model))
            c = m.correct(e.m_model, e.line_id, e.line_km, e.features)
            mod.append(abs(e.m_true - c.m_corrected))
    r = np.asarray(raw) if raw else np.asarray([float("nan")])
    q = np.asarray(mod) if mod else np.asarray([float("nan")])
    mae_r, mae_q = float(np.mean(r)), float(np.mean(q))
    p90_r, p90_q = float(np.percentile(r, 90)), float(np.percentile(q, 90))
    gain = (mae_r - mae_q) / mae_r if mae_r > 0 else 0.0

    # "Beats the baseline" is not enough on its own. Capping a correction at
    # +/-2 % pulls every estimate slightly towards the fleet mean, which
    # shrinks MAE by a percent or two even on pure noise. So the gain has to
    # be both MATERIAL and repeatable: a minimum effect size, plus a paired
    # bootstrap whose 5th percentile is still an improvement.
    rng = np.random.default_rng(0)
    d = r - q
    n = d.size
    boots = np.asarray([
        float(np.mean(d[rng.integers(0, n, n)])) for _ in range(400)
    ]) if n > 1 else np.asarray([0.0])
    ci_low = float(np.percentile(boots, 5)) / mae_r if mae_r > 0 else 0.0

    ships, why = True, ""
    if not (mae_q < mae_r):
        ships, why = False, "it does not beat the raw two-ended estimate on held-out lines"
    elif p90_q > p90_r:
        ships, why = False, ("the 90th-percentile error gets worse; the tail is what "
                             "destroys credibility with the patrol team")
    elif gain < MIN_RELATIVE_GAIN:
        ships, why = False, ("the gain is only " + format(gain * 100, ".1f")
                             + " %, under the " + format(MIN_RELATIVE_GAIN * 100, ".0f")
                             + " % minimum effect size; shrinkage towards the fleet "
                             "mean produces that much on noise alone")
    elif ci_low <= 0.0:
        ships, why = False, ("the improvement is not distinguishable from chance "
                             "(5th percentile of the paired bootstrap is "
                             + format(ci_low * 100, "+.1f") + " %)")

    return Validation(mae_raw_pu=mae_r, mae_model_pu=mae_q,
                      p90_raw_pu=p90_r, p90_model_pu=p90_q,
                      n_lines=len(lines), n_events=len(events),
                      ships=ships, relative_gain=gain, gain_ci_low=ci_low,
                      reason=why)
