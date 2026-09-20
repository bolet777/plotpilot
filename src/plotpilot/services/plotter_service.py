"""Plotter detection, pen control, and layer plotting orchestration."""

from __future__ import annotations

import logging
import os
import tempfile
import threading
import time
import weakref
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal, Slot

from plotpilot.models.plot_estimate import PlotEstimate
from plotpilot.models.plot_job import PlotPhase, PlotResult, PlotState, SafeStopResult
from plotpilot.models.plot_progress import (
    PlotProgress,
    PlotProgressPhase,
    build_running_progress,
    idle_plot_progress,
)
from plotpilot.models.plot_settings import PlotSettings
from plotpilot.models.plotter_status import PlotterConnectionState, PlotterStatus
from plotpilot.models.svg_document import SvgDocument
from plotpilot.models.svg_layer import SvgLayer
from plotpilot.plotter.axidraw import PLOT_CANCEL_WAIT, AxiDrawCliBackend
from plotpilot.plotter.base import PlotterBackend
from plotpilot.services.bounds_service import plot_bounds_block_message
from plotpilot.services.plot_service import plot_svg_for_layer, validate_layer_plot_svg
from plotpilot.services.settings_service import SettingsService
from plotpilot.svg.plot_dimensions import PlotDimensionError

logger = logging.getLogger(__name__)

PLOT_EXIT_WAIT_SECONDS = PLOT_CANCEL_WAIT + 12.0

AUTO_DETECT_INTERVAL_MS = 5000
AUTO_DETECT_RESUME_DELAY_MS = 1000
PLOT_PROGRESS_TICK_MS = 500


class _PlotterTaskSignals(QObject):
    finished = Signal(object, str)
    progress = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)


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


_lifecycle_services: list[weakref.ReferenceType[PlotterService]] = []


def _register_plotter_service(service: PlotterService) -> None:
    if "PYTEST_CURRENT_TEST" not in os.environ:
        return
    _lifecycle_services.append(weakref.ref(service))


def shutdown_all_plotter_services() -> None:
    """Stop timers and cancel plots for services created during pytest."""
    for ref in list(_lifecycle_services):
        service = ref()
        if service is not None:
            service.shutdown()
    _lifecycle_services.clear()


