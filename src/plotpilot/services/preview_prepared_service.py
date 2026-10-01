"""Build prepared plot geometry for preview parity with axicli output."""

from __future__ import annotations

import io
from dataclasses import dataclass

from svgelements import SVG, Group, Image, Shape, Text

from plotpilot.geometry.plot_viewport import (
    PlotViewportError,
    PreparedPlotSvg,
    emit_validated_plot_svg,
)
from plotpilot.models import print_margins as print_margin_model
from plotpilot.models.artwork_transform import ArtworkTransform
from plotpilot.models.plot_settings import PlotSettings
from plotpilot.models.print_margins import PrintMargins, PrintMarginsError, printable_area_for
from plotpilot.models.svg_document import SvgDocument
from plotpilot.models.svg_layer import SvgLayer
from plotpilot.services.preview_work_area import (
    FallbackWorkArea,
    WorkAreaOrientation,
    resolve_plot_viewport,
)


@dataclass(frozen=True, slots=True)
class LayerContentCounts:
    stroke_shapes: int
    fill_only_shapes: int
    text_elements: int
    image_elements: int

    @property
    def non_plottable(self) -> int:
        return self.fill_only_shapes + self.text_elements + self.image_elements


@dataclass(frozen=True, slots=True)
class PreparedLayerPreview:
    """Authoritative preview state: same preparation as plot output."""

    context_svg_text: str
    page_width_mm: float
    page_height_mm: float
    prepared: PreparedPlotSvg | None
    preparation_error: str | None
    content_counts: LayerContentCounts
    status_lines: tuple[str, ...]


def count_layer_content(svg_text: str) -> LayerContentCounts:
    """Count drawable categories in isolated layer SVG (diagnostics only)."""
    root = SVG.parse(io.StringIO(svg_text))
    stroke_shapes = 0
    fill_only_shapes = 0
    text_elements = 0
    image_elements = 0

    for element in root.elements():
        if isinstance(element, Text):
            text_elements += 1
            continue
        if isinstance(element, Image):
            image_elements += 1
            continue
        if isinstance(element, (SVG, Group)) or not isinstance(element, Shape):
            continue
        has_stroke = _shape_has_stroke(element)
        has_fill = _shape_has_fill(element)
        if has_stroke:
            stroke_shapes += 1
        elif has_fill:
            fill_only_shapes += 1

    return LayerContentCounts(
        stroke_shapes=stroke_shapes,
        fill_only_shapes=fill_only_shapes,
        text_elements=text_elements,
        image_elements=image_elements,
    )


def build_prepared_layer_preview(
    document: SvgDocument,
    layer: SvgLayer,
    *,
    plot_settings: PlotSettings,
    transform: ArtworkTransform,
    fallback: FallbackWorkArea = FallbackWorkArea.A4,
    fallback_orientation: WorkAreaOrientation = WorkAreaOrientation.PORTRAIT,
    print_margins: PrintMargins | None = None,
) -> PreparedLayerPreview:
    """Prepare layer geometry for preview using the plot pipeline."""
    from plotpilot.services.layer_geometry import position_and_clip_geometry, prepare_layer_geometry

    geometry = prepare_layer_geometry(document, layer)
    if geometry.preparation_error is not None and not geometry.polylines:
        if geometry.page_width_mm <= 0 or geometry.page_height_mm <= 0:
            return PreparedLayerPreview(
                context_svg_text=geometry.context_svg_text,
                page_width_mm=geometry.page_width_mm,
                page_height_mm=geometry.page_height_mm,
                prepared=None,
                preparation_error=geometry.preparation_error,
                content_counts=geometry.content_counts,
                status_lines=(geometry.preparation_error,),
            )

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
    )
    prepared: PreparedPlotSvg | None = None
    error_message = clipped.error_message
    if error_message is None:
        try:
            area = printable_area_for(viewport.width_mm, viewport.height_mm, margins)
            prepared = emit_validated_plot_svg(
                list(clipped.polylines),
                viewport_width_mm=viewport.width_mm,
                viewport_height_mm=viewport.height_mm,
                clip_x_min_mm=area.x_mm,
                clip_y_min_mm=area.y_mm,
                clip_x_max_mm=area.x_max_mm,
                clip_y_max_mm=area.y_max_mm,
            )
        except PrintMarginsError as exc:
            error_message = exc.user_message
        except PlotViewportError as exc:
            error_message = exc.user_message

    path_count = prepared.path_count if prepared is not None else None
    status_lines = _status_lines(geometry.content_counts, path_count, error_message)
    return PreparedLayerPreview(
        context_svg_text=geometry.context_svg_text,
        page_width_mm=geometry.page_width_mm,
        page_height_mm=geometry.page_height_mm,
        prepared=prepared,
        preparation_error=error_message,
        content_counts=geometry.content_counts,
        status_lines=status_lines,
    )


def _status_lines(
    counts: LayerContentCounts,
    path_count: int | None,
    preparation_error: str | None,
) -> tuple[str, ...]:
    lines: list[str] = []
    if preparation_error is not None:
        lines.append(preparation_error)

    if counts.text_elements:
        lines.append("Text will not be plotted — convert to paths")
    if counts.image_elements:
        lines.append("Images are not plottable")

    ignored = counts.non_plottable
    if path_count is not None and counts.stroke_shapes > path_count:
        ignored += counts.stroke_shapes - path_count

    if ignored == 1:
        lines.append("1 element is not plottable")
    elif ignored > 1:
        lines.append(f"{ignored} elements are not plottable")

    return tuple(lines)


def _shape_has_stroke(element: Shape) -> bool:
    stroke = getattr(element, "stroke", None)
    if stroke is None:
        return False
    value = str(stroke.value).lower() if hasattr(stroke, "value") else str(stroke).lower()
    return value not in {"none", "transparent"}


def _shape_has_fill(element: Shape) -> bool:
    fill = getattr(element, "fill", None)
    if fill is None:
        return False
    value = str(fill.value).lower() if hasattr(fill, "value") else str(fill).lower()
    return value not in {"none", "transparent"}


def preview_status_lines(
    counts: LayerContentCounts,
    path_count: int | None,
    preparation_error: str | None,
) -> tuple[str, ...]:
    """User-facing preview warnings for one prepared layer."""
    return _status_lines(counts, path_count, preparation_error)


__all__ = [
    "LayerContentCounts",
    "PreparedLayerPreview",
    "build_prepared_layer_preview",
    "count_layer_content",
    "preview_status_lines",
]
