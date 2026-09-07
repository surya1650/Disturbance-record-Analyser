"""Inline SVG for the two-page report.

Everything is hand-built SVG with no plotting dependency, so a report is a
single self-contained HTML file that renders in any browser on an isolated
network and converts to PDF with WeasyPrint when one is available.

Phase colours follow the Indian R/Y/B convention, because the people reading
this work in R/Y/B and a report that colours phase C blue while calling it C
is a small, constant source of confusion.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

PHASE_COLOUR = {"A": "#c0392b", "B": "#b7950b", "C": "#2471a3"}
PHASE_LABEL = {"A": "R", "B": "Y", "C": "B"}
GRID = "#dfe3e6"
AXIS = "#6b7780"
INK = "#1b2733"
MUTED = "#7a8894"
EVENT = "#8e44ad"


def esc(s: object) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


@dataclass
class Frame:
    """Maps data coordinates to pixels inside a plot box."""

    x0: float
    y0: float
    w: float
    h: float
    xmin: float
    xmax: float
    ymin: float
    ymax: float

    def px(self, x: float) -> float:
        if self.xmax == self.xmin:
            return self.x0
        return self.x0 + (x - self.xmin) / (self.xmax - self.xmin) * self.w

    def py(self, y: float) -> float:
        if self.ymax == self.ymin:
            return self.y0 + self.h / 2.0
        return self.y0 + self.h - (y - self.ymin) / (self.ymax - self.ymin) * self.h

    def path(self, xs: Sequence[float], ys: Sequence[float]) -> str:
        pts = []
        for x, y in zip(xs, ys):
            if not (math.isfinite(x) and math.isfinite(y)):
                continue
            pts.append(format(self.px(x), ".1f") + "," + format(self.py(y), ".1f"))
        return " ".join(pts)


def _nice(v: float) -> float:
    """A round number at or above v, for axis limits."""
    if v <= 0:
        return 1.0
    e = math.floor(math.log10(v))
    b = v / (10 ** e)
    step = 1.0 if b <= 1 else 2.0 if b <= 2 else 5.0 if b <= 5 else 10.0
    return step * (10 ** e)


def _axes(f: Frame, xlabel: str, ylabel: str, nx: int = 6, ny: int = 4) -> str:
    out = []
    for i in range(nx + 1):
        x = f.xmin + (f.xmax - f.xmin) * i / nx
        px = f.px(x)
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
                   'stroke-width="0.6"/>' % (px, f.y0, px, f.y0 + f.h, GRID))
        out.append('<text x="%.1f" y="%.1f" font-size="8" fill="%s" '
                   'text-anchor="middle">%s</text>'
                   % (px, f.y0 + f.h + 11, MUTED, format(x, ".0f")))
    for i in range(ny + 1):
        y = f.ymin + (f.ymax - f.ymin) * i / ny
        py = f.py(y)
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
                   'stroke-width="0.6"/>' % (f.x0, py, f.x0 + f.w, py, GRID))
        out.append('<text x="%.1f" y="%.1f" font-size="8" fill="%s" '
                   'text-anchor="end">%s</text>'
                   % (f.x0 - 4, py + 3, MUTED, format(y, ".4g")))
    out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="none" '
               'stroke="%s" stroke-width="0.8"/>' % (f.x0, f.y0, f.w, f.h, AXIS))
    out.append('<text x="%.1f" y="%.1f" font-size="8.5" fill="%s" '
               'text-anchor="middle">%s</text>'
               % (f.x0 + f.w / 2, f.y0 + f.h + 24, INK, esc(xlabel)))
    out.append('<text x="%.1f" y="%.1f" font-size="8.5" fill="%s" '
               'text-anchor="middle" transform="rotate(-90 %.1f %.1f)">%s</text>'
               % (f.x0 - 34, f.y0 + f.h / 2, INK, f.x0 - 34, f.y0 + f.h / 2, esc(ylabel)))
    return "".join(out)


def _events(f: Frame, events: Sequence[Tuple[float, str]]) -> str:
    out = []
    for t, label in events:
        if not (f.xmin <= t <= f.xmax):
            continue
        px = f.px(t)
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
                   'stroke-width="0.9" stroke-dasharray="3,2"/>'
                   % (px, f.y0, px, f.y0 + f.h, EVENT))
        out.append('<text x="%.1f" y="%.1f" font-size="7.5" fill="%s" '
                   'text-anchor="middle">%s</text>'
                   % (px, f.y0 - 3, EVENT, esc(label)))
    return "".join(out)


# --------------------------------------------------------------------------
def oscillogram(
    panels: Sequence[Dict[str, object]], width: int = 720, panel_h: int = 110,
) -> str:
    """Stacked current and voltage panels on one time axis.

    Each panel is {title, t_ms, traces {phase: array}, unit, events}.
    Time is milliseconds from fault inception, which is the only reference
    that means the same thing at both terminals.
    """
    if not panels:
        return ""
    left, right, top, gap = 52, 14, 18, 40
    height = top + len(panels) * (panel_h + gap)
    out = ['<svg viewBox="0 0 %d %d" width="100%%" xmlns="http://www.w3.org/2000/svg" '
           'font-family="Segoe UI,Helvetica,Arial,sans-serif">' % (width, height)]
    xmin = min(float(np.min(p["t_ms"])) for p in panels if len(p["t_ms"]))
    xmax = max(float(np.max(p["t_ms"])) for p in panels if len(p["t_ms"]))
    for i, p in enumerate(panels):
        y0 = top + i * (panel_h + gap)
        amp = 0.0
        for arr in p["traces"].values():
            if len(arr):
                amp = max(amp, float(np.max(np.abs(arr))))
        lim = _nice(amp * 1.1) if amp > 0 else 1.0
        f = Frame(left, y0, width - left - right, panel_h, xmin, xmax, -lim, lim)
        out.append(_axes(f, "ms from fault inception", str(p["unit"])))
        out.append('<text x="%.1f" y="%.1f" font-size="9.5" font-weight="600" '
                   'fill="%s">%s</text>' % (left, y0 - 6, INK, esc(p["title"])))
        for ph, arr in p["traces"].items():
            if not len(arr):
                continue
            out.append('<polyline points="%s" fill="none" stroke="%s" '
                       'stroke-width="1.0" stroke-linejoin="round"/>'
                       % (f.path(p["t_ms"], arr), PHASE_COLOUR.get(ph, INK)))
        out.append(_events(f, p.get("events", ())))
        lx = width - right - 96
        for j, ph in enumerate("ABC"):
            if ph in p["traces"]:
                out.append('<rect x="%.1f" y="%.1f" width="8" height="3" fill="%s"/>'
                           % (lx + j * 30, y0 + 6, PHASE_COLOUR[ph]))
                out.append('<text x="%.1f" y="%.1f" font-size="8" fill="%s">%s</text>'
                           % (lx + j * 30 + 11, y0 + 9, INK, PHASE_LABEL[ph]))
    out.append("</svg>")
    return "".join(out)


def digital_timeline(
    rows: Sequence[Tuple[str, str, Sequence[Tuple[float, float]]]],
    t0_ms: float, t1_ms: float, width: int = 720,
) -> str:
    """One bar per canonical signal, per terminal.

    rows are (end, signal, [(start_ms, end_ms), ...]).
    """
    if not rows:
        return '<p class="muted">No digital channels mapped.</p>'
    left, right, top, rh = 132, 14, 16, 13
    height = top + len(rows) * rh + 34
    f = Frame(left, top, width - left - right, len(rows) * rh, t0_ms, t1_ms, 0, 1)
    out = ['<svg viewBox="0 0 %d %d" width="100%%" xmlns="http://www.w3.org/2000/svg" '
           'font-family="Segoe UI,Helvetica,Arial,sans-serif">' % (width, height)]
    for i in range(7):
        t = t0_ms + (t1_ms - t0_ms) * i / 6.0
        px = f.px(t)
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
                   'stroke-width="0.6"/>' % (px, top, px, top + len(rows) * rh, GRID))
        out.append('<text x="%.1f" y="%.1f" font-size="8" fill="%s" '
                   'text-anchor="middle">%s</text>'
                   % (px, top + len(rows) * rh + 12, MUTED, format(t, ".0f")))
    out.append('<text x="%.1f" y="%.1f" font-size="8.5" fill="%s" '
               'text-anchor="middle">ms from fault inception</text>'
               % (left + f.w / 2, top + len(rows) * rh + 26, INK))
    for i, (end, sig, spans) in enumerate(rows):
        y = top + i * rh
        out.append('<text x="4" y="%.1f" font-size="8" fill="%s">%s</text>'
                   % (y + 9, INK, esc(end + "  " + sig)))
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
                   'stroke-width="0.5"/>'
                   % (left, y + rh - 2, left + f.w, y + rh - 2, GRID))
        for a, b in spans:
            xa, xb = f.px(max(a, t0_ms)), f.px(min(b, t1_ms))
            if xb <= xa:
                xb = xa + 1.2
            out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#2e7d32" '
                       'opacity="0.85" rx="1"/>' % (xa, y + 2, xb - xa, rh - 6))
    out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
               'stroke-width="1"/>' % (f.px(0.0), top, f.px(0.0), top + len(rows) * rh, EVENT))
    out.append("</svg>")
    return "".join(out)


def rx_diagram(
    zones: Sequence[Dict[str, object]], trajectory: Sequence[complex],
    line_angle_deg: float, reach_points: Sequence[Tuple[str, complex]] = (),
    width: int = 420, height: int = 380,
) -> str:
    """Apparent impedance against the relay's actual characteristic.

    Everything is in SECONDARY ohm, which is what the relay settings are in;
    converting the trajectory to primary and the polygons to secondary is the
    classic way to draw a picture that looks right and is wrong by the ratio.
    """
    pts = [z for z in trajectory if z is not None and math.isfinite(z.real)]
    if not pts and not zones:
        # Nothing to draw. An empty set of axes looks like a measurement that
        # sat at the origin, which is a different and much worse claim.
        return ('<p class="muted">No impedance trajectory available: this needs a '
                'relay settings export next to the record.</p>')
    xs = [z.real for z in pts] + [0.0]
    ys = [z.imag for z in pts] + [0.0]
    for zn in zones:
        for r, x in zn["vertices"]:
            xs.append(r)
            ys.append(x)
    for _, z in reach_points:
        xs.append(z.real)
        ys.append(z.imag)
    if not xs:
        return '<p class="muted">No impedance trajectory available.</p>'
    rmax = _nice(max(abs(min(xs)), abs(max(xs))) * 1.1)
    xmax = _nice(max(abs(min(ys)), abs(max(ys))) * 1.1)
    lim = max(rmax, xmax)
    f = Frame(46, 14, width - 60, height - 52, -lim, lim, -lim, lim)
    out = ['<svg viewBox="0 0 %d %d" width="100%%" xmlns="http://www.w3.org/2000/svg" '
           'font-family="Segoe UI,Helvetica,Arial,sans-serif">' % (width, height)]
    out.append(_axes(f, "R, secondary ohm", "X, secondary ohm", nx=4, ny=4))
    out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
               'stroke-width="0.9"/>' % (f.px(-lim), f.py(0), f.px(lim), f.py(0), AXIS))
    out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
               'stroke-width="0.9"/>' % (f.px(0), f.py(-lim), f.px(0), f.py(lim), AXIS))
    a = math.radians(line_angle_deg)
    out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
               'stroke-width="0.8" stroke-dasharray="4,3"/>'
               % (f.px(0), f.py(0), f.px(lim * math.cos(a)), f.py(lim * math.sin(a)), MUTED))
    palette = ["#1f6feb", "#2e7d32", "#b7950b", "#8e44ad", "#7a8894", "#c0392b"]
    for i, zn in enumerate(zones):
        col = palette[i % len(palette)]
        pts_s = " ".join(format(f.px(r), ".1f") + "," + format(f.py(x), ".1f")
                         for r, x in zn["vertices"])
        out.append('<polygon points="%s" fill="%s" fill-opacity="0.05" stroke="%s" '
                   'stroke-width="1"/>' % (pts_s, col, col))
        vr, vx = zn["vertices"][len(zn["vertices"]) // 2]
        out.append('<text x="%.1f" y="%.1f" font-size="8" fill="%s">%s</text>'
                   % (f.px(vr) + 3, f.py(vx) - 3, col, esc(zn["name"])))
    if pts:
        out.append('<polyline points="%s" fill="none" stroke="#111" stroke-width="1.4"/>'
                   % f.path([z.real for z in pts], [z.imag for z in pts]))
        last = pts[-1]
        out.append('<circle cx="%.1f" cy="%.1f" r="3.2" fill="#111"/>'
                   % (f.px(last.real), f.py(last.imag)))
        out.append('<text x="%.1f" y="%.1f" font-size="8" fill="#111">measured</text>'
                   % (f.px(last.real) + 5, f.py(last.imag) + 3))
    out.append("</svg>")
    return "".join(out)


def phasor_diagram(phasors: Dict[str, complex], title: str = "",
                   width: int = 300, height: int = 300) -> str:
    """Sequence or phase phasors at the analysis instant, normalised."""
    vals = [v for v in phasors.values() if v is not None and abs(v) > 0]
    if not vals:
        return ""
    scale = max(abs(v) for v in vals)
    cx, cy, rad = width / 2.0, height / 2.0 + 6, min(width, height) / 2.0 - 34
    out = ['<svg viewBox="0 0 %d %d" width="100%%" xmlns="http://www.w3.org/2000/svg" '
           'font-family="Segoe UI,Helvetica,Arial,sans-serif">' % (width, height)]
    out.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="none" stroke="%s" '
               'stroke-width="0.7"/>' % (cx, cy, rad, GRID))
    for ang in range(0, 360, 30):
        a = math.radians(ang)
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
                   'stroke-width="0.4"/>'
                   % (cx, cy, cx + rad * math.cos(a), cy - rad * math.sin(a), GRID))
    colours = ["#c0392b", "#b7950b", "#2471a3", "#2e7d32", "#8e44ad", "#7a8894"]
    for i, (name, v) in enumerate(phasors.items()):
        if v is None or abs(v) == 0:
            continue
        r = rad * abs(v) / scale
        a = math.atan2(v.imag, v.real)
        x, y = cx + r * math.cos(a), cy - r * math.sin(a)
        col = colours[i % len(colours)]
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
                   'stroke-width="1.6"/>' % (cx, cy, x, y, col))
        out.append('<circle cx="%.1f" cy="%.1f" r="2.2" fill="%s"/>' % (x, y, col))
        out.append('<text x="%.1f" y="%.1f" font-size="8" fill="%s">%s</text>'
                   % (x + 4, y - 2, col, esc(name)))
    if title:
        out.append('<text x="%.1f" y="12" font-size="9" font-weight="600" fill="%s" '
                   'text-anchor="middle">%s</text>' % (cx, INK, esc(title)))
    out.append("</svg>")
    return "".join(out)


def qr_svg(data: str, size: int = 110) -> str:
    """QR for the ground-truth capture link, when a generator is installed.

    Not hand-rolled: a silently wrong QR sends the patrol team's confirmation
    nowhere, and there is no offline decoder here to prove one correct. If no
    generator is available the caller falls back to printing the URL, which is
    typeable, and `pip install segno` turns the code on.
    """
    try:
        import segno                                   # type: ignore

        buf = segno.make(data, error="m").svg_inline(scale=3, border=2)
        return '<div style="width:%dpx">%s</div>' % (size, buf)
    except Exception:                                   # noqa: BLE001
        pass
    try:
        import io as _io

        import qrcode                                   # type: ignore
        import qrcode.image.svg                         # type: ignore

        img = qrcode.make(data, image_factory=qrcode.image.svg.SvgPathImage)
        b = _io.BytesIO()
        img.save(b)
        return '<div style="width:%dpx">%s</div>' % (size, b.getvalue().decode("utf-8"))
    except Exception:                                   # noqa: BLE001
        return ""
