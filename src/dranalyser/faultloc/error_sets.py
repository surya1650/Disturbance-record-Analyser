"""Offline necessary E5 sets under caller-declared absolute phasor error circles.

Exact passive uncoupled series Z2=Z1 model; BOTH currents enter the line.
No shunts/taps/internal sources. Provenance strings are declarations, not proof.
Numerical outer sets are neither formal floating intervals nor confidence bounds.
"""
from dataclasses import dataclass
import math
from numbers import Complex, Real


@dataclass(frozen=True)
class BoundedTerminal:
    voltage: complex
    current: complex
    voltage_radius: float | None
    current_radius: float | None
    provenance: str | None


@dataclass(frozen=True)
class PairedObservation:
    s: BoundedTerminal
    r: BoundedTerminal


@dataclass(frozen=True)
class SeriesSection:
    end: float
    impedance: complex


def _real(value):
    try:
        # A relative-epsilon guard cannot certify arithmetic on subnormal data.
        return (isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value)
                and (value == 0 or abs(value) >= float.fromhex('0x1.0p-1022')))
    except (OverflowError, TypeError, ValueError):
        return False


def _complex(value):
    try:
        return (isinstance(value, Complex) and not isinstance(value, bool)
                and _real(value.real) and _real(value.imag) and math.isfinite(abs(value)))
    except (OverflowError, TypeError, ValueError):
        return False


def _provenance(value):
    return isinstance(value, str) and bool(value.strip())


def _terminal(t):
    return (isinstance(t, BoundedTerminal) and _complex(t.voltage) and _complex(t.current)
            and all(_real(v) and v >= 0 for v in (t.voltage_radius, t.current_radius))
            and _provenance(t.provenance))


def _product(a, b):
    value = a*b
    if not _complex(value) or (a != 0 and b != 0 and value == 0):
        raise ArithmeticError('Unrepresentable or subnormal propagated error/voltage scale.')
    return value


def _prepare(pair, sections):
    """Normalized section voltage drops/radii, with conservative triangle sums."""
    ds = [_product(z.impedance, pair.s.current) for z in sections]
    dr = [_product(z.impedance, pair.r.current) for z in sections]
    qs = [_product(abs(z.impedance), pair.s.current_radius) for z in sections]
    qr = [_product(abs(z.impedance), pair.r.current_radius) for z in sections]
    vs, vr = pair.s.voltage, pair.r.voltage
    rvs, rvr = pair.s.voltage_radius, pair.r.voltage_radius
    scale = max(abs(vs), abs(vr), rvs, rvr, math.fsum(map(abs, ds)),
                math.fsum(map(abs, dr)), math.fsum(qs), math.fsum(qr))
    if not math.isfinite(scale):
        raise ArithmeticError('Nonfinite normalization scale.')
    scale = scale or 1.0
    values = [vs, vr, rvs, rvr, *ds, *dr, *qs, *qr]
    if any(v != 0 and v/scale == 0 for v in values):
        raise ArithmeticError('Unrepresentable normalized voltage/error scale.')
    vs, vr, rvs, rvr = (v/scale for v in (vs, vr, rvs, rvr))
    ds, dr, qs, qr = [[v/scale for v in group] for group in (ds, dr, qs, qr)]
    terms = []
    for j in range(len(sections)):
        a, c = vs-sum(ds[:j]), vr-sum(dr[j+1:])
        radius = rvs+rvr+math.fsum(qs[:j])+math.fsum(qr[j+1:])
        lip = abs(ds[j])+abs(dr[j])+qs[j]+qr[j]
        terms.append((a, ds[j], c, dr[j], radius, qs[j], qr[j], lip))
    return terms


def _g(term, u):
    a, b, c, d, radius, qs, qr, _ = term
    return abs(abs(a-u*b)-abs(c-(1-u)*d))-(radius+u*qs+(1-u)*qr)


def _merge(intervals):
    merged = []
    for lo, hi in sorted(intervals):
        if merged and lo <= merged[-1][1]:
            merged[-1][1] = max(hi, merged[-1][1])
        else:
            merged.append([lo, hi])
    return merged


