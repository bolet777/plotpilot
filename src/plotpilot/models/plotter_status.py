"""Plotter connection and status models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PlotterConnectionState(StrEnum):
    """High-level plotter availability."""

    UNKNOWN = "unknown"
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class PlotterStatus:
    """Snapshot of plotter backend state for UI and services."""

    state: PlotterConnectionState
    device_name: str = "AxiDraw"
    message: str = ""
    backend_version: str | None = None

    @property
    def is_connected(self) -> bool:
        return self.state is PlotterConnectionState.CONNECTED

    @property
    def pen_commands_enabled(self) -> bool:
        return self.is_connected
