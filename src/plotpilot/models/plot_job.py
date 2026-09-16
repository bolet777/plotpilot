"""Plot job state for layer plotting."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PlotPhase(StrEnum):
    """UI-facing plot lifecycle."""

    IDLE = "idle"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class PlotState:
    """Snapshot of an in-flight or finished plot."""

    phase: PlotPhase = PlotPhase.IDLE
    layer_name: str = ""
    message: str = ""

    @property
    def is_active(self) -> bool:
        return self.phase is PlotPhase.RUNNING


@dataclass(frozen=True, slots=True)
class PlotResult:
    """Outcome returned by plotter backends."""

    success: bool
    message: str
    cancelled: bool = False
    detail: str = ""
