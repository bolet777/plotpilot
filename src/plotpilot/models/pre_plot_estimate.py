"""Pre-plot time and distance summary from one or more layer estimates."""

from __future__ import annotations

from dataclasses import dataclass

from plotpilot.models.plot_estimate import PlotEstimate
from plotpilot.models.plot_progress import format_plot_duration


@dataclass(frozen=True, slots=True)
class PrePlotEstimateReport:
    """User-facing estimate. Drawing time excludes pen-change pauses."""

    state: str
    summary: str
    drawing_seconds: float | None = None
    pen_down_distance_m: float | None = None
    pen_up_distance_m: float | None = None
    layer_count: int = 0


def running_pre_plot_estimate(layer_count: int) -> PrePlotEstimateReport:
    noun = "layer" if layer_count == 1 else "layers"
    return PrePlotEstimateReport(
        state="running",
        summary=f"Estimating {layer_count} {noun}…",
        layer_count=layer_count,
    )


def build_pre_plot_estimate_report(
    layers: list[tuple[str, PlotEstimate | None]],
) -> PrePlotEstimateReport:
    """Sum successful layer estimates. ``None`` means that layer could not be estimated."""
    if not layers:
        return PrePlotEstimateReport(state="failed", summary="Nothing to estimate.")

    available = [(name, estimate) for name, estimate in layers if estimate is not None]
    missing = [name for name, estimate in layers if estimate is None]
    if not available:
        names = ", ".join(missing)
        return PrePlotEstimateReport(
            state="failed",
            summary=f"Estimate unavailable ({names}).",
            layer_count=len(layers),
        )

    drawing_seconds = sum(estimate.duration_seconds for _name, estimate in available)
    pen_down = _sum_optional([estimate.pen_down_distance_m for _name, estimate in available])
    pen_up = _sum_optional([estimate.pen_up_distance_m for _name, estimate in available])

    lines: list[str] = []
    if len(layers) == 1:
        lines.append(f"Drawing estimate: {format_plot_duration(drawing_seconds)}")
    else:
        for name, estimate in layers:
            if estimate is None:
                lines.append(f"{name}: unavailable")
            else:
                lines.append(f"{name}: {format_plot_duration(estimate.duration_seconds)}")
        lines.append(f"Total drawing: {format_plot_duration(drawing_seconds)}")
        lines.append("Pen-change pauses are not included.")

    if pen_down is not None:
        lines.append(f"Pen down: {_format_meters(pen_down)}")
    if pen_up is not None:
        lines.append(f"Pen up: {_format_meters(pen_up)}")
    if missing and len(layers) == 1:
        lines.append("Estimate unavailable.")

    return PrePlotEstimateReport(
        state="ready",
        summary="\n".join(lines),
        drawing_seconds=drawing_seconds,
        pen_down_distance_m=pen_down,
        pen_up_distance_m=pen_up,
        layer_count=len(layers),
    )


def _sum_optional(values: list[float | None]) -> float | None:
    total = 0.0
    seen = False
    for value in values:
        if value is None:
            continue
        total += value
        seen = True
    if not seen:
        return None
    return total


def _format_meters(distance_m: float) -> str:
    return f"{distance_m:.3f} m"
