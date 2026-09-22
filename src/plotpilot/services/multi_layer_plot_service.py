"""Orchestrates sequential multi-layer plotting with pen-change pauses."""

from __future__ import annotations

import logging
import time
from dataclasses import replace

from PySide6.QtCore import QObject, QTimer, Signal

from plotpilot.models.artwork_transform import ArtworkTransform
from plotpilot.models.multi_layer_job import (
    MultiLayerJobLayer,
    MultiLayerJobState,
    MultiLayerPlotJob,
    idle_multi_layer_job,
)
from plotpilot.models.plot_job import PlotPhase, PlotState, SafeStopResult
from plotpilot.models.plot_settings import PlotSettings
from plotpilot.models.plotter_status import PlotterConnectionState, PlotterStatus
from plotpilot.models.svg_document import SvgDocument
from plotpilot.models.svg_layer import SvgLayer
from plotpilot.services.bounds_service import plot_bounds_block_message
from plotpilot.services.plotter_service import PlotterService
from plotpilot.services.preview_work_area import FallbackWorkArea

logger = logging.getLogger(__name__)

_PEN_UP_RETRY_MS = 100
_PEN_UP_RETRY_TIMEOUT_SECONDS = 30.0


class MultiLayerPlotService(QObject):
    """Runs a multi-layer job on top of PlotterService without auto-continuing."""

    job_changed = Signal(object)
    pen_change_required = Signal(object)

    def __init__(self, plotter_service: PlotterService, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._plotter = plotter_service
        plotter_service.chain_extra_hardware_busy(self._plotter_hardware_busy)
        self._job = idle_multi_layer_job()
        self._document: SvgDocument | None = None
        self._layer_by_id: dict[str, SvgLayer] = {}
        self._pen_up_wait = False
        self._pen_up_retry_started_monotonic: float | None = None
        self._continue_in_flight = False
        self._awaiting_stop_cleanup = False
        self._plotter.plot_state_changed.connect(self._on_plot_state_changed)
        self._plotter.pen_up_finished.connect(self._on_pen_up_finished)
        self._plotter.safe_stop_finished.connect(self._on_safe_stop_finished)

    @property
    def job(self) -> MultiLayerPlotJob:
        return self._job

    def start_job(
        self,
        document: SvgDocument,
        layers: list[SvgLayer],
        *,
        settings: PlotSettings,
        artwork_transform: ArtworkTransform | None = None,
        fallback_work_area: FallbackWorkArea = FallbackWorkArea.A4,
    ) -> str | None:
        """Begin plotting the first layer. Returns an error message or None if started."""
        if self._job.is_active:
            return "A multi-layer plot is already running."
        if self._plotter.plot_state.is_active or self._awaiting_stop_cleanup:
            return "A plot is already running."
        if not self._plotter.status.is_connected:
            return "AxiDraw is not connected."
        if not layers:
            return "No layers selected."

        bounds_error = plot_bounds_block_message(document.raw_text, settings)
        if bounds_error is not None:
            return bounds_error

        snapshots = tuple(_snapshot_layer(layer) for layer in layers)
        self._document = document
        self._layer_by_id = {layer.layer_id: layer for layer in layers}
        self._continue_in_flight = False
        self._clear_pen_up_wait()
        transform = artwork_transform or ArtworkTransform.identity()
        self._set_job(
            MultiLayerPlotJob(
                layers=snapshots,
                current_index=0,
                state=MultiLayerJobState.PLOTTING,
                settings=settings,
                artwork_transform=transform,
                fallback_work_area=fallback_work_area.value,
                completed_count=0,
                message=snapshots[0].name,
            )
        )
        return self._start_current_layer()

    def continue_after_pen_change(self) -> str | None:
        if self._job.state is not MultiLayerJobState.WAITING_FOR_PEN_CHANGE:
            return "No layer is waiting to continue."
        if self._continue_in_flight or self._plotter.plot_state.is_active:
            return "Plot already starting."
        if self._pen_up_wait:
            return "Preparing pen for change."

        self._continue_in_flight = True
        self._set_job(
            replace(
                self._job,
                state=MultiLayerJobState.PLOTTING,
                message=self._job.current_layer.name if self._job.current_layer else "",
            )
        )
        error = self._start_current_layer()
        if error is not None:
            self._continue_in_flight = False
            self._fail_job(error)
        return error

    def _plotter_hardware_busy(self) -> bool:
        return self._job.is_active or self._awaiting_stop_cleanup

    def stop_job(self) -> None:
        if self._job.state in (
            MultiLayerJobState.IDLE,
            MultiLayerJobState.COMPLETED,
            MultiLayerJobState.CANCELLED,
            MultiLayerJobState.ERROR,
        ):
            return
        if self._awaiting_stop_cleanup:
            return
        self._clear_pen_up_wait()
        self._awaiting_stop_cleanup = True
        self._plotter.request_safe_stop()

    def _start_current_layer(self) -> str | None:
        layer_snapshot = self._job.current_layer
        document = self._document
        if layer_snapshot is None or document is None:
            self._fail_job("Multi-layer job is missing document context.")
            return "Multi-layer job is missing document context."
        svg_layer = self._layer_by_id.get(layer_snapshot.layer_id)
        if svg_layer is None:
            self._fail_job("Layer is no longer available.")
            return "Layer is no longer available."

        next_layer = self._job.next_layer
        error = self._plotter.start_plot_layer(
            document,
            svg_layer,
            plot_settings=self._job.settings,
            artwork_transform=self._job.artwork_transform,
            fallback_work_area=FallbackWorkArea(self._job.fallback_work_area),
            layer_index=self._job.current_index + 1,
            layer_count=self._job.total_layers,
            next_layer_name=next_layer.name if next_layer is not None else None,
        )
        if error is not None:
            self._fail_job(error)
            return error
        return None

    def _on_plot_state_changed(self, state: PlotState) -> None:
        if self._job.state is not MultiLayerJobState.PLOTTING:
            return
        if state.phase is PlotPhase.RUNNING:
            self._continue_in_flight = False
            layer = self._job.current_layer
            if layer is not None:
                self._set_job(replace(self._job, message=layer.name))
            return
        if state.phase is PlotPhase.SUCCEEDED:
            self._on_layer_plot_succeeded()
            return
        if state.phase is PlotPhase.CANCELLED:
            if self._awaiting_stop_cleanup:
                return
            completed = self._job.completed_count
            total = self._job.total_layers
            self._reset_job(
                replace(
                    self._job,
                    state=MultiLayerJobState.CANCELLED,
                    message=f"Multi-layer plot stopped\n{completed} / {total} layers completed",
                )
            )
            return
        if state.phase is PlotPhase.FAILED:
            layer = self._job.current_layer
            name = layer.name if layer else "Unknown"
            completed = self._job.completed_count
            total = self._job.total_layers
            detail = state.message.removeprefix("Plot failed: ")
            self._reset_job(
                replace(
                    self._job,
                    state=MultiLayerJobState.ERROR,
                    message=(
                        f"Plot failed on layer:\n{name}\n\n{detail}\n\n"
                        f"Completed:\n{completed} / {total}"
                    ),
                    error_detail=detail,
                )
            )

    def _on_layer_plot_succeeded(self) -> None:
        completed = self._job.completed_count + 1
        layer_just_finished = self._job.layers[self._job.current_index]
        logger.debug(
            "multi-layer: layer %s plot succeeded (%s/%s)",
            completed,
            completed,
            self._job.total_layers,
        )
        is_last = completed >= self._job.total_layers
        if is_last:
            total = self._job.total_layers
            self._reset_job(
                MultiLayerPlotJob(
                    layers=self._job.layers,
                    current_index=self._job.current_index,
                    state=MultiLayerJobState.COMPLETED,
                    settings=self._job.settings,
                    completed_count=completed,
                    message=f"✓ Multi-layer plot complete\n{total} / {total} layers plotted",
                )
            )
            return

        self._set_job(
            replace(
                self._job,
                completed_count=completed,
                current_index=self._job.current_index + 1,
            )
        )
        self._begin_pen_up_for_pen_change(layer_just_finished.name)

    def _begin_pen_up_for_pen_change(self, completed_layer_name: str) -> None:
        nxt = self._job.current_layer
        if nxt is None:
            self._fail_job("Missing next layer after plot success.")
            return
        logger.debug(
            "multi-layer: requesting pen up before pen change to layer %s (after %s)",
            nxt.name,
            completed_layer_name,
        )
        self._pen_up_wait = True
        self._pen_up_retry_started_monotonic = time.monotonic()
        self._request_pen_up()

    def _request_pen_up(self) -> None:
        if not self._pen_up_wait:
            return
        if self._job.state is not MultiLayerJobState.PLOTTING:
            self._clear_pen_up_wait()
            return
        if self._awaiting_stop_cleanup:
            self._clear_pen_up_wait()
            return

        if self._plotter.pen_up():
            logger.debug("multi-layer: pen up queued")
            return

        started = self._pen_up_retry_started_monotonic
        if started is not None and time.monotonic() - started > _PEN_UP_RETRY_TIMEOUT_SECONDS:
            self._clear_pen_up_wait()
            self._fail_job("Timed out waiting to raise pen before pen change.")
            return

        logger.debug("multi-layer: pen up deferred, will retry")
        QTimer.singleShot(_PEN_UP_RETRY_MS, self._request_pen_up)

    def _on_pen_up_finished(self, result: object) -> None:
        if not self._pen_up_wait:
            return
        self._clear_pen_up_wait()
        status = result if isinstance(result, PlotterStatus) else None
        if status is None:
            self._fail_job("Pen raise failed before pen change.")
            return
        if status.state is PlotterConnectionState.ERROR:
            self._fail_job(status.message or "Could not raise pen before pen change.")
            return
        if status.state is not PlotterConnectionState.CONNECTED:
            self._fail_job("AxiDraw disconnected before pen change.")
            return
        logger.debug("multi-layer: pen up finished")
        self._enter_pen_change_wait()

    def _on_safe_stop_finished(self, result: SafeStopResult) -> None:
        if not self._awaiting_stop_cleanup:
            return
        self._awaiting_stop_cleanup = False
        completed = self._job.completed_count
        total = self._job.total_layers
        layer_note = f"Multi-layer plot stopped\n{completed} / {total} layers completed"
        body = f"{layer_note}\n\n{result.message}"
        self._reset_job(
            MultiLayerPlotJob(
                layers=self._job.layers,
                current_index=self._job.current_index,
                state=MultiLayerJobState.CANCELLED,
                settings=self._job.settings,
                completed_count=completed,
                message=body,
            )
        )

    def _enter_pen_change_wait(self) -> None:
        nxt = self._job.current_layer
        if nxt is None:
            self._fail_job("Missing next layer after pen raise.")
            return
        logger.debug("multi-layer: waiting for pen change to layer %s", nxt.name)
        self._set_job(
            replace(
                self._job,
                state=MultiLayerJobState.WAITING_FOR_PEN_CHANGE,
                message=nxt.name,
            )
        )
        self.pen_change_required.emit(nxt)

    def _fail_job(self, message: str) -> None:
        completed = self._job.completed_count
        total = self._job.total_layers
        layer = self._job.current_layer
        name = layer.name if layer else "Unknown"
        if self._job.state is MultiLayerJobState.PLOTTING and completed < total:
            body = (
                f"Plot failed on layer:\n{name}\n\n{message}\n\nCompleted:\n{completed} / {total}"
            )
        else:
            body = message
        self._reset_job(
            replace(
                self._job,
                state=MultiLayerJobState.ERROR,
                message=body,
                error_detail=message,
            )
        )

    def _set_job(self, job: MultiLayerPlotJob) -> None:
        self._job = job
        self.job_changed.emit(job)

    def _clear_pen_up_wait(self) -> None:
        self._pen_up_wait = False
        self._pen_up_retry_started_monotonic = None

    def _reset_job(self, final_job: MultiLayerPlotJob) -> None:
        self._set_job(final_job)
        self._document = None
        self._layer_by_id = {}
        self._continue_in_flight = False
        self._clear_pen_up_wait()


def _snapshot_layer(layer: SvgLayer) -> MultiLayerJobLayer:
    return MultiLayerJobLayer(
        layer_id=layer.layer_id,
        name=layer.name,
        document_order=layer.order,
        representative_color=layer.representative_color,
    )
