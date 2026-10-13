"""Optional keep-inside shapes in machine millimetres (Qt-free)."""

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


class ClipEllipseError(ValueError):
    """A keep-inside ellipse is non-finite or has no positive radius."""

    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


@dataclass(frozen=True, slots=True)
class ClipEllipse:
    """Axis-aligned ellipse on the machine bed. Y increases downward.

    A circle is an ellipse with equal radii. The center and radii are machine
    millimetres. Preparation keeps strokes inside this ellipse after the
    printable-area clip.
    """

    cx_mm: float
    cy_mm: float
    rx_mm: float
    ry_mm: float

    def validate(self) -> None:
        if not all(
            math.isfinite(value) for value in (self.cx_mm, self.cy_mm, self.rx_mm, self.ry_mm)
        ):
            msg = "Keep-inside ellipse coordinates must be finite."
            raise ClipEllipseError(msg)
        if self.rx_mm <= 0.0 or self.ry_mm <= 0.0:
            msg = "Keep-inside ellipse must have positive radii."
            raise ClipEllipseError(msg)

    @property
    def is_circle(self) -> bool:
        return self.rx_mm == self.ry_mm


ClipShape = ClipRectangle | ClipEllipse


def ellipse_from_rectangle(rectangle: ClipRectangle) -> ClipEllipse:
    """Inscribe an ellipse in *rectangle*. A square becomes a circle."""
    ellipse = ClipEllipse(
        cx_mm=rectangle.x_mm + rectangle.width_mm / 2.0,
        cy_mm=rectangle.y_mm + rectangle.height_mm / 2.0,
        rx_mm=rectangle.width_mm / 2.0,
        ry_mm=rectangle.height_mm / 2.0,
    )
    ellipse.validate()
    return ellipse


def translate_ellipse(
    ellipse: ClipEllipse,
    dx_mm: float,
    dy_mm: float,
    *,
    x_min: float,
    y_min: float,
    x_max: float,
    y_max: float,
) -> ClipEllipse:
    """Slide *ellipse* by a millimetre delta and stop at the bounds."""
    left = _clamp(
        ellipse.cx_mm - ellipse.rx_mm + dx_mm,
        x_min,
        x_max - 2.0 * ellipse.rx_mm,
    )
    top = _clamp(
        ellipse.cy_mm - ellipse.ry_mm + dy_mm,
        y_min,
        y_max - 2.0 * ellipse.ry_mm,
    )
    moved = ClipEllipse(
        left + ellipse.rx_mm,
        top + ellipse.ry_mm,
        ellipse.rx_mm,
        ellipse.ry_mm,
    )
    moved.validate()
    return moved


def resize_ellipse(
    ellipse: ClipEllipse,
    handle: str,
    pointer_x: float,
    pointer_y: float,
    *,
    circle: bool,
    x_min: float,
    y_min: float,
    x_max: float,
    y_max: float,
) -> ClipEllipse | None:
    """Resize from a cardinal handle. The opposite side stays fixed.

    ``circle`` forces equal radii and shrinks so the result stays inside the
    bounds. Returns ``None`` when the diameter would be under ``MIN_CLIP_SIDE_MM``.
    """
    px = _clamp(pointer_x, x_min, x_max)
    py = _clamp(pointer_y, y_min, y_max)
    if handle in ("e", "w"):
        fixed_x = ellipse.cx_mm - ellipse.rx_mm if handle == "e" else ellipse.cx_mm + ellipse.rx_mm
        if handle == "e":
            diameter = px - fixed_x
            center_from_fixed = 1.0
        else:
            diameter = fixed_x - px
            center_from_fixed = -1.0
        if diameter < MIN_CLIP_SIDE_MM:
            return None
        radius = diameter / 2.0
        cy = ellipse.cy_mm
        if circle:
            room = min(cy - y_min, y_max - cy)
            radius = min(radius, room)
            if radius * 2.0 < MIN_CLIP_SIDE_MM:
                return None
            ry = radius
        else:
            ry = ellipse.ry_mm
        cx = fixed_x + center_from_fixed * radius
        resized = ClipEllipse(cx, cy, radius, ry)
    elif handle in ("n", "s"):
        fixed_y = ellipse.cy_mm + ellipse.ry_mm if handle == "n" else ellipse.cy_mm - ellipse.ry_mm
        if handle == "s":
            diameter = py - fixed_y
            center_from_fixed = 1.0
        else:
            diameter = fixed_y - py
            center_from_fixed = -1.0
        if diameter < MIN_CLIP_SIDE_MM:
            return None
        radius = diameter / 2.0
        cx = ellipse.cx_mm
        if circle:
            room = min(cx - x_min, x_max - cx)
            radius = min(radius, room)
            if radius * 2.0 < MIN_CLIP_SIDE_MM:
                return None
            rx = radius
        else:
            rx = ellipse.rx_mm
        cy = fixed_y + center_from_fixed * radius
        resized = ClipEllipse(cx, cy, rx, radius)
    else:
        return None
    resized.validate()
    return resized


def _clamp(value: float, low: float, high: float) -> float:
    if high < low:
        return low
    return min(max(value, low), high)
