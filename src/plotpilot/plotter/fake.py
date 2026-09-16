"""In-memory plotter backend for automated tests."""

from __future__ import annotations

from dataclasses import dataclass, field

from plotpilot.models.plotter_status import PlotterConnectionState, PlotterStatus


@dataclass
class FakePlotterBackend:
    """Configurable fake plotter; records pen calls."""

    detect_result: PlotterStatus = field(
        default_factory=lambda: PlotterStatus(
            state=PlotterConnectionState.DISCONNECTED,
            message="Not connected",
        )
    )
    pen_up_raises: BaseException | None = None
    pen_down_raises: BaseException | None = None
    pen_up_result: PlotterStatus | None = None
    pen_down_result: PlotterStatus | None = None
    detect_calls: int = 0
    pen_up_calls: int = 0
    pen_down_calls: int = 0

    def detect(self) -> PlotterStatus:
        self.detect_calls += 1
        return self.detect_result

    def pen_up(self) -> PlotterStatus:
        self.pen_up_calls += 1
        if self.pen_up_raises is not None:
            raise self.pen_up_raises
        if self.pen_up_result is not None:
            return self.pen_up_result
        return self.detect_result

    def pen_down(self) -> PlotterStatus:
        self.pen_down_calls += 1
        if self.pen_down_raises is not None:
            raise self.pen_down_raises
        if self.pen_down_result is not None:
            return self.pen_down_result
        return self.detect_result
