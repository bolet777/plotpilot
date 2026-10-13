"""Optional keep-inside rectangle in machine millimetres (Qt-free)."""

from __future__ import annotations

import math
from dataclasses import dataclass

# Drags smaller than this do not replace an existing rectangle.
MIN_CLIP_SIDE_MM = 1.0


class ClipRectangleError(ValueError):
    """A keep-inside rectangle is non-finite or has no positive area."""

    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


@dataclass(frozen=True, slots=True)
class ClipRectangle:
    """Axis-aligned window on the machine bed. Y increases downward.

    Preparation keeps strokes inside the overlap of this rectangle and the
    printable area. Absence of a rectangle is ``None`` at the call site.
    """

    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float

    def validate(self) -> None:
        if not all(
            math.isfinite(value) for value in (self.x_mm, self.y_mm, self.width_mm, self.height_mm)
        ):
            msg = "Keep-inside rectangle coordinates must be finite."
            raise ClipRectangleError(msg)
        if self.width_mm <= 0.0 or self.height_mm <= 0.0:
            msg = "Keep-inside rectangle must have a positive width and height."
            raise ClipRectangleError(msg)

    @property
    def x_max_mm(self) -> float:
        return self.x_mm + self.width_mm

    @property
    def y_max_mm(self) -> float:
        return self.y_mm + self.height_mm


def drag_rectangle(
    anchor_x: float,
    anchor_y: float,
    pointer_x: float,
    pointer_y: float,
    *,
    square: bool,
    x_min: float,
    y_min: float,
    x_max: float,
    y_max: float,
) -> ClipRectangle | None:
    """Build a rectangle from an anchor to a pointer, clamped to the bounds.

    ``square`` gives equal width and height, shrunk so the result stays inside
    the bounds. Returns ``None`` when either side is under ``MIN_CLIP_SIDE_MM``.
    """
    ax = _clamp(anchor_x, x_min, x_max)
    ay = _clamp(anchor_y, y_min, y_max)
    px = _clamp(pointer_x, x_min, x_max)
    py = _clamp(pointer_y, y_min, y_max)
    dx = px - ax
    dy = py - ay
    if square and (dx != 0.0 or dy != 0.0):
        sign_x = math.copysign(1.0, dx) if dx != 0.0 else 0.0
        sign_y = math.copysign(1.0, dy) if dy != 0.0 else 0.0
        if sign_x == 0.0:
            sign_x = sign_y
        if sign_y == 0.0:
            sign_y = sign_x
        side = max(abs(dx), abs(dy))
        room_x = (x_max - ax) if sign_x >= 0.0 else (ax - x_min)
        room_y = (y_max - ay) if sign_y >= 0.0 else (ay - y_min)
        side = min(side, room_x, room_y)
        dx = sign_x * side
        dy = sign_y * side
    left, right = sorted((ax, ax + dx))
    top, bottom = sorted((ay, ay + dy))
    left = max(left, x_min)
    top = max(top, y_min)
    right = min(right, x_max)
    bottom = min(bottom, y_max)
    width = right - left
    height = bottom - top
    if width < MIN_CLIP_SIDE_MM or height < MIN_CLIP_SIDE_MM:
        return None
    rectangle = ClipRectangle(left, top, width, height)
    rectangle.validate()
    return rectangle


def translate_rectangle(
    rectangle: ClipRectangle,
    dx_mm: float,
    dy_mm: float,
    *,
    x_min: float,
    y_min: float,
    x_max: float,
    y_max: float,
) -> ClipRectangle:
    """Slide *rectangle* by a millimetre delta and stop at the bounds."""
    x = _clamp(rectangle.x_mm + dx_mm, x_min, x_max - rectangle.width_mm)
    y = _clamp(rectangle.y_mm + dy_mm, y_min, y_max - rectangle.height_mm)
    moved = ClipRectangle(x, y, rectangle.width_mm, rectangle.height_mm)
    moved.validate()
    return moved


def _clamp(value: float, low: float, high: float) -> float:
    if high < low:
        return low
    return min(max(value, low), high)