class PlotterService(QObject):
    """Runs plotter I/O off the UI thread and publishes status updates."""

    status_changed = Signal(object)
    plot_state_changed = Signal(object)
    plot_progress_changed = Signal(object)
    safe_stop_finished = Signal(object)

    def __init__(
        self,
        backend: PlotterBackend | None = None,
        *,
        settings_service: SettingsService | None = None,
        auto_detect_interval_ms: int | None = None,
        auto_detect_resume_delay_ms: int | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._backend = backend if backend is not None else AxiDrawCliBackend()
        self._auto_detect_interval_ms = (
            auto_detect_interval_ms
            if auto_detect_interval_ms is not None
            else AUTO_DETECT_INTERVAL_MS
        )
        self._auto_detect_resume_delay_ms = (
            auto_detect_resume_delay_ms
            if auto_detect_resume_delay_ms is not None
            else AUTO_DETECT_RESUME_DELAY_MS
        )
        self._settings_service = settings_service
        self._status = PlotterStatus(
            state=PlotterConnectionState.DISCONNECTED,
            message="Searching for AxiDraw…",
        )
        self._plot_state = PlotState()
        self._detect_in_flight = False
        self._pending_refresh = False
        self._pending_presence_after_resume = False
        self._operation_in_flight = False
        self._plot_in_flight = False
        self._safe_stop_in_flight = False
        self._safe_stop_wait_for_plot = False
        self._plot_exit_event = threading.Event()
        self._temp_plot_path: Path | None = None
        self._active_plot_settings: PlotSettings | None = None
        self._plot_progress = idle_plot_progress()
        self._progress_started_monotonic: float | None = None
        self._progress_frozen_elapsed: float | None = None
        self._progress_estimate_seconds: float | None = None
        self._progress_estimate_unavailable = False
        self._progress_layer_index: int | None = None
        self._progress_layer_count: int | None = None
        self._progress_next_layer_name: str = ""
        self._extra_hardware_busy: Callable[[], bool] | None = None
        self._auto_detect_paused = False
        self._monitor_timer = QTimer(self)
        self._monitor_timer.setInterval(self._auto_detect_interval_ms)
        self._monitor_timer.timeout.connect(self._on_monitor_timer)
        self._resume_timer = QTimer(self)
        self._resume_timer.setSingleShot(True)
        self._resume_timer.setInterval(self._auto_detect_resume_delay_ms)
        self._resume_timer.timeout.connect(self._on_auto_detect_resume)
        self._progress_timer = QTimer(self)
        self._progress_timer.setInterval(PLOT_PROGRESS_TICK_MS)
        self._progress_timer.timeout.connect(self._on_progress_timer)
        self._shutdown = False
        _register_plotter_service(self)

    def shutdown(self) -> None:
        """Stop background work (timers, in-flight plot). Safe when the UI is closing."""
        if self._shutdown:
            return
        self._shutdown = True
        self.stop_automatic_monitoring()
        self._stop_progress_timer()
        if self._plot_in_flight:
            try:
                self._backend.cancel_plot()
            except Exception:  # noqa: BLE001 — best-effort teardown
                pass
        self._plot_exit_event.set()

    @property
    def status(self) -> PlotterStatus:
        return self._status

    @property
    def plot_state(self) -> PlotState:
        return self._plot_state

    @property
    def plot_progress(self) -> PlotProgress:
        return self._plot_progress

    @property
    def backend(self) -> PlotterBackend:
        return self._backend

    def set_extra_hardware_busy(self, predicate: Callable[[], bool] | None) -> None:
        """Optional hook (e.g. multi-layer job) to suspend background detection."""
        self._extra_hardware_busy = predicate

    def chain_extra_hardware_busy(self, predicate: Callable[[], bool]) -> None:
        """Extend the hardware-busy hook without replacing an existing predicate."""
        previous = self._extra_hardware_busy

        def combined() -> bool:
            return (previous() if previous is not None else False) or predicate()

        self._extra_hardware_busy = combined

    def start_automatic_monitoring(self) -> None:
        """Begin passive polling after UI startup (non-blocking)."""
        self._monitor_timer.setInterval(self._auto_detect_interval_ms)
        self._resume_timer.setInterval(self._auto_detect_resume_delay_ms)
        self._auto_detect_paused = False
        if not self._monitor_timer.isActive():
            self._monitor_timer.start()
        QTimer.singleShot(0, self._kick_initial_detection)

    def stop_automatic_monitoring(self) -> None:
        try:
            self._monitor_timer.stop()
            self._resume_timer.stop()
            self._auto_detect_paused = False
            self._pending_presence_after_resume = False
        except RuntimeError:
            pass

    @property
    def _automatic_monitoring_active(self) -> bool:
        try:
            return self._monitor_timer.isActive()
        except RuntimeError:
            return False

    def __del__(self) -> None:
        try:
            self.stop_automatic_monitoring()
        except Exception:  # noqa: BLE001 — best-effort during GC
            pass

    def refresh(self) -> None:
        if self._is_hardware_busy():
            self._pending_refresh = True
            return
        self._begin_full_detect()

    def _kick_initial_detection(self) -> None:
        if self._shutdown:
            return
        if self._is_hardware_busy():
            self._pending_refresh = True
            return
        self._begin_full_detect()

    def _begin_full_detect(self) -> None:
        if self._detect_in_flight:
            self._pending_refresh = True
            return
        self._detect_in_flight = True
        self._run_async(self._backend.detect, "detect")

    def _begin_presence_detect(self) -> None:
        if self._detect_in_flight:
            self._pending_presence_after_resume = True
            return
        self._detect_in_flight = True
        self._run_async(self._backend.detect_presence, "detect_presence")

    def _is_hardware_busy(self) -> bool:
        if (
            self._plot_in_flight
            or self._operation_in_flight
            or self._safe_stop_in_flight
            or self._plot_state.is_active
        ):
            return True
        if self._extra_hardware_busy is not None and self._extra_hardware_busy():
            return True
        return False

    def _pause_auto_detect_for_hardware(self) -> None:
        if not self._automatic_monitoring_active:
            return
        self._auto_detect_paused = True
        self._resume_timer.stop()

    def _schedule_auto_detect_resume(self) -> None:
        if not self._automatic_monitoring_active:
            self._flush_pending_detection_now()
            return
        if not self._resume_timer.isActive():
            self._resume_timer.start()

    def _flush_pending_detection_now(self) -> None:
        if self._is_hardware_busy() or self._detect_in_flight:
            return
        if self._pending_refresh:
            self._pending_refresh = False
            self._begin_full_detect()
            return
        if self._pending_presence_after_resume:
            self._pending_presence_after_resume = False
            self._begin_presence_detect()

    @Slot()
    def _on_auto_detect_resume(self) -> None:
        if self._shutdown:
            return
        if self._is_hardware_busy():
            self._schedule_auto_detect_resume()
            return
        self._auto_detect_paused = False
        if self._pending_refresh:
            self._pending_refresh = False
            self._begin_full_detect()
            return
        if self._pending_presence_after_resume:
            self._pending_presence_after_resume = False
            self._begin_presence_detect()
            return
        if self._automatic_monitoring_active and not self._detect_in_flight:
            self._begin_presence_detect()

    @Slot()
    def _on_monitor_timer(self) -> None:
        if self._shutdown:
            return
        if self._auto_detect_paused or self._is_hardware_busy():
            self._pending_presence_after_resume = True
            return
        if self._detect_in_flight:
            self._pending_presence_after_resume = True
            return
        self._begin_presence_detect()

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
        layer_index: int | None = None,
        layer_count: int | None = None,
        next_layer_name: str | None = None,
    ) -> str | None:
        """Validate and queue a layer plot. Returns an error message or None if started."""
        if self._plot_in_flight or self._safe_stop_in_flight:
            return "A plot is already running."
        if self._plot_state.phase is PlotPhase.STOPPING:
            return "Plotter is finishing stop cleanup."
        if not self._status.is_connected:
            return "AxiDraw is not connected."

        plot_settings = (
            plot_settings if plot_settings is not None else self._snapshot_plot_settings()
        )
        bounds_error = plot_bounds_block_message(document.raw_text, plot_settings)
        if bounds_error is not None:
            return bounds_error

        svg_text = plot_svg_for_layer(document, layer)
        try:
            validate_layer_plot_svg(svg_text)
        except PlotDimensionError as exc:
            return exc.user_message

        temp_path = _write_temp_svg(svg_text)
        self._temp_plot_path = temp_path
        self._active_plot_settings = plot_settings
        self._plot_in_flight = True
        self._pause_auto_detect_for_hardware()
        self._plot_exit_event.clear()
        self._begin_plot_progress(
            layer.name,
            layer_index=layer_index,
            layer_count=layer_count,
            next_layer_name=next_layer_name or "",
        )
        self._set_plot_state(
            PlotPhase.RUNNING,
            layer.name,
            f"Plotting: {layer.name}",
        )

        self._start_plot_estimate(temp_path, self._active_plot_settings)

        def _run_plot() -> PlotResult:
            return self._backend.plot_svg(temp_path, settings=plot_settings)

        self._run_async(_run_plot, "plot")
        return None

    def request_safe_stop(self) -> None:
        """Cancel an active plot (if any) and run raise_pen → walk_home → disable_xy."""
        if self._safe_stop_in_flight:
            return
        self._safe_stop_in_flight = True
        self._pause_auto_detect_for_hardware()
        self._safe_stop_wait_for_plot = self._plot_in_flight
        if self._plot_in_flight:
            # Cancel from the caller thread so a blocked plot worker releases even when
            # the thread pool is saturated and the safe-stop task has not started yet.
            self._backend.cancel_plot()
        layer_name = self._plot_state.layer_name
        self._freeze_plot_progress()
        self._set_plot_state(PlotPhase.STOPPING, layer_name, "Stopping plot…")

        signals = _PlotterTaskSignals(self)
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
        if self._shutdown or not self._safe_stop_in_flight:
            return
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
        if operation_name not in ("plot", "estimate"):
            self._operation_in_flight = True
        if operation_name in ("plot", "pen_up", "pen_down", "safe_stop"):
            self._pause_auto_detect_for_hardware()
        signals = _PlotterTaskSignals(self)
        signals.finished.connect(self._on_task_finished)
        task = _PlotterTask(operation, operation_name, signals)
        QThreadPool.globalInstance().start(task)

    @Slot(object, str)
    def _on_task_finished(self, result: object, operation_name: str) -> None:
        if self._shutdown:
            return
        if operation_name == "estimate":
            self._operation_in_flight = False
            if self._progress_started_monotonic is not None and self._plot_state.phase in (
                PlotPhase.RUNNING,
                PlotPhase.STOPPING,
                PlotPhase.SUCCEEDED,
            ):
                if isinstance(result, PlotEstimate):
                    self._progress_estimate_seconds = result.duration_seconds
                    self._progress_estimate_unavailable = False
                else:
                    self._progress_estimate_unavailable = True
                if self._plot_state.phase is PlotPhase.SUCCEEDED:
                    self._emit_completed_plot_progress()
                else:
                    self._emit_plot_progress(self._progress_phase_for_plot_state())
            return

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
                self._finish_plot_progress(PlotProgressPhase.CANCELLED)
            elif plot_result.success:
                phase = PlotPhase.SUCCEEDED
                message = plot_result.message or "Plot complete"
                self._finish_plot_progress(PlotProgressPhase.COMPLETE, fraction=1.0)
            else:
                phase = PlotPhase.FAILED
                message = f"Plot failed: {plot_result.message}"
                self._finish_plot_progress(PlotProgressPhase.FAILED)
            self._set_plot_state(phase, layer_name, message)
            self._schedule_auto_detect_resume()
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
            if stop_result.cleanup_complete:
                self._finish_plot_progress(PlotProgressPhase.CANCELLED)
            else:
                self._finish_plot_progress(PlotProgressPhase.CANCELLED)
            self._set_plot_state(phase, layer_name, stop_result.message)
            self.safe_stop_finished.emit(stop_result)
            self._schedule_auto_detect_resume()
            return

        self._operation_in_flight = False
        if operation_name in ("detect", "detect_presence"):
            self._detect_in_flight = False
            self._operation_in_flight = False
            if operation_name == "detect" and isinstance(result, PlotterStatus):
                self._publish_status(result)
            elif operation_name == "detect_presence" and isinstance(result, PlotterStatus):
                self._apply_presence_result(result)
            self._finish_detect_queue(bootstrap_presence=operation_name == "detect")
            return

        if isinstance(result, PlotterStatus):
            self._status = result
            self.status_changed.emit(result)
        self._schedule_auto_detect_resume()

    def _finish_detect_queue(self, *, bootstrap_presence: bool = False) -> None:
        if self._pending_refresh and not self._is_hardware_busy():
            self._pending_refresh = False
            self._begin_full_detect()
            return
        if self._pending_presence_after_resume and not self._is_hardware_busy():
            self._pending_presence_after_resume = False
            self._begin_presence_detect()
            return
        if (
            bootstrap_presence
            and self._automatic_monitoring_active
            and not self._auto_detect_paused
            and not self._resume_timer.isActive()
            and not self._is_hardware_busy()
        ):
            self._begin_presence_detect()

    def _apply_presence_result(self, result: PlotterStatus) -> None:
        if result.state is PlotterConnectionState.ERROR:
            if not _same_connection_state(self._status, result):
                self._publish_status(result)
            return

        previous = self._status
        if result.state is PlotterConnectionState.DISCONNECTED:
            if previous.state is PlotterConnectionState.CONNECTED:
                self._publish_status(
                    PlotterStatus(
                        state=PlotterConnectionState.DISCONNECTED,
                        message="Not connected",
                        backend_version=previous.backend_version,
                    )
                )
            return

        if result.state is PlotterConnectionState.CONNECTED:
            if previous.state is not PlotterConnectionState.CONNECTED:
                self._pending_refresh = True
            return

    def _publish_status(self, status: PlotterStatus) -> None:
        if _same_connection_state(self._status, status) and self._status.message == status.message:
            return
        self._status = status
        self.status_changed.emit(status)

    def _set_plot_state(self, phase: PlotPhase, layer_name: str, message: str) -> None:
        self._plot_state = PlotState(phase=phase, layer_name=layer_name, message=message)
        self.plot_state_changed.emit(self._plot_state)
        if phase is PlotPhase.STOPPING:
            self._emit_plot_progress(PlotProgressPhase.STOPPING)
        elif phase is PlotPhase.RUNNING:
            self._emit_plot_progress(PlotProgressPhase.RUNNING)

    def _begin_plot_progress(
        self,
        layer_name: str,
        *,
        layer_index: int | None,
        layer_count: int | None,
        next_layer_name: str,
    ) -> None:
        self._progress_started_monotonic = time.monotonic()
        self._progress_frozen_elapsed = None
        self._progress_estimate_seconds = None
        self._progress_estimate_unavailable = False
        self._progress_layer_index = layer_index
        self._progress_layer_count = layer_count
        self._progress_next_layer_name = next_layer_name
        self._progress_timer.start()
        self._emit_plot_progress(PlotProgressPhase.RUNNING)

    def _start_plot_estimate(self, svg_path: Path, settings: PlotSettings | None) -> None:
        def _run_estimate() -> PlotEstimate | None:
            return self._backend.estimate_plot_svg(svg_path, settings=settings)

        self._run_async(_run_estimate, "estimate")

    def _freeze_plot_progress(self) -> None:
        elapsed = self._current_elapsed_seconds()
        if elapsed is not None:
            self._progress_frozen_elapsed = elapsed

    def _finish_plot_progress(
        self,
        phase: PlotProgressPhase,
        *,
        fraction: float | None = None,
    ) -> None:
        self._stop_progress_timer()
        elapsed = self._current_elapsed_seconds() or 0.0
        if phase is PlotProgressPhase.COMPLETE:
            progress = build_running_progress(
                layer_name=self._plot_state.layer_name,
                elapsed_seconds=elapsed,
                estimated_total_seconds=self._progress_estimate_seconds,
                estimate_unavailable=self._progress_estimate_unavailable,
                layer_index=self._progress_layer_index,
                layer_count=self._progress_layer_count,
                next_layer_name=self._progress_next_layer_name,
                phase=phase,
            )
            progress = PlotProgress(
                phase=phase,
                layer_name=progress.layer_name,
                layer_index=progress.layer_index,
                layer_count=progress.layer_count,
                elapsed_seconds=elapsed,
                estimated_total_seconds=progress.estimated_total_seconds,
                estimated_remaining_seconds=(
                    0.0 if fraction == 1.0 else progress.estimated_remaining_seconds
                ),
                estimated_fraction=1.0 if fraction == 1.0 else progress.estimated_fraction,
                is_estimated=progress.is_estimated,
                estimate_unavailable=progress.estimate_unavailable,
                next_layer_name=progress.next_layer_name,
            )
        else:
            progress = build_running_progress(
                layer_name=self._plot_state.layer_name,
                elapsed_seconds=elapsed,
                estimated_total_seconds=self._progress_estimate_seconds,
                estimate_unavailable=self._progress_estimate_unavailable,
                layer_index=self._progress_layer_index,
                layer_count=self._progress_layer_count,
                next_layer_name=self._progress_next_layer_name,
                phase=phase,
            )
        self._plot_progress = progress
        self.plot_progress_changed.emit(progress)
        if phase in (
            PlotProgressPhase.COMPLETE,
            PlotProgressPhase.FAILED,
            PlotProgressPhase.CANCELLED,
        ):
            self._reset_plot_progress_after_delay()

    def _reset_plot_progress_after_delay(self) -> None:
        def _clear() -> None:
            if self._plot_state.phase in (PlotPhase.RUNNING, PlotPhase.STOPPING):
                return
            self._plot_progress = idle_plot_progress()
            self.plot_progress_changed.emit(self._plot_progress)

        QTimer.singleShot(2500, _clear)

    def _stop_progress_timer(self) -> None:
        try:
            self._progress_timer.stop()
        except RuntimeError:
            pass

    def _current_elapsed_seconds(self) -> float | None:
        if self._progress_frozen_elapsed is not None:
            return self._progress_frozen_elapsed
        if self._progress_started_monotonic is None:
            return None
        return time.monotonic() - self._progress_started_monotonic

    def _progress_phase_for_plot_state(self) -> PlotProgressPhase:
        phase = self._plot_state.phase
        if phase is PlotPhase.STOPPING:
            return PlotProgressPhase.STOPPING
        if phase is PlotPhase.RUNNING:
            return PlotProgressPhase.RUNNING
        return PlotProgressPhase.IDLE

    @Slot()
    def _on_progress_timer(self) -> None:
        if self._shutdown:
            return
        if self._plot_state.phase not in (PlotPhase.RUNNING, PlotPhase.STOPPING):
            return
        self._emit_plot_progress(self._progress_phase_for_plot_state())

    def _emit_completed_plot_progress(self) -> None:
        elapsed = self._current_elapsed_seconds() or 0.0
        base = build_running_progress(
            layer_name=self._plot_state.layer_name,
            elapsed_seconds=elapsed,
            estimated_total_seconds=self._progress_estimate_seconds,
            estimate_unavailable=self._progress_estimate_unavailable,
            layer_index=self._progress_layer_index,
            layer_count=self._progress_layer_count,
            next_layer_name=self._progress_next_layer_name,
            phase=PlotProgressPhase.COMPLETE,
        )
        progress = PlotProgress(
            phase=PlotProgressPhase.COMPLETE,
            layer_name=base.layer_name,
            layer_index=base.layer_index,
            layer_count=base.layer_count,
            elapsed_seconds=elapsed,
            estimated_total_seconds=base.estimated_total_seconds,
            estimated_remaining_seconds=0.0,
            estimated_fraction=1.0,
            is_estimated=base.is_estimated,
            estimate_unavailable=base.estimate_unavailable,
            next_layer_name=base.next_layer_name,
        )
        self._plot_progress = progress
        self.plot_progress_changed.emit(progress)

    def _emit_plot_progress(self, phase: PlotProgressPhase) -> None:
        elapsed = self._current_elapsed_seconds() or 0.0
        progress = build_running_progress(
            layer_name=self._plot_state.layer_name,
            elapsed_seconds=elapsed,
            estimated_total_seconds=self._progress_estimate_seconds,
            estimate_unavailable=self._progress_estimate_unavailable,
            layer_index=self._progress_layer_index,
            layer_count=self._progress_layer_count,
            next_layer_name=self._progress_next_layer_name,
            phase=phase,
        )
        self._plot_progress = progress
        self.plot_progress_changed.emit(progress)

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


def _same_connection_state(previous: PlotterStatus, updated: PlotterStatus) -> bool:
    return previous.state is updated.state


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
