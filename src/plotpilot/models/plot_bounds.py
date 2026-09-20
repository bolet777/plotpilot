"""Document vs plotter travel preflight result."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BoundsStatus(Enum):
    OK = "ok"
    UNKNOWN_MODEL = "unknown_model"
    OUT_OF_BOUNDS = "out_of_bounds"
    INVALID_DIMENSIONS = "invalid_dimensions"


@dataclass(frozen=True, slots=True)
class PlotBoundsCheck:
    status: BoundsStatus
    document_width_mm: float | None
    document_height_mm: float | None
    model_width_mm: float | None
    model_height_mm: float | None
    model_display_name: str | None
    message: str
    would_fit_if_rotated: bool = False

    @property
    def blocks_plotting(self) -> bool:
        return self.status is BoundsStatus.OUT_OF_BOUNDS
