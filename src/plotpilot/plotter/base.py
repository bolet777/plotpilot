"""Plotter backend abstraction."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

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
