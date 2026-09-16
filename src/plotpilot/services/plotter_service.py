"""Plotter detection and pen control orchestration."""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from plotpilot.models.plotter_status import PlotterConnectionState, PlotterStatus
from plotpilot.plotter.axidraw import AxiDrawCliBackend
from plotpilot.plotter.base import PlotterBackend

logger = logging.getLogger(__name__)


class _PlotterTaskSignals(QObject):
    finished = Signal(object, str)


class _PlotterTask(QRunnable):
    def __init__(
        self,
        operation: Callable[[], PlotterStatus],
        operation_name: str,
        signals: _PlotterTaskSignals,
    ) -> None:
        super().__init__()
        self._operation = operation
        self._operation_name = operation_name
        self.signals = signals

    def run(self) -> None:
        try:
            status = self._operation()
        except Exception as exc:  # noqa: BLE001 — surface to UI, keep app alive
            logger.exception("Plotter %s failed", self._operation_name)
            status = PlotterStatus(
                state=PlotterConnectionState.ERROR,
                message=str(exc) or f"{self._operation_name} failed",
            )
        self.signals.finished.emit(status, self._operation_name)


class PlotterService(QObject):
    """Runs plotter I/O off the UI thread and publishes status updates."""

    status_changed = Signal(object)

    def __init__(
        self,
        backend: PlotterBackend | None = None,
        *,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._backend = backend if backend is not None else AxiDrawCliBackend()
        self._status = PlotterStatus(
            state=PlotterConnectionState.DISCONNECTED,
            message="Not connected. Use Refresh to detect.",
        )
        self._detect_in_flight = False
        self._pending_refresh = False
        self._operation_in_flight = False

    @property
    def status(self) -> PlotterStatus:
        return self._status

    @property
    def backend(self) -> PlotterBackend:
        return self._backend

    def refresh(self) -> None:
        """Start detection unless a detect is already running (coalesce extra requests)."""
        if self._detect_in_flight:
            self._pending_refresh = True
            return
        self._detect_in_flight = True
        self._run_async(self._backend.detect, "detect")

    def pen_up(self) -> None:
        if not self._status.pen_commands_enabled or self._operation_in_flight:
            return
        self._run_async(self._backend.pen_up, "pen_up")

    def pen_down(self) -> None:
        if not self._status.pen_commands_enabled or self._operation_in_flight:
            return
        self._run_async(self._backend.pen_down, "pen_down")

    def _run_async(
        self,
        operation: Callable[[], PlotterStatus],
        operation_name: str,
    ) -> None:
        self._operation_in_flight = True
        signals = _PlotterTaskSignals()
        signals.finished.connect(self._on_task_finished)
        task = _PlotterTask(operation, operation_name, signals)
        QThreadPool.globalInstance().start(task)

    @Slot(object, str)
    def _on_task_finished(self, status: PlotterStatus, operation_name: str) -> None:
        self._operation_in_flight = False
        if operation_name == "detect":
            self._detect_in_flight = False
            if self._pending_refresh:
                self._pending_refresh = False
                self.refresh()
                return
        self._status = status
        self.status_changed.emit(status)
