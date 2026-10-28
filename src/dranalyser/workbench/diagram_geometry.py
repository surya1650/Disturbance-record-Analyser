"""Conservative validation for user-declared drawing boundaries."""
import math


def valid_polygon(points):
    points = points[:-1] if points[0] == points[-1] else points
    if len(points) < 3:
        return False
    if len({tuple(p) for p in points}) != len(points):
        return False
    scale = max(abs(v) for p in points for v in p) or 1
    pairs = [(x/scale, y/scale) for x, y in points]
    area = sum(a[0]*b[1]-b[0]*a[1] for a, b in zip(pairs, pairs[1:]+pairs[:1], strict=True))
    if not math.isfinite(area) or abs(area) < 1e-12:
        return False
    def cross(a, b, c):
        return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    edges = list(zip(pairs, pairs[1:]+pairs[:1], strict=True))
    for i, (a, b) in enumerate(edges):
        for j in range(i+1, len(edges)):
            if j == i+1 or (i == 0 and j == len(edges)-1):
                continue
            c, d = edges[j]
            values = cross(a, b, c), cross(a, b, d), cross(c, d, a), cross(c, d, b)
            if values[0]*values[1] < 0 and values[2]*values[3] < 0:
                return False
            for value, point, lo, hi in [(values[0], c, a, b), (values[1], d, a, b), (values[2], a, c, d), (values[3], b, c, d)]:
                if abs(value) < 1e-14 and min(lo[0], hi[0]) <= point[0] <= max(lo[0], hi[0]) and min(lo[1], hi[1]) <= point[1] <= max(lo[1], hi[1]):
                    return False
    return True
