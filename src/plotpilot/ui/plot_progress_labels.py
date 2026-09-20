"""Format plot progress for compact Qt labels."""

from __future__ import annotations

from plotpilot.models.plot_progress import (
    PlotProgress,
    PlotProgressPhase,
    format_plot_duration,
    format_remaining_duration,
)


def progress_headline(progress: PlotProgress) -> str:
    if not progress.layer_name:
        return ""
    if progress.layer_index is not None and progress.layer_count is not None:
        return f"Layer {progress.layer_index} of {progress.layer_count} — {progress.layer_name}"
    return f"Plotting: {progress.layer_name}"


def progress_fraction_label(progress: PlotProgress) -> str:
    if progress.estimated_fraction is None:
        if progress.estimate_unavailable and progress.phase is PlotProgressPhase.RUNNING:
            return "Estimate unavailable"
        return ""
    percent = int(round(progress.estimated_fraction * 100))
    if progress.is_estimated and progress.phase is PlotProgressPhase.RUNNING:
        return f"{percent}% estimated"
    if progress.phase is PlotProgressPhase.COMPLETE:
        return "100%"
    return f"{percent}%"


def progress_timing_line(progress: PlotProgress) -> str:
    elapsed = format_plot_duration(progress.elapsed_seconds)
    if progress.phase is PlotProgressPhase.COMPLETE:
        return f"{elapsed} elapsed"
    if progress.estimated_remaining_seconds is not None and progress.is_estimated:
        remaining = format_remaining_duration(
            progress.estimated_remaining_seconds,
            estimated=True,
        )
        return f"{elapsed} elapsed · {remaining} remaining"
    if progress.estimate_unavailable:
        return f"{elapsed} elapsed · Estimate unavailable"
    return f"{elapsed} elapsed"


def progress_next_layer_line(progress: PlotProgress) -> str:
    if not progress.next_layer_name or progress.phase is not PlotProgressPhase.RUNNING:
        return ""
    return f"Next: {progress.next_layer_name}"
