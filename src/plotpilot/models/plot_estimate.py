"""Structured plot time/distance estimate from axicli preview."""

from __future__ import annotations

import re
from dataclasses import dataclass

_ESTIMATED_TIME = re.compile(
    r"Estimated print time:\s*([\d.]+)\s*Seconds",
    re.IGNORECASE,
)
_PEN_DOWN = re.compile(
    r"Length of path to draw:\s*([\d.]+)\s*m",
    re.IGNORECASE,
)
_PEN_UP = re.compile(
    r"Pen-up travel distance:\s*([\d.]+)\s*m",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class PlotEstimate:
    duration_seconds: float
    pen_down_distance_m: float | None = None
    pen_up_distance_m: float | None = None


def parse_preview_report(text: str) -> PlotEstimate | None:
    """Parse axicli `-v -T` stdout/stderr. Returns None if duration is missing."""
    if not text:
        return None
    time_match = _ESTIMATED_TIME.search(text)
    if time_match is None:
        return None
    try:
        duration = float(time_match.group(1))
    except ValueError:
        return None
    pen_down = _optional_float(_PEN_DOWN, text)
    pen_up = _optional_float(_PEN_UP, text)
    return PlotEstimate(
        duration_seconds=duration,
        pen_down_distance_m=pen_down,
        pen_up_distance_m=pen_up,
    )


def _optional_float(pattern: re.Pattern[str], text: str) -> float | None:
    match = pattern.search(text)
    if match is None:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None
