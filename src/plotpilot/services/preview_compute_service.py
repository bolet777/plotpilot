"""Run layer flatten/clip off the UI thread and drop stale results."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from plotpilot.models import print_margins as print_margin_model
from plotpilot.models.artwork_transform import ArtworkTransform
from plotpilot.models.clip_shape import ClipMode, ClipShape
from plotpilot.models.plot_settings import PlotSettings
from plotpilot.models.print_margins import (
    PrintableArea,
    PrintMargins,
    PrintMarginsError,
    printable_area_for,
)
from plotpilot.models.svg_document import SvgDocument
from plotpilot.models.svg_layer import SvgLayer
from plotpilot.services.layer_geometry import (
    ClippedLayerGeometry,
    PreparedLayerGeometry,
    PreviewResultGate,
    position_and_clip_geometry,
    prepare_composite_geometry,
    prepare_layer_geometry,
)
from plotpilot.services.preview_prepared_service import preview_status_lines
from plotpilot.services.preview_service import composite_preview_layers
from plotpilot.services.preview_work_area import (
    FallbackWorkArea,
    PreviewWorkArea,
    WorkAreaOrientation,
    resolve_plot_viewport,
    resolve_preview_work_area,
)


@dataclass(frozen=True, slots=True)
class InteractivePreview:
    """One finished placement. ``fresh_geometry`` is set only on a cache miss."""

    document_id: int
    layer_id: str
    fresh_geometry: PreparedLayerGeometry | None
    page_width_mm: float
    page_height_mm: float
    clipped: ClippedLayerGeometry
    status_lines: tuple[str, ...]
    work_area: PreviewWorkArea | None
    printable_area: PrintableArea | None = None
    composite_layer_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class HighlightedLayerGeometry:
    """Flattened geometry for the highlighted layer only. Does not drive the ink."""

    document_id: int
    layer_id: str
    geometry: PreparedLayerGeometry


def _interactive_preview_from_geometry(
    *,
    document: SvgDocument,
    layer_id: str,
    geometry: PreparedLayerGeometry,
    fresh_geometry: PreparedLayerGeometry | None,
    transform: ArtworkTransform,
    plot_settings: PlotSettings,
    fallback: FallbackWorkArea,
    fallback_orientation: WorkAreaOrientation,
    print_margins: PrintMargins | None,
    keep_inside: ClipShape | None,
    clip_mode: ClipMode,
    composite_layer_ids: tuple[str, ...] = (),
) -> InteractivePreview:
    viewport = resolve_plot_viewport(
        plot_settings,
        fallback=fallback,
        fallback_orientation=fallback_orientation,
    )
    margins = print_margin_model.active_print_margins(print_margins)
    clipped = position_and_clip_geometry(
        geometry,
        transform,
        viewport_width_mm=viewport.width_mm,
        viewport_height_mm=viewport.height_mm,
        print_margins=margins,
        keep_inside=keep_inside,
        clip_mode=clip_mode,
    )
    try:
        printable = printable_area_for(viewport.width_mm, viewport.height_mm, margins)
    except PrintMarginsError:
        printable = None
    path_count = None if clipped.error_message is not None else clipped.path_count
    status = preview_status_lines(
        geometry.content_counts,
        path_count,
        clipped.error_message,
    )
    return InteractivePreview(
        document_id=id(document),
        layer_id=layer_id,
        fresh_geometry=fresh_geometry,
        page_width_mm=geometry.page_width_mm,
        page_height_mm=geometry.page_height_mm,
        clipped=clipped,
        status_lines=status,
        work_area=resolve_preview_work_area(
            plot_settings,
            fallback=fallback,
            fallback_orientation=fallback_orientation,
        ),
        printable_area=printable,
        composite_layer_ids=composite_layer_ids,
    )


def compute_interactive_preview(
    document: SvgDocument,
    layer: SvgLayer,
    *,
    cached_geometry: PreparedLayerGeometry | None,
    transform: ArtworkTransform,
    plot_settings: PlotSettings,
    fallback: FallbackWorkArea,
    fallback_orientation: WorkAreaOrientation,
    print_margins: PrintMargins | None = None,
    keep_inside: ClipShape | None = None,
    clip_mode: ClipMode = ClipMode.KEEP_INSIDE,
) -> InteractivePreview:
    """Flatten only when *cached_geometry* is missing, then clip. No Qt."""
    geometry = cached_geometry
    fresh: PreparedLayerGeometry | None = None
    if geometry is None:
        geometry = prepare_layer_geometry(document, layer)
        fresh = geometry

    return _interactive_preview_from_geometry(
        document=document,
        layer_id=layer.layer_id,
        geometry=geometry,
        fresh_geometry=fresh,
        transform=transform,
        plot_settings=plot_settings,
        fallback=fallback,
        fallback_orientation=fallback_orientation,
        print_margins=print_margins,
        keep_inside=keep_inside,
        clip_mode=clip_mode,
    )


def compute_interactive_composite_preview(
    document: SvgDocument,
    layers: Sequence[SvgLayer],
    *,
    cached_geometry: PreparedLayerGeometry | None,
    transform: ArtworkTransform,
    plot_settings: PlotSettings,
    fallback: FallbackWorkArea,
    fallback_orientation: WorkAreaOrientation,
    print_margins: PrintMargins | None = None,
    keep_inside: ClipShape | None = None,
    clip_mode: ClipMode = ClipMode.KEEP_INSIDE,
) -> InteractivePreview:
    """Flatten the checked-layer union when needed, then clip. No Qt.

    ``fresh_geometry`` is the composite, never a stand-in for the highlighted layer.
    ``composite_layer_ids`` is the normalized ordered id tuple used as the cache key.
    """
    source = composite_preview_layers(document, layers)
    geometry = cached_geometry
    fresh: PreparedLayerGeometry | None = None
    if geometry is None:
        geometry = prepare_composite_geometry(document, source)
        fresh = geometry
    layer_id = source[0].layer_id if source else ""
    return _interactive_preview_from_geometry(
        document=document,
        layer_id=layer_id,
        geometry=geometry,
        fresh_geometry=fresh,
        transform=transform,
        plot_settings=plot_settings,
        fallback=fallback,
        fallback_orientation=fallback_orientation,
        print_margins=print_margins,
        keep_inside=keep_inside,
        clip_mode=clip_mode,
        composite_layer_ids=tuple(layer.layer_id for layer in source),
    )


def compute_highlighted_layer_geometry(
    document: SvgDocument,
    layer: SvgLayer,
) -> HighlightedLayerGeometry:
    """Flatten one highlighted layer for slider travel. Does not clip or paint."""
    return HighlightedLayerGeometry(
        document_id=id(document),
        layer_id=layer.layer_id,
        geometry=prepare_layer_geometry(document, layer),
    )


class _PreviewTaskSignals(QObject):
    finished = Signal(int, object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)


class _PreviewTask(QRunnable):
    def __init__(
        self,
        generation: int,
        operation: Callable[[], object],
        signals: _PreviewTaskSignals,
    ) -> None:
        super().__init__()
        self._generation = generation
        self._operation = operation
        self.signals = signals

    def run(self) -> None:
        try:
            result = self._operation()
        except Exception as exc:  # noqa: BLE001 — deliver to UI, keep the app alive
            result = exc
        self.signals.finished.emit(self._generation, result)


class PreviewComputeService(QObject):
    """Queues preview placement jobs. The newest generation wins."""

    finished = Signal(int, object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.gate = PreviewResultGate()
        self._signals = _PreviewTaskSignals(self)
        self._signals.finished.connect(self.finished)

    def submit(self, operation: Callable[[], object]) -> int:
        generation = self.gate.issue()
        task = _PreviewTask(generation, operation, self._signals)
        QThreadPool.globalInstance().start(task)
        return generation

    def cancel_pending(self) -> None:
        """Drop in-flight results. The next ``submit`` starts a newer generation."""
        self.gate.issue()

    def shutdown(self) -> None:
        self.gate.shutdown()
        self.blockSignals(True)


__all__ = [
    "HighlightedLayerGeometry",
    "InteractivePreview",
    "PreviewComputeService",
    "compute_highlighted_layer_geometry",
    "compute_interactive_composite_preview",
    "compute_interactive_preview",
]
