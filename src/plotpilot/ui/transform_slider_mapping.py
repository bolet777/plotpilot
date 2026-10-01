"""Map QSlider integer positions to artwork transform physical values (Qt-free)."""

from __future__ import annotations

import math

from plotpilot.models.artwork_transform import DEFAULT_SCALE_MAX, DEFAULT_SCALE_MIN

POSITION_STEP_MM = 0.1
SCALE_STEP_PERCENT = 0.1

SCALE_SLIDER_MIN_PERCENT = DEFAULT_SCALE_MIN * 100.0
SCALE_SLIDER_MAX_PERCENT = DEFAULT_SCALE_MAX * 100.0

SCALE_PRESET_PERCENTS = (50.0, 100.0, 150.0, 200.0)


def position_slider_maximum(range_mm: float, *, step_mm: float = POSITION_STEP_MM) -> int:
    """Inclusive slider range for symmetric ±range_mm."""
    if range_mm <= 0 or not math.isfinite(range_mm):
        msg = "Position slider range must be a positive finite number."
        raise ValueError(msg)
    steps_per_side = int(round(range_mm / step_mm))
    return steps_per_side * 2


def mm_to_position_slider(
    x_mm: float,
    range_mm: float,
    *,
    step_mm: float = POSITION_STEP_MM,
) -> int:
    steps_per_side = int(round(range_mm / step_mm))
    value = int(round(x_mm / step_mm)) + steps_per_side
    return max(0, min(position_slider_maximum(range_mm, step_mm=step_mm), value))


def position_slider_to_mm(
    slider_value: int,
    range_mm: float,
    *,
    step_mm: float = POSITION_STEP_MM,
) -> float:
    steps_per_side = int(round(range_mm / step_mm))
    return (slider_value - steps_per_side) * step_mm


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
