"""Plotter detection, pen control, and layer plotting orchestration."""

from __future__ import annotations

import logging
import os
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from plotpilot.models.plot_job import PlotPhase, PlotResult, PlotState, SafeStopResult
from plotpilot.models.plot_settings import PlotSettings
from plotpilot.models.plotter_status import PlotterConnectionState, PlotterStatus
from plotpilot.models.svg_document import SvgDocument
from plotpilot.models.svg_layer import SvgLayer
from plotpilot.plotter.axidraw import PLOT_CANCEL_WAIT, AxiDrawCliBackend
from plotpilot.plotter.base import PlotterBackend
from plotpilot.services.plot_service import plot_svg_for_layer, validate_layer_plot_svg
from plotpilot.services.settings_service import SettingsService
from plotpilot.svg.plot_dimensions import PlotDimensionError

logger = logging.getLogger(__name__)

PLOT_EXIT_WAIT_SECONDS = PLOT_CANCEL_WAIT + 12.0


class _PlotterTaskSignals(QObject):
    finished = Signal(object, str)
    progress = Signal(str)


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
            elif self._operation_name == "safe_stop":
                result = SafeStopResult(
                    pen_raised=False,
                    homed=False,
                    motors_disabled=False,
                    message=f"Plot stopped — cleanup incomplete\n{exc}",
                    errors=(str(exc),),
                )
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
    safe_stop_finished = Signal(object)

    def __init__(
        self,
        backend: PlotterBackend | None = None,
        *,
        settings_service: SettingsService | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._backend = backend if backend is not None else AxiDrawCliBackend()
        self._settings_service = settings_service
        self._status = PlotterStatus(
            state=PlotterConnectionState.DISCONNECTED,
            message="Not connected. Use Refresh to detect.",
        )
        self._plot_state = PlotState()
        self._detect_in_flight = False
        self._pending_refresh = False
        self._operation_in_flight = False
        self._plot_in_flight = False
        self._safe_stop_in_flight = False
        self._safe_stop_wait_for_plot = False
        self._plot_exit_event = threading.Event()
        self._temp_plot_path: Path | None = None
        self._active_plot_settings: PlotSettings | None = None

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
        if self._plot_in_flight or self._detect_in_flight or self._safe_stop_in_flight:
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
            or self._safe_stop_in_flight
        ):
            return
        self._run_async(self._backend.pen_up, "pen_up")

    def pen_down(self) -> None:
        if (
            not self._status.pen_commands_enabled
            or self._operation_in_flight
            or self._plot_in_flight
            or self._safe_stop_in_flight
        ):
            return
        self._run_async(self._backend.pen_down, "pen_down")

    def start_plot_layer(
        self,
        document: SvgDocument,
        layer: SvgLayer,
        *,
        plot_settings: PlotSettings | None = None,
    ) -> str | None:
        """Validate and queue a layer plot. Returns an error message or None if started."""
        if self._plot_in_flight or self._safe_stop_in_flight:
            return "A plot is already running."
        if self._plot_state.phase is PlotPhase.STOPPING:
            return "Plotter is finishing stop cleanup."
        if not self._status.is_connected:
            return "AxiDraw is not connected."

        svg_text = plot_svg_for_layer(document, layer)
        try:
            validate_layer_plot_svg(svg_text)
        except PlotDimensionError as exc:
            return exc.user_message

        temp_path = _write_temp_svg(svg_text)
        self._temp_plot_path = temp_path
        self._active_plot_settings = (
            plot_settings if plot_settings is not None else self._snapshot_plot_settings()
        )
        self._plot_in_flight = True
        self._plot_exit_event.clear()
        self._set_plot_state(
            PlotPhase.RUNNING,
            layer.name,
            f"Plotting: {layer.name}",
        )

        plot_settings = self._active_plot_settings

        def _run_plot() -> PlotResult:
            return self._backend.plot_svg(temp_path, settings=plot_settings)

        self._run_async(_run_plot, "plot")
        return None

    def request_safe_stop(self) -> None:
        """Cancel an active plot (if any) and run raise_pen → walk_home → disable_xy."""
        if self._safe_stop_in_flight:
            return
        self._safe_stop_in_flight = True
        self._safe_stop_wait_for_plot = self._plot_in_flight
        layer_name = self._plot_state.layer_name
        self._set_plot_state(PlotPhase.STOPPING, layer_name, "Stopping plot…")

        signals = _PlotterTaskSignals()
        signals.finished.connect(self._on_task_finished)
        signals.progress.connect(self._on_safe_stop_progress)

        def _run_safe_stop() -> SafeStopResult:
            def progress(message: str) -> None:
                signals.progress.emit(message)

            return self._run_safe_stop_sequence(progress)

        task = _PlotterTask(_run_safe_stop, "safe_stop", signals)
        QThreadPool.globalInstance().start(task)

    def cancel_plot(self) -> None:
        """Request cancellation of the active plot subprocess only (no homing)."""
        if not self._plot_in_flight:
            return
        self._backend.cancel_plot()

    @Slot(str)
    def _on_safe_stop_progress(self, message: str) -> None:
        layer_name = self._plot_state.layer_name
        self._set_plot_state(PlotPhase.STOPPING, layer_name, message)

    def _run_safe_stop_sequence(
        self,
        emit_progress: Callable[[str], None],
    ) -> SafeStopResult:
        errors: list[str] = []

        if self._safe_stop_wait_for_plot:
            emit_progress("Stopping plot…")
            self._backend.cancel_plot()
            if not self._plot_exit_event.wait(timeout=PLOT_EXIT_WAIT_SECONDS):
                errors.append("Timed out waiting for the plot process to exit.")
        else:
            emit_progress("Stopping plot…")

        emit_progress("Raising pen…")
        pen_status = _call_manual(self._backend.pen_up, "Raise pen", errors)

        pen_ok = _status_connected(pen_status)
        if not pen_ok:
            message = _format_safe_stop_message(pen_ok, False, False, errors)
            return SafeStopResult(
                pen_raised=pen_ok,
                homed=False,
                motors_disabled=False,
                message=message,
                errors=tuple(errors),
            )

        emit_progress("Returning home…")
        home_status = _call_manual(self._backend.walk_home, "Return home", errors)
        homed = _status_connected(home_status)
        if not homed:
            message = _format_safe_stop_message(pen_ok, False, False, errors)
            return SafeStopResult(
                pen_raised=pen_ok,
                homed=False,
                motors_disabled=False,
                message=message,
                errors=tuple(errors),
            )

        emit_progress("Disabling motors…")
        disable_status = _call_manual(self._backend.disable_xy, "Disable motors", errors)
        motors_disabled = _status_connected(disable_status)
        if motors_disabled:
            emit_progress("Motors disabled")

        message = _format_safe_stop_message(pen_ok, homed, motors_disabled, errors)
        return SafeStopResult(
            pen_raised=pen_ok,
            homed=homed,
            motors_disabled=motors_disabled,
            message=message,
            errors=tuple(errors),
        )

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
            self._active_plot_settings = None
            self._cleanup_temp_plot_file()
            self._plot_exit_event.set()
            if self._safe_stop_in_flight:
                return
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

        if operation_name == "safe_stop":
            self._safe_stop_in_flight = False
            stop_result = (
                result
                if isinstance(result, SafeStopResult)
                else SafeStopResult(
                    pen_raised=False,
                    homed=False,
                    motors_disabled=False,
                    message="Plot stopped — cleanup incomplete",
                    errors=("Unknown safe stop failure",),
                )
            )
            layer_name = self._plot_state.layer_name
            phase = PlotPhase.IDLE if stop_result.cleanup_complete else PlotPhase.CANCELLED
            self._set_plot_state(phase, layer_name, stop_result.message)
            self.safe_stop_finished.emit(stop_result)
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

    def _snapshot_plot_settings(self) -> PlotSettings:
        if self._settings_service is None:
            return PlotSettings()
        return self._settings_service.plot_settings

    def _cleanup_temp_plot_file(self) -> None:
        path = self._temp_plot_path
        self._temp_plot_path = None
        if path is None:
            return
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not remove temporary plot file %s", path)


def _status_connected(status: PlotterStatus | None) -> bool:
    return status is not None and status.state is PlotterConnectionState.CONNECTED


def _call_manual(
    operation: Callable[[], PlotterStatus],
    label: str,
    errors: list[str],
) -> PlotterStatus | None:
    try:
        status = operation()
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{label} failed: {exc}")
        return None
    if not _status_connected(status):
        detail = status.message if status is not None else f"{label} failed"
        errors.append(detail)
    return status


def _format_safe_stop_message(
    pen_raised: bool,
    homed: bool,
    motors_disabled: bool,
    errors: list[str],
) -> str:
    if pen_raised and homed and motors_disabled and not errors:
        return "Plot stopped — pen up, home, motors disabled"
    if errors:
        detail = "\n".join(errors)
        return f"Plot stopped — cleanup incomplete\n{detail}"
    return "Plot stopped — cleanup incomplete"


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