def e5_error_feasible(observations, *, sections, model_provenance,
                      resolution=1/1024, max_boxes=100000):
    """Return necessary physical-chainage sets; never select or authorize a point.

    All supports constrain the intersection, but their unknown phase offsets need
    not agree. A nonempty set therefore does not prove a common physical solution.
    Supplied radii must cover every claimed measurement error; they are not inferred.
    """
    out = dict(status='withheld', reason='', intervals_pu=[], total_width_pu=0.0,
               boxes_evaluated=0, research_only=True, authorizes_location=False,
               numerical_guard_normalized=None, model='exact passive series Z2=Z1',
               provenance_authenticated=False, common_phase_enforced=False)
    if (not _real(resolution) or not 1e-6 <= resolution <= 1
            or type(max_boxes) is not int or not 1 <= max_boxes <= 200000):
        out['reason'] = 'Invalid resolution or box budget.'
        return out
    if not _provenance(model_provenance):
        out['reason'] = 'Explicit model provenance declaration required.'
        return out
    if (not isinstance(observations, (list, tuple)) or not 1 <= len(observations) <= 256
            or any(not isinstance(o, PairedObservation) or not _terminal(o.s)
                   or not _terminal(o.r) for o in observations)):
        out['reason'] = 'Require 1..256 finite paired observations with explicit caps/provenance.'
        return out
    if not isinstance(sections, (list, tuple)) or not 1 <= len(sections) <= 64:
        out['reason'] = 'Require 1..64 complete passive series sections.'
        return out
    previous = 0.0
    for section in sections:
        if (not isinstance(section, SeriesSection) or not _real(section.end)
                or not previous < section.end <= 1 or not _complex(section.impedance)
                or section.impedance.real < 0 or section.impedance.imag <= 0):
            out['reason'] = 'Invalid passive section impedance or physical chainage endpoints.'
            return out
        previous = float(section.end)
    if previous != 1:
        out['reason'] = 'Section endpoints must cover the entire physical line through 1.'
        return out
    try:
        prepared = [_prepare(o, sections) for o in observations]
    except (ArithmeticError, OverflowError, ValueError) as exc:
        out['reason'] = str(exc)
        return out
    guard = 256*math.ulp(1.0)*(len(sections)+1)
    out['numerical_guard_normalized'] = guard
    out['support_count'] = len(observations)
    out['section_count'] = len(sections)
    edges = [0.0, *[float(s.end) for s in sections]]
    stack = [(j, 0.0, 1.0) for j in reversed(range(len(sections)))]
    retained = []

    def interval(box):
        j, lo, hi = box
        start, end = edges[j:j+2]
        return [start+(end-start)*lo, end if hi == 1 else start+(end-start)*hi]

    while stack and out['boxes_evaluated'] < max_boxes:
        box = stack.pop()
        j, lo, hi = box
        mid, half = (lo+hi)/2, (hi-lo)/2
        out['boxes_evaluated'] += 1
        margins = [(_g(p[j], mid), p[j][-1]*half) for p in prepared]
        if any(g > movement+guard for g, movement in margins):
            continue
        if ((hi-lo)*(edges[j+1]-edges[j]) <= resolution
                or all(g+movement <= guard for g, movement in margins)):
            retained.append(interval(box))
        else:
            stack.extend([(j, mid, hi), (j, lo, mid)])
    limited = bool(stack)
    retained.extend(interval(box) for box in stack)
    intervals = _merge(retained)
    width = math.fsum(hi-lo for lo, hi in intervals)
    if limited:
        status, reason = 'resource_limited', 'All unresolved boxes retained; budget exhausted.'
    elif not intervals:
        status, reason = 'inconsistent', 'Empty necessary set conditional on supplied caps/model.'
    elif intervals == [[0.0, 1.0]]:
        status, reason = 'uninformative', 'Necessary set covers the entire physical line.'
    elif len(intervals) > 1:
        status, reason = 'ambiguous', 'Multiple necessary-set components; no point selection.'
    else:
        status, reason = 'outer_set', 'One necessary-set component; no location authorization.'
    out.update(status=status, reason=reason, intervals_pu=intervals, total_width_pu=width)
    return out
