"""Plot progress model and pure time/progress calculations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

RUNNING_PROGRESS_CAP = 0.99


class PlotProgressPhase(StrEnum):
    """UI-facing progress lifecycle (aligned with plot phases)."""

    IDLE = "idle"
    RUNNING = "running"
    STOPPING = "stopping"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class PlotProgress:
    """Snapshot of plotting progress for UI and tests."""

    phase: PlotProgressPhase = PlotProgressPhase.IDLE
    layer_name: str = ""
    layer_index: int | None = None
    layer_count: int | None = None
    elapsed_seconds: float = 0.0
    estimated_total_seconds: float | None = None
    estimated_remaining_seconds: float | None = None
    estimated_fraction: float | None = None
    is_estimated: bool = False
    estimate_unavailable: bool = False
    next_layer_name: str = ""

    @property
    def is_visible(self) -> bool:
        return self.phase in (
            PlotProgressPhase.RUNNING,
            PlotProgressPhase.STOPPING,
            PlotProgressPhase.COMPLETE,
            PlotProgressPhase.FAILED,
            PlotProgressPhase.CANCELLED,
        )


def format_plot_duration(total_seconds: float) -> str:
    """Format seconds as MM:SS, or H:MM:SS when one hour or more."""
    total = max(0, int(total_seconds))
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def format_remaining_duration(total_seconds: float, *, estimated: bool) -> str:
    formatted = format_plot_duration(total_seconds)
    return f"~{formatted}" if estimated else formatted


def running_estimated_fraction(elapsed_seconds: float, estimated_total_seconds: float) -> float:
    if estimated_total_seconds <= 0:
        return 0.0
    return min(elapsed_seconds / estimated_total_seconds, RUNNING_PROGRESS_CAP)


def estimated_remaining_seconds(elapsed_seconds: float, estimated_total_seconds: float) -> float:
    return max(0.0, estimated_total_seconds - elapsed_seconds)


def build_running_progress(
    *,
    layer_name: str,
    elapsed_seconds: float,
    estimated_total_seconds: float | None,
    estimate_unavailable: bool,
    layer_index: int | None = None,
    layer_count: int | None = None,
    next_layer_name: str = "",
    phase: PlotProgressPhase = PlotProgressPhase.RUNNING,
) -> PlotProgress:
    fraction: float | None = None
    remaining: float | None = None
    is_estimated = False
    if estimated_total_seconds is not None and estimated_total_seconds > 0:
        is_estimated = True
        fraction = running_estimated_fraction(elapsed_seconds, estimated_total_seconds)
        remaining = estimated_remaining_seconds(elapsed_seconds, estimated_total_seconds)
    return PlotProgress(
        phase=phase,
        layer_name=layer_name,
        layer_index=layer_index,
        layer_count=layer_count,
        elapsed_seconds=elapsed_seconds,
        estimated_total_seconds=estimated_total_seconds,
        estimated_remaining_seconds=remaining,
        estimated_fraction=fraction,
        is_estimated=is_estimated,
        estimate_unavailable=estimate_unavailable and estimated_total_seconds is None,
        next_layer_name=next_layer_name,
    )


def idle_plot_progress() -> PlotProgress:
    return PlotProgress()
