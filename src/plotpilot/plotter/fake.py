"""In-memory plotter backend for automated tests."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from plotpilot.models.plot_job import PlotResult
from plotpilot.models.plotter_status import PlotterConnectionState, PlotterStatus


@dataclass
class FakePlotterBackend:
    """Configurable fake plotter; records pen and plot calls."""

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
    plot_result: PlotResult | None = None
    plot_block_until_cancel: bool = False
    plot_delay_seconds: float = 0.0
    detect_calls: int = 0
    pen_up_calls: int = 0
    pen_down_calls: int = 0
    plot_paths: list[Path] = field(default_factory=list)
    plot_file_contents: list[str] = field(default_factory=list)
    plot_file_existed: bool = False
    cancel_plot_calls: int = 0
    _cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)

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

    def plot_svg(self, svg_path: Path) -> PlotResult:
        self.plot_paths.append(svg_path)
        self.plot_file_existed = svg_path.exists()
        if svg_path.exists():
            self.plot_file_contents.append(svg_path.read_text(encoding="utf-8"))
        self._cancel_event.clear()
        if self.plot_delay_seconds > 0:
            time.sleep(self.plot_delay_seconds)
        if self.plot_block_until_cancel:
            while not self._cancel_event.wait(0.02):
                continue
            return PlotResult(
                success=False,
                cancelled=True,
                message="Plot stopped",
            )
        if self.plot_result is not None:
            return self.plot_result
        return PlotResult(success=True, message="Plot complete")

    def cancel_plot(self) -> None:
        self.cancel_plot_calls += 1
        self._cancel_event.set()
