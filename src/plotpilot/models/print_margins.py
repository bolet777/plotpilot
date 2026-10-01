"""Symmetric print margins and the inset printable rectangle (Qt-free)."""

from __future__ import annotations

import math
from dataclasses import dataclass

# Smallest printable width or height the editor and validator will allow.
MIN_PRINTABLE_MM = 0.1


class PrintMarginsError(ValueError):
    """Margins are non-finite, negative, or too large for the work area."""

    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


@dataclass(frozen=True, slots=True)
class PrintMargins:
    """Left/right share ``horizontal_mm``. Top/bottom share ``vertical_mm``."""

    horizontal_mm: float = 10.0
    vertical_mm: float = 10.0

    def validate(self) -> None:
        _require_non_negative("Horizontal", self.horizontal_mm)
        _require_non_negative("Vertical", self.vertical_mm)

    def validate_for_work_area(self, width_mm: float, height_mm: float) -> None:
        """Reject margins that do not leave a positive printable rectangle."""
        self.validate()
        if (
            not math.isfinite(width_mm)
            or not math.isfinite(height_mm)
            or width_mm <= 0.0
            or height_mm <= 0.0
        ):
            msg = "Work area size must be positive."
            raise PrintMarginsError(msg)
        printable_width = width_mm - 2.0 * self.horizontal_mm
        printable_height = height_mm - 2.0 * self.vertical_mm
        if printable_width < MIN_PRINTABLE_MM:
            msg = (
                f"Horizontal margins of {_fmt_mm(self.horizontal_mm)} mm leave no printable "
                f"width in a {_fmt_mm(width_mm)} mm work area."
            )
            raise PrintMarginsError(msg)
        if printable_height < MIN_PRINTABLE_MM:
            msg = (
                f"Vertical margins of {_fmt_mm(self.vertical_mm)} mm leave no printable "
                f"height in a {_fmt_mm(height_mm)} mm work area."
            )
            raise PrintMarginsError(msg)


@dataclass(frozen=True, slots=True)
class PrintableArea:
    """Machine-space rectangle where strokes may be sent to the plotter.

    The origin is inset by the margins. It is not a width and height starting at (0, 0).
    """

    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float

    @property
    def x_max_mm(self) -> float:
        return self.x_mm + self.width_mm

    @property
    def y_max_mm(self) -> float:
        return self.y_mm + self.height_mm

    def size_label(self) -> str:
        return f"{_fmt_mm(self.width_mm)} × {_fmt_mm(self.height_mm)} mm"


def active_print_margins(margins: PrintMargins | None) -> PrintMargins:
    """Return *margins*, or the product default when a caller omits them.

    The application always passes the saved margins (10 mm unless the user
    changed them). An omitted value still uses that default so a missed
    caller cannot plot into the margin.
    """
    if margins is None:
        return PrintMargins()
    return margins


def printable_area_for(
    work_width_mm: float,
    work_height_mm: float,
    margins: PrintMargins,
) -> PrintableArea:
    """Inset *margins* from the physical work area. Machine origin stays (0, 0)."""
    margins.validate_for_work_area(work_width_mm, work_height_mm)
    return PrintableArea(
        x_mm=margins.horizontal_mm,
        y_mm=margins.vertical_mm,
        width_mm=work_width_mm - 2.0 * margins.horizontal_mm,
        height_mm=work_height_mm - 2.0 * margins.vertical_mm,
    )


def max_symmetric_margin_mm(span_mm: float) -> float:
    """Largest 0.1 mm margin that still leaves ``MIN_PRINTABLE_MM`` of span."""
    if not math.isfinite(span_mm) or span_mm <= MIN_PRINTABLE_MM:
        return 0.0
    raw = (span_mm - MIN_PRINTABLE_MM) / 2.0
    stepped = math.floor((raw * 10.0) + 1e-9) / 10.0
    return max(0.0, stepped)


def _require_non_negative(label: str, value: float) -> None:
    if not math.isfinite(value):
        msg = f"{label} print margin must be a finite number."
        raise PrintMarginsError(msg)
    if value < 0.0:
        msg = f"{label} print margin cannot be negative."
        raise PrintMarginsError(msg)


def _fmt_mm(value: float) -> str:
    if abs(value - round(value)) < 0.05:
        return str(int(round(value)))
    return f"{value:.1f}"
