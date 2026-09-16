"""Plotter backend abstraction."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from plotpilot.models.plot_job import PlotResult
from plotpilot.models.plot_settings import PlotSettings
from plotpilot.models.plotter_status import PlotterStatus


@runtime_checkable
class PlotterBackend(Protocol):
    """Device control surface used by PlotterService (no UI or Qt types)."""

    def detect(self) -> PlotterStatus:
        """Probe hardware without XY plotting commands."""

    def pen_up(self) -> PlotterStatus:
        """Raise pen; returns updated status."""

    def pen_down(self) -> PlotterStatus:
        """Lower pen; returns updated status."""

    def plot_svg(
        self,
        svg_path: Path,
        *,
        settings: PlotSettings | None = None,
    ) -> PlotResult:
        """Plot an SVG file (blocking until complete, error, or cancel)."""

    def cancel_plot(self) -> None:
        """Request cancellation of an in-flight plot_svg call."""
