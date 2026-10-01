"""Stable flattened layer geometry and cheap transform/clip placement."""

from __future__ import annotations

from dataclasses import dataclass

from plotpilot.geometry.plot_viewport import (
    PlotViewportError,
    clip_document_polylines,
    flatten_document_geometry,
)
from plotpilot.models.artwork_transform import ArtworkTransform
from plotpilot.models.svg_document import SvgDocument
from plotpilot.models.svg_layer import SvgLayer
from plotpilot.services.preview_prepared_service import LayerContentCounts, count_layer_content
from plotpilot.services.preview_service import preview_svg_for_layer
from plotpilot.svg.plot_dimensions import PlotDimensionError, parse_physical_size

_NO_INTERSECTION = "No artwork intersects the plot area."


@dataclass(frozen=True, slots=True)
class PreparedLayerGeometry:
    """Immutable pre-flattened geometry for one layer. No Qt objects."""

    context_svg_text: str
    page_width_mm: float
    page_height_mm: float
    content_counts: LayerContentCounts
    polylines: tuple[tuple[tuple[float, float], ...], ...]
    preparation_error: str | None


@dataclass(frozen=True, slots=True)
class ClippedLayerGeometry:
    """Machine-space polylines after placement and clipping."""

    polylines: tuple[tuple[tuple[float, float], ...], ...]
    path_count: int
    error_message: str | None


def prepare_layer_geometry(document: SvgDocument, layer: SvgLayer) -> PreparedLayerGeometry:
    """Isolate, parse, diagnose, and flatten one layer. Independent of placement."""
    context_svg = preview_svg_for_layer(document, layer)
    try:
        physical = parse_physical_size(context_svg)
    except PlotDimensionError as exc:
        return PreparedLayerGeometry(
            context_svg_text=context_svg,
            page_width_mm=0.0,
            page_height_mm=0.0,
            content_counts=count_layer_content(context_svg),
            polylines=(),
            preparation_error=exc.user_message,
        )

    counts = count_layer_content(context_svg)
    try:
        flattened = flatten_document_geometry(context_svg)
    except PlotViewportError as exc:
        return PreparedLayerGeometry(
            context_svg_text=context_svg,
            page_width_mm=physical.width_mm,
            page_height_mm=physical.height_mm,
            content_counts=counts,
            polylines=(),
            preparation_error=exc.user_message,
        )

    return PreparedLayerGeometry(
        context_svg_text=context_svg,
        page_width_mm=physical.width_mm,
        page_height_mm=physical.height_mm,
        content_counts=counts,
        polylines=flattened.polylines,
        preparation_error=None,
    )


def position_and_clip_geometry(
    geometry: PreparedLayerGeometry,
    transform: ArtworkTransform,
    *,
    viewport_width_mm: float,
    viewport_height_mm: float,
) -> ClippedLayerGeometry:
    """Place cached document polylines into the machine viewport."""
    if geometry.preparation_error is not None:
        return ClippedLayerGeometry(
            polylines=(),
            path_count=0,
            error_message=geometry.preparation_error,
        )
    try:
        clipped = clip_document_polylines(
            geometry.polylines,
            transform,
            viewport_width_mm=viewport_width_mm,
            viewport_height_mm=viewport_height_mm,
        )
    except PlotViewportError as exc:
        return ClippedLayerGeometry(polylines=(), path_count=0, error_message=exc.user_message)
    if not clipped:
        return ClippedLayerGeometry(polylines=(), path_count=0, error_message=_NO_INTERSECTION)
    return ClippedLayerGeometry(
        polylines=tuple(clipped),
        path_count=len(clipped),
        error_message=None,
    )


class LayerGeometryCache:
    """Holds flattened geometry for the current document and layer."""

    def __init__(self) -> None:
        self.prepare_count = 0
        self.clip_count = 0
        self._document_id: int | None = None
        self._layer_id: str | None = None
        self._geometry: PreparedLayerGeometry | None = None

    def lookup(self, document_id: int, layer_id: str) -> PreparedLayerGeometry | None:
        if (
            self._geometry is not None
            and self._document_id == document_id
            and self._layer_id == layer_id
        ):
            return self._geometry
        return None

    def store(
        self,
        document_id: int,
        layer_id: str,
        geometry: PreparedLayerGeometry,
    ) -> None:
        self._document_id = document_id
        self._layer_id = layer_id
        self._geometry = geometry

    def invalidate(self) -> None:
        self._document_id = None
        self._layer_id = None
        self._geometry = None

    def clipped_for(
        self,
        document: SvgDocument,
        layer: SvgLayer,
        transform: ArtworkTransform,
        *,
        viewport_width_mm: float,
        viewport_height_mm: float,
    ) -> ClippedLayerGeometry:
        """Prepare on cache miss, then clip. For tests and synchronous callers."""
        geometry = self.lookup(id(document), layer.layer_id)
        if geometry is None:
            geometry = prepare_layer_geometry(document, layer)
            self.prepare_count += 1
            self.store(id(document), layer.layer_id, geometry)
        self.clip_count += 1
        return position_and_clip_geometry(
            geometry,
            transform,
            viewport_width_mm=viewport_width_mm,
            viewport_height_mm=viewport_height_mm,
        )


class PreviewResultGate:
    """Generation counter: only the newest request may update the preview."""

    def __init__(self) -> None:
        self.current = 0
        self.accepting = True

    def issue(self) -> int:
        self.current += 1
        return self.current

    def accept(self, generation: int) -> bool:
        return self.accepting and generation == self.current

    def shutdown(self) -> None:
        self.accepting = False
        self.current += 1


__all__ = [
    "ClippedLayerGeometry",
    "LayerGeometryCache",
    "PreparedLayerGeometry",
    "PreviewResultGate",
    "position_and_clip_geometry",
    "prepare_layer_geometry",
]
