"""Plot job state for layer plotting."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PlotPhase(StrEnum):
    """UI-facing plot lifecycle."""

    IDLE = "idle"
    RUNNING = "running"
    STOPPING = "stopping"
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
        return self.phase in (PlotPhase.RUNNING, PlotPhase.STOPPING)


@dataclass(frozen=True, slots=True)
class PlotResult:
    """Outcome returned by plotter backends."""

    success: bool
    message: str
    cancelled: bool = False
    detail: str = ""


@dataclass(frozen=True, slots=True)
class SafeStopResult:
    """Outcome of raise_pen → walk_home → disable_xy after stop."""

    pen_raised: bool
    homed: bool
    motors_disabled: bool
    message: str
    errors: tuple[str, ...] = ()

    @property
    def cleanup_complete(self) -> bool:
        return self.pen_raised and self.homed and self.motors_disabled
