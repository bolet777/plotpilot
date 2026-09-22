"""Axis-aligned rectangle clipping for line segments (Liang–Barsky)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ClipRect:
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    def __post_init__(self) -> None:
        if self.x_max < self.x_min or self.y_max < self.y_min:
            msg = "Invalid clip rectangle."
            raise ValueError(msg)


def clip_segment(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    rect: ClipRect,
) -> tuple[bool, float, float, float, float]:
    """Return (accept, x0', y0', x1', y1') after clipping to *rect*."""
    dx = x1 - x0
    dy = y1 - y0
    u1 = 0.0
    u2 = 1.0

    for p, q in (
        (-dx, x0 - rect.x_min),
        (dx, rect.x_max - x0),
        (-dy, y0 - rect.y_min),
        (dy, rect.y_max - y0),
    ):
        if p == 0.0:
            if q < 0.0:
                return False, x0, y0, x1, y1
            continue
        t = q / p
        if p < 0.0:
            if t > u2:
                return False, x0, y0, x1, y1
            if t > u1:
                u1 = t
        else:
            if t < u1:
                return False, x0, y0, x1, y1
            if t < u2:
                u2 = t

    nx0 = x0 + u1 * dx
    ny0 = y0 + u1 * dy
    nx1 = x0 + u2 * dx
    ny1 = y0 + u2 * dy
    return True, nx0, ny0, nx1, ny1
