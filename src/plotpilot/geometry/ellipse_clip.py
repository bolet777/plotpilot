"""Keep-inside clip of one straight segment against an axis-aligned ellipse.

Qt-free. The segment is mapped into the ellipse's unit circle, cut there, and
mapped back to machine millimetres. A circle is an ellipse with equal radii.
"""

from __future__ import annotations

import math

from plotpilot.models.clip_shape import ClipEllipse

# Same snap tolerance as the polyline clipper (``COORD_TOLERANCE_MM``).
_TOLERANCE_MM = 0.01

_A_EPSILON = 1e-18


def ellipse_overlaps_rect(
    ellipse: ClipEllipse,
    x_min: float,
    y_min: float,
    x_max: float,
    y_max: float,
) -> bool:
    """True when the ellipse bounding box has positive area inside the rect."""
    return (
        ellipse.cx_mm - ellipse.rx_mm < x_max
        and ellipse.cx_mm + ellipse.rx_mm > x_min
        and ellipse.cy_mm - ellipse.ry_mm < y_max
        and ellipse.cy_mm + ellipse.ry_mm > y_min
    )


def clip_segment_to_ellipse(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    ellipse: ClipEllipse,
) -> tuple[float, float, float, float] | None:
    """Return the inside span of one segment, or ``None`` when nothing is kept.

    A tangent or any other zero-length contact is dropped. The inside of an
    ellipse is one span, so a segment that only grazes the boundary does not
    invent a second piece.
    """
    ellipse.validate()
    rx = ellipse.rx_mm
    ry = ellipse.ry_mm
    if rx < 1e-9 or ry < 1e-9:
        return None
    cx = ellipse.cx_mm
    cy = ellipse.cy_mm
    u0 = (x0 - cx) / rx
    v0 = (y0 - cy) / ry
    u1 = (x1 - cx) / rx
    v1 = (y1 - cy) / ry
    du = u1 - u0
    dv = v1 - v0
    a = du * du + dv * dv
    min_radius = min(rx, ry)
    uv_slack = _TOLERANCE_MM / min_radius
    length_mm = math.hypot(x1 - x0, y1 - y0)

    def radial(t: float) -> float:
        u = u0 + t * du
        v = v0 + t * dv
        return u * u + v * v

    def inside(t: float) -> bool:
        return radial(t) <= 1.0 + 2.0 * uv_slack

    def to_mm(t: float) -> tuple[float, float]:
        u = u0 + t * du
        v = v0 + t * dv
        return (cx + u * rx, cy + v * ry)

    if a <= _A_EPSILON:
        if inside(0.0) and length_mm > _TOLERANCE_MM:
            return (x0, y0, x1, y1)
        return None

    b = 2.0 * (u0 * du + v0 * dv)
    c = u0 * u0 + v0 * v0 - 1.0
    discriminant = b * b - 4.0 * a * c
    if discriminant < 0.0:
        gap_mm = (-discriminant / (4.0 * a)) / 2.0 * min_radius
        if gap_mm > _TOLERANCE_MM:
            return None
        discriminant = 0.0

    root = math.sqrt(discriminant)
    inverse = 0.5 / a
    t_tol = _TOLERANCE_MM / length_mm if length_mm > _TOLERANCE_MM else 1.0
    unique: list[float] = []
    for raw in ((-b - root) * inverse, (-b + root) * inverse):
        if -t_tol <= raw <= 1.0 + t_tol:
            clamped = min(1.0, max(0.0, raw))
            if not unique or abs(clamped - unique[-1]) > 1e-9:
                unique.append(clamped)

    start_inside = inside(0.0)
    end_inside = inside(1.0)
    if start_inside and end_inside:
        t_start, t_end = 0.0, 1.0
    elif start_inside:
        exits = [t for t in unique if t > 1e-12]
        t_start, t_end = 0.0, exits[0] if exits else 1.0
    elif end_inside:
        entries = [t for t in unique if t < 1.0 - 1e-12]
        t_start, t_end = (entries[-1] if entries else 0.0), 1.0
    elif len(unique) >= 2:
        t_start, t_end = unique[0], unique[-1]
    else:
        return None

    if (t_end - t_start) * length_mm <= _TOLERANCE_MM:
        return None
    sx, sy = to_mm(t_start)
    ex, ey = to_mm(t_end)
    return (sx, sy, ex, ey)
