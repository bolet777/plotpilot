"""In-memory plotter backend for automated tests."""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from plotpilot.models.plot_job import PlotResult
from plotpilot.models.plot_settings import PlotSettings
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
    walk_home_raises: BaseException | None = None
    disable_xy_raises: BaseException | None = None
    pen_up_result: PlotterStatus | None = None
    pen_down_result: PlotterStatus | None = None
    walk_home_result: PlotterStatus | None = None
    disable_xy_result: PlotterStatus | None = None
    plot_result: PlotResult | None = None
    plot_block_until_cancel: bool = False
    plot_block_timeout_seconds: float | None = None
    plot_delay_seconds: float = 0.0
    detect_calls: int = 0
    detect_presence_calls: int = 0
    detect_presence_result: PlotterStatus | None = None
    pen_up_calls: int = 0
    pen_down_calls: int = 0
    walk_home_calls: int = 0
    disable_xy_calls: int = 0
    manual_sequence: list[str] = field(default_factory=list)
    plot_paths: list[Path] = field(default_factory=list)
    plot_settings_used: list[PlotSettings | None] = field(default_factory=list)
    plot_file_contents: list[str] = field(default_factory=list)
    plot_file_existed: bool = False
    cancel_plot_calls: int = 0
    _cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)

    def detect(self) -> PlotterStatus:
        self.detect_calls += 1
        return self.detect_result

    def detect_presence(self) -> PlotterStatus:
        self.detect_presence_calls += 1
        if self.detect_presence_result is not None:
            return self.detect_presence_result
        return self.detect_result

    def pen_up(self) -> PlotterStatus:
        self.pen_up_calls += 1
        self.manual_sequence.append("raise_pen")
        if self.pen_up_raises is not None:
            raise self.pen_up_raises
        if self.pen_up_result is not None:
            return self.pen_up_result
        return self.detect_result

    def pen_down(self) -> PlotterStatus:
        self.pen_down_calls += 1
        self.manual_sequence.append("lower_pen")
        if self.pen_down_raises is not None:
            raise self.pen_down_raises
        if self.pen_down_result is not None:
            return self.pen_down_result
        return self.detect_result

    def walk_home(self) -> PlotterStatus:
        self.walk_home_calls += 1
        self.manual_sequence.append("walk_home")
        if self.walk_home_raises is not None:
            raise self.walk_home_raises
        if self.walk_home_result is not None:
            return self.walk_home_result
        return self.detect_result

    def disable_xy(self) -> PlotterStatus:
        self.disable_xy_calls += 1
        self.manual_sequence.append("disable_xy")
        if self.disable_xy_raises is not None:
            raise self.disable_xy_raises
        if self.disable_xy_result is not None:
            return self.disable_xy_result
        return self.detect_result

    def plot_svg(
        self,
        svg_path: Path,
        *,
        settings: PlotSettings | None = None,
    ) -> PlotResult:
        self.plot_paths.append(svg_path)
        self.plot_settings_used.append(settings)
        self.plot_file_existed = svg_path.exists()
        if svg_path.exists():
            self.plot_file_contents.append(svg_path.read_text(encoding="utf-8"))
        self._cancel_event.clear()
        if self.plot_delay_seconds > 0:
            time.sleep(self.plot_delay_seconds)
        if self.plot_block_until_cancel:
            timeout = self.plot_block_timeout_seconds
            if timeout is None and os.getenv("PYTEST_CURRENT_TEST"):
                timeout = 30.0
            deadline = time.monotonic() + timeout if timeout is not None else None
            while not self._cancel_event.wait(0.02):
                if deadline is not None and time.monotonic() >= deadline:
                    return PlotResult(
                        success=False,
                        cancelled=True,
                        message="Plot stopped (block timeout)",
                    )
            self.manual_sequence.append("plot_exited")
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
