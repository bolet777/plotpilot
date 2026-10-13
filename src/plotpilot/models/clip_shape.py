"""Optional keep-inside rectangle in machine millimetres (Qt-free)."""

from __future__ import annotations

import math
from dataclasses import dataclass


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
