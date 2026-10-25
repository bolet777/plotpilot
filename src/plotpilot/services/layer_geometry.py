"""Stable flattened layer geometry and cheap transform/clip placement."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from plotpilot.geometry.plot_viewport import (
    PlotViewportError,
    clip_document_polylines,
    flatten_document_geometry,
)
from plotpilot.models import print_margins as print_margin_model
from plotpilot.models.artwork_transform import ArtworkTransform
from plotpilot.models.clip_shape import ClipMode, ClipShape
from plotpilot.models.print_margins import PrintMargins, PrintMarginsError, printable_area_for
from plotpilot.models.svg_document import SvgDocument
from plotpilot.models.svg_layer import SvgLayer
from plotpilot.services.preview_prepared_service import LayerContentCounts, count_layer_content
from plotpilot.services.preview_service import preview_svg_for_layer, preview_svg_for_layers
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


def _geometry_from_context_svg(context_svg: str) -> PreparedLayerGeometry:
    """Parse, diagnose, and flatten an already isolated preview SVG."""
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


def prepare_layer_geometry(document: SvgDocument, layer: SvgLayer) -> PreparedLayerGeometry:
    """Isolate, parse, diagnose, and flatten one layer. Independent of placement."""
    return _geometry_from_context_svg(preview_svg_for_layer(document, layer))


def prepare_composite_geometry(
    document: SvgDocument,
    layers: Sequence[SvgLayer],
) -> PreparedLayerGeometry:
    """Compose the checked layers, then flatten once. Independent of placement.

    Descendants of a checked ancestor are omitted so nested groups are not drawn twice.
    """
    return _geometry_from_context_svg(preview_svg_for_layers(document, layers))


def position_and_clip_geometry(
    geometry: PreparedLayerGeometry,
    transform: ArtworkTransform,
    *,
    viewport_width_mm: float,
    viewport_height_mm: float,
    print_margins: PrintMargins | None = None,
    keep_inside: ClipShape | None = None,
    clip_mode: ClipMode = ClipMode.KEEP_INSIDE,
) -> ClippedLayerGeometry:
    """Place cached document polylines and clip them to the printable area.

    ``keep_inside`` further limits the clip to a rectangle overlap or an ellipse,
    or removes the inside of that shape. ``None`` keeps today's margin clip.
    """
    if geometry.preparation_error is not None:
        return ClippedLayerGeometry(
            polylines=(),
            path_count=0,
            error_message=geometry.preparation_error,
        )
    margins = print_margin_model.active_print_margins(print_margins)
    try:
        area = printable_area_for(viewport_width_mm, viewport_height_mm, margins)
        clipped = clip_document_polylines(
            geometry.polylines,
            transform,
            viewport_width_mm=viewport_width_mm,
            viewport_height_mm=viewport_height_mm,
            clip_x_min_mm=area.x_mm,
            clip_y_min_mm=area.y_mm,
            clip_x_max_mm=area.x_max_mm,
            clip_y_max_mm=area.y_max_mm,
            page_width_mm=geometry.page_width_mm,
            page_height_mm=geometry.page_height_mm,
            keep_inside=keep_inside,
            clip_mode=clip_mode,
        )
    except PrintMarginsError as exc:
        return ClippedLayerGeometry(polylines=(), path_count=0, error_message=exc.user_message)
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
        print_margins: PrintMargins | None = None,
        keep_inside: ClipShape | None = None,
        clip_mode: ClipMode = ClipMode.KEEP_INSIDE,
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
            print_margins=print_margins,
            keep_inside=keep_inside,
            clip_mode=clip_mode,
        )


class PreviewCompositeCache:
    """Flattened geometry for one checked-layer preview set.

    Separate from :class:`LayerGeometryCache`. The highlighted-layer cache stays
    the single selected layer (slider travel). This slot is keyed by document
    identity and the ordered tuple of normalized layer ids — the same inputs
    that invalidate flattened preview geometry. Placement (transform, margins,
    clip) is applied later and is not part of the key.
    """

    def __init__(self) -> None:
        self.prepare_count = 0
        self.clip_count = 0
        self._document_id: int | None = None
        self._layer_ids: tuple[str, ...] | None = None
        self._geometry: PreparedLayerGeometry | None = None

    def lookup(
        self,
        document_id: int,
        layer_ids: tuple[str, ...],
    ) -> PreparedLayerGeometry | None:
        if (
            self._geometry is not None
            and self._document_id == document_id
            and self._layer_ids == layer_ids
        ):
            return self._geometry
        return None

    def store(
        self,
        document_id: int,
        layer_ids: tuple[str, ...],
        geometry: PreparedLayerGeometry,
    ) -> None:
        self._document_id = document_id
        self._layer_ids = layer_ids
        self._geometry = geometry

    def invalidate(self) -> None:
        self._document_id = None
        self._layer_ids = None
        self._geometry = None


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
    "PreviewCompositeCache",
    "PreviewResultGate",
    "position_and_clip_geometry",
    "prepare_composite_geometry",
    "prepare_layer_geometry",
]
