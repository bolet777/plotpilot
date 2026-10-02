"""Map QSlider integer positions to artwork transform physical values (Qt-free)."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

from plotpilot.models.artwork_transform import DEFAULT_SCALE_MAX, DEFAULT_SCALE_MIN

POSITION_STEP_MM = 0.1
SCALE_STEP_PERCENT = 0.1

SCALE_SLIDER_MIN_PERCENT = DEFAULT_SCALE_MIN * 100.0
SCALE_SLIDER_MAX_PERCENT = DEFAULT_SCALE_MAX * 100.0

SCALE_PRESET_PERCENTS = (50.0, 100.0, 150.0, 200.0)

# Step-count tolerance for binary noise when a limit already lies on the 0.1 mm grid.
_STEP_SNAP_TOLERANCE = 1e-6


@dataclass(frozen=True, slots=True)
class ArtworkBoundsMm:
    """Unscaled artwork extent in document millimeters, before ``ArtworkTransform``."""

    min_x_mm: float
    max_x_mm: float
    min_y_mm: float
    max_y_mm: float

    @classmethod
    def origin_point(cls) -> ArtworkBoundsMm:
        """Zero-size artwork at the document origin."""
        return cls(0.0, 0.0, 0.0, 0.0)


def artwork_bounds_from_polylines(
    polylines: Iterable[Iterable[tuple[float, float]]],
) -> ArtworkBoundsMm | None:
    """Bounding box of document-mm points. These coordinates are not yet scaled."""
    min_x = math.inf
    min_y = math.inf
    max_x = -math.inf
    max_y = -math.inf
    found = False
    for subpath in polylines:
        for x_mm, y_mm in subpath:
            if not math.isfinite(x_mm) or not math.isfinite(y_mm):
                continue
            found = True
            min_x = min(min_x, x_mm)
            min_y = min(min_y, y_mm)
            max_x = max(max_x, x_mm)
            max_y = max(max_y, y_mm)
    if not found:
        return None
    return ArtworkBoundsMm(min_x, max_x, min_y, max_y)


def axis_translation_limits(
    *,
    artwork_min_mm: float,
    artwork_max_mm: float,
    scale: float,
    printable_min_mm: float,
    printable_max_mm: float,
) -> tuple[float, float]:
    """Translation range that lets the scaled artwork cross the printable span.

    ``ArtworkTransform`` places a source point as ``translation + source * scale``.
    ``artwork_min_mm`` / ``artwork_max_mm`` are unscaled document millimeters, so
    scale is applied once:

        scaled_min = artwork_min * scale
        scaled_max = artwork_max * scale
        min_translation = printable_min - scaled_max
        max_translation = printable_max - scaled_min

    The same formula is used for X and Y. Y is not inverted: machine Y grows
    the same way as the transform.
    """
    if (
        not math.isfinite(artwork_min_mm)
        or not math.isfinite(artwork_max_mm)
        or not math.isfinite(scale)
        or not math.isfinite(printable_min_mm)
        or not math.isfinite(printable_max_mm)
        or scale <= 0.0
        or printable_max_mm < printable_min_mm
    ):
        msg = "Translation limits require finite bounds and a positive scale."
        raise ValueError(msg)
    low = min(artwork_min_mm, artwork_max_mm)
    high = max(artwork_min_mm, artwork_max_mm)
    scaled_min = low * scale
    scaled_max = high * scale
    return printable_min_mm - scaled_max, printable_max_mm - scaled_min


def position_slider_maximum(
    min_mm: float,
    max_mm: float,
    *,
    step_mm: float = POSITION_STEP_MM,
) -> int:
    """Inclusive slider steps covering ``min_mm`` … ``max_mm``."""
    min_steps, max_steps = _limit_steps(min_mm, max_mm, step_mm)
    return max_steps - min_steps


def mm_to_position_slider(
    x_mm: float,
    min_mm: float,
    max_mm: float,
    *,
    step_mm: float = POSITION_STEP_MM,
) -> int:
    min_steps, max_steps = _limit_steps(min_mm, max_mm, step_mm)
    value = int(round(x_mm / step_mm)) - min_steps
    return max(0, min(max_steps - min_steps, value))


def position_slider_to_mm(
    slider_value: int,
    min_mm: float,
    max_mm: float,
    *,
    step_mm: float = POSITION_STEP_MM,
) -> float:
    min_steps, _max_steps = _limit_steps(min_mm, max_mm, step_mm)
    return (min_steps + slider_value) * step_mm


def scale_slider_maximum(*, step_percent: float = SCALE_STEP_PERCENT) -> int:
    span = SCALE_SLIDER_MAX_PERCENT - SCALE_SLIDER_MIN_PERCENT
    return int(round(span / step_percent))


def percent_to_scale_slider(
    percent: float,
    *,
    step_percent: float = SCALE_STEP_PERCENT,
) -> int:
    value = int(round((percent - SCALE_SLIDER_MIN_PERCENT) / step_percent))
    return max(0, min(scale_slider_maximum(step_percent=step_percent), value))


def scale_slider_to_percent(
    slider_value: int,
    *,
    step_percent: float = SCALE_STEP_PERCENT,
) -> float:
    return SCALE_SLIDER_MIN_PERCENT + slider_value * step_percent


def preset_visible(percent: float) -> bool:
    return SCALE_SLIDER_MIN_PERCENT <= percent <= SCALE_SLIDER_MAX_PERCENT


def preset_matches_scale(percent: float, scale: float) -> bool:
    return math.isclose(scale * 100.0, percent, rel_tol=0.0, abs_tol=1e-9)


def _limit_steps(min_mm: float, max_mm: float, step_mm: float) -> tuple[int, int]:
    if (
        not math.isfinite(min_mm)
        or not math.isfinite(max_mm)
        or not math.isfinite(step_mm)
        or step_mm <= 0.0
        or max_mm < min_mm
    ):
        msg = "Position slider limits must be a finite span with a positive step."
        raise ValueError(msg)
    min_steps = _steps_floor(min_mm, step_mm)
    max_steps = _steps_ceil(max_mm, step_mm)
    if max_steps < min_steps:
        max_steps = min_steps
    return min_steps, max_steps


def _steps_floor(mm: float, step_mm: float) -> int:
    scaled = mm / step_mm
    nearest = round(scaled)
    if math.isclose(scaled, nearest, rel_tol=0.0, abs_tol=_STEP_SNAP_TOLERANCE):
        return int(nearest)
    return math.floor(scaled)


def _steps_ceil(mm: float, step_mm: float) -> int:
    scaled = mm / step_mm
    nearest = round(scaled)
    if math.isclose(scaled, nearest, rel_tol=0.0, abs_tol=_STEP_SNAP_TOLERANCE):
        return int(nearest)
    return math.ceil(scaled)
