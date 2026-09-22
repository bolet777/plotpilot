"""Multi-layer plot job state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from plotpilot.models.plot_settings import PlotSettings


class MultiLayerJobState(StrEnum):
    """Lifecycle for a sequential multi-layer plot job."""

    IDLE = "idle"
    PLOTTING = "plotting"
    WAITING_FOR_PEN_CHANGE = "waiting_for_pen_change"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class MultiLayerJobLayer:
    """Immutable layer entry stored in an active job."""

    layer_id: str
    name: str
    document_order: int
    representative_color: str | None


@dataclass(frozen=True, slots=True)
class MultiLayerPlotJob:
    """Snapshot of a multi-layer plot job."""

    layers: tuple[MultiLayerJobLayer, ...]
    current_index: int
    state: MultiLayerJobState
    settings: PlotSettings
    completed_count: int = 0
    message: str = ""
    error_detail: str = ""

    @property
    def total_layers(self) -> int:
        return len(self.layers)

    @property
    def is_active(self) -> bool:
        return self.state in (
            MultiLayerJobState.PLOTTING,
            MultiLayerJobState.WAITING_FOR_PEN_CHANGE,
        )

    @property
    def current_layer(self) -> MultiLayerJobLayer | None:
        if not self.layers or self.current_index < 0 or self.current_index >= len(self.layers):
            return None
        return self.layers[self.current_index]

    @property
    def next_layer(self) -> MultiLayerJobLayer | None:
        next_index = self.current_index + 1
        if next_index < 0 or next_index >= len(self.layers):
            return None
        return self.layers[next_index]

    @property
    def progress_label(self) -> str:
        if not self.layers or self.state is MultiLayerJobState.IDLE:
            return ""
        if self.state is MultiLayerJobState.WAITING_FOR_PEN_CHANGE:
            if self.current_layer is None:
                return ""
            return f"Layer {self.completed_count} of {self.total_layers} complete"
        layer = self.current_layer
        if layer is None:
            return ""
        human_index = self.current_index + 1
        return f"Plotting {human_index} / {self.total_layers} — {layer.name}"


def idle_multi_layer_job() -> MultiLayerPlotJob:
    return MultiLayerPlotJob(
        layers=(),
        current_index=0,
        state=MultiLayerJobState.IDLE,
        settings=PlotSettings(),
    )
