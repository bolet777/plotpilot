"""Structured plot time/distance estimate from axicli preview."""

from __future__ import annotations

import re
from dataclasses import dataclass

# axicli 3.9.6 prints the time via plotink.text_utils.format_hms, on stderr.
# Under 10 s: "2.052 Seconds". 10–59 s: "36 Seconds".
# 60 s and above: "3:00 (Minutes, seconds)" or "1:02:03 (Hours, minutes, seconds)".
_TIME_LINE = re.compile(r"Estimated print time:\s*(.+)", re.IGNORECASE)
_SECONDS = re.compile(r"([\d.]+)\s*Seconds\b", re.IGNORECASE)
_MINUTES = re.compile(
    r"(\d+):(\d{2})\s*\(\s*Minutes\s*,\s*seconds\s*\)",
    re.IGNORECASE,
)
_HOURS = re.compile(
    r"(\d+):(\d{2}):(\d{2})\s*\(\s*Hours\s*,\s*minutes\s*,\s*seconds\s*\)",
    re.IGNORECASE,
)
_PEN_DOWN = re.compile(
    r"Length of path to draw:\s*([\d.]+)\s*m\b",
    re.IGNORECASE,
)
_PEN_UP = re.compile(
    r"Pen-up travel distance:\s*([\d.]+)\s*m\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class PlotEstimate:
    duration_seconds: float
    pen_down_distance_m: float | None = None
    pen_up_distance_m: float | None = None


@dataclass(frozen=True, slots=True)
class PreviewEstimateResult:
    """Parsed preview, or a short UI-safe reason when axicli did not yield one."""

    estimate: PlotEstimate | None = None
    failure: str | None = None


def parse_preview_report(text: str) -> PlotEstimate | None:
    """Parse axicli `-v -T` stdout/stderr. Returns None if duration is missing."""
    if not text:
        return None
    time_match = _TIME_LINE.search(text)
    if time_match is None:
        return None
    duration = _duration_seconds(time_match.group(1))
    if duration is None:
        return None
    pen_down = _optional_float(_PEN_DOWN, text)
    pen_up = _optional_float(_PEN_UP, text)
    return PlotEstimate(
        duration_seconds=duration,
        pen_down_distance_m=pen_down,
        pen_up_distance_m=pen_up,
    )


def _duration_seconds(time_text: str) -> float | None:
    hours = _HOURS.search(time_text)
    if hours is not None:
        return int(hours.group(1)) * 3600 + int(hours.group(2)) * 60 + int(hours.group(3))
    minutes = _MINUTES.search(time_text)
    if minutes is not None:
        return int(minutes.group(1)) * 60 + int(minutes.group(2))
    seconds = _SECONDS.search(time_text)
    if seconds is None:
        return None
    try:
        return float(seconds.group(1))
    except ValueError:
        return None


def _optional_float(pattern: re.Pattern[str], text: str) -> float | None:
    match = pattern.search(text)
    if match is None:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None
