"""Plotter detection, pen control, and layer plotting orchestration."""

from __future__ import annotations

import logging
import os
import tempfile
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from plotpilot.models.plot_job import PlotPhase, PlotResult, PlotState
from plotpilot.models.plotter_status import PlotterConnectionState, PlotterStatus
from plotpilot.models.svg_document import SvgDocument
from plotpilot.models.svg_layer import SvgLayer
from plotpilot.plotter.axidraw import AxiDrawCliBackend
from plotpilot.plotter.base import PlotterBackend
from plotpilot.services.plot_service import plot_svg_for_layer, validate_layer_plot_svg
from plotpilot.svg.plot_dimensions import PlotDimensionError

logger = logging.getLogger(__name__)


class _PlotterTaskSignals(QObject):
    finished = Signal(object, str)


class _PlotterTask(QRunnable):
    def __init__(
        self,
        operation: Callable[[], object],
        operation_name: str,
        signals: _PlotterTaskSignals,
    ) -> None:
        super().__init__()
        self._operation = operation
        self._operation_name = operation_name
        self.signals = signals

    def run(self) -> None:
        try:
            result = self._operation()
        except Exception as exc:  # noqa: BLE001 — surface to UI, keep app alive
            logger.exception("Plotter %s failed", self._operation_name)
            if self._operation_name == "plot":
                result = PlotResult(success=False, message=str(exc) or "Plot failed")
            else:
                result = PlotterStatus(
                    state=PlotterConnectionState.ERROR,
                    message=str(exc) or f"{self._operation_name} failed",
                )
        self.signals.finished.emit(result, self._operation_name)


class PlotterService(QObject):
    """Runs plotter I/O off the UI thread and publishes status updates."""

    status_changed = Signal(object)
    plot_state_changed = Signal(object)

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
        self._plot_state = PlotState()
        self._detect_in_flight = False
        self._pending_refresh = False
        self._operation_in_flight = False
        self._plot_in_flight = False
        self._temp_plot_path: Path | None = None

    @property
    def status(self) -> PlotterStatus:
        return self._status

    @property
    def plot_state(self) -> PlotState:
        return self._plot_state

    @property
    def backend(self) -> PlotterBackend:
        return self._backend

    def refresh(self) -> None:
        if self._plot_in_flight or self._detect_in_flight:
            if self._detect_in_flight:
                self._pending_refresh = True
            return
        self._detect_in_flight = True
        self._run_async(self._backend.detect, "detect")

    def pen_up(self) -> None:
        if (
            not self._status.pen_commands_enabled
            or self._operation_in_flight
            or self._plot_in_flight
        ):
            return
        self._run_async(self._backend.pen_up, "pen_up")

    def pen_down(self) -> None:
        if (
            not self._status.pen_commands_enabled
            or self._operation_in_flight
            or self._plot_in_flight
        ):
            return
        self._run_async(self._backend.pen_down, "pen_down")

    def start_plot_layer(self, document: SvgDocument, layer: SvgLayer) -> str | None:
        """Validate and queue a layer plot. Returns an error message or None if started."""
        if self._plot_in_flight:
            return "A plot is already running."
        if not self._status.is_connected:
            return "AxiDraw is not connected."

        svg_text = plot_svg_for_layer(document, layer)
        try:
            validate_layer_plot_svg(svg_text)
        except PlotDimensionError as exc:
            return exc.user_message

        temp_path = _write_temp_svg(svg_text)
        self._temp_plot_path = temp_path
        self._plot_in_flight = True
        self._set_plot_state(
            PlotPhase.RUNNING,
            layer.name,
            f"Plotting: {layer.name}",
        )

        def _run_plot() -> PlotResult:
            return self._backend.plot_svg(temp_path)

        self._run_async(_run_plot, "plot")
        return None

    def cancel_plot(self) -> None:
        if not self._plot_in_flight:
            return
        self._backend.cancel_plot()

    def _run_async(
        self,
        operation: Callable[[], object],
        operation_name: str,
    ) -> None:
        if operation_name != "plot":
            self._operation_in_flight = True
        signals = _PlotterTaskSignals()
        signals.finished.connect(self._on_task_finished)
        task = _PlotterTask(operation, operation_name, signals)
        QThreadPool.globalInstance().start(task)

    @Slot(object, str)
    def _on_task_finished(self, result: object, operation_name: str) -> None:
        if operation_name == "plot":
            self._plot_in_flight = False
            self._cleanup_temp_plot_file()
            plot_result = (
                result
                if isinstance(result, PlotResult)
                else PlotResult(
                    success=False,
                    message="Plot failed",
                )
            )
            layer_name = self._plot_state.layer_name
            if plot_result.cancelled:
                phase = PlotPhase.CANCELLED
                message = plot_result.message or "Plot stopped"
            elif plot_result.success:
                phase = PlotPhase.SUCCEEDED
                message = plot_result.message or "Plot complete"
            else:
                phase = PlotPhase.FAILED
                message = f"Plot failed: {plot_result.message}"
            self._set_plot_state(phase, layer_name, message)
            return

        self._operation_in_flight = False
        if operation_name == "detect":
            self._detect_in_flight = False
            if isinstance(result, PlotterStatus):
                self._status = result
                self.status_changed.emit(result)
            if self._pending_refresh:
                self._pending_refresh = False
                self.refresh()
            return

        if isinstance(result, PlotterStatus):
            self._status = result
            self.status_changed.emit(result)

    def _set_plot_state(self, phase: PlotPhase, layer_name: str, message: str) -> None:
        self._plot_state = PlotState(phase=phase, layer_name=layer_name, message=message)
        self.plot_state_changed.emit(self._plot_state)

    def _cleanup_temp_plot_file(self) -> None:
        path = self._temp_plot_path
        self._temp_plot_path = None
        if path is None:
            return
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not remove temporary plot file %s", path)


def _write_temp_svg(svg_text: str) -> Path:
    handle, raw_path = tempfile.mkstemp(prefix="plotpilot-", suffix=".svg")
    path = Path(raw_path)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as handle_file:
            handle_file.write(svg_text)
    except OSError:
        path.unlink(missing_ok=True)
        raise
    return path
