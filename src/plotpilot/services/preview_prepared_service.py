"""Build prepared plot geometry for preview parity with axicli output."""

from __future__ import annotations

import io
from dataclasses import dataclass

from svgelements import SVG, Group, Image, Shape, Text

from plotpilot.geometry.plot_viewport import PlotViewportError, PreparedPlotSvg
from plotpilot.models.artwork_transform import ArtworkTransform
from plotpilot.models.plot_settings import PlotSettings
from plotpilot.models.svg_document import SvgDocument
from plotpilot.models.svg_layer import SvgLayer
from plotpilot.services.positioned_plot_service import prepare_layer_plot_svg
from plotpilot.services.preview_service import preview_svg_for_layer
from plotpilot.services.preview_work_area import FallbackWorkArea
from plotpilot.svg.plot_dimensions import PlotDimensionError, parse_physical_size


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
) -> PreparedLayerPreview:
    """Prepare layer geometry for preview using the plot pipeline."""
    context_svg = preview_svg_for_layer(document, layer)
    try:
        physical = parse_physical_size(context_svg)
    except PlotDimensionError as exc:
        return PreparedLayerPreview(
            context_svg_text=context_svg,
            page_width_mm=0.0,
            page_height_mm=0.0,
            prepared=None,
            preparation_error=exc.user_message,
            content_counts=count_layer_content(context_svg),
            status_lines=(exc.user_message,),
        )

    counts = count_layer_content(context_svg)
    try:
        prepared = prepare_layer_plot_svg(
            context_svg,
            plot_settings=plot_settings,
            transform=transform,
            fallback=fallback,
        )
        error_message: str | None = None
    except PlotViewportError as exc:
        prepared = None
        error_message = exc.user_message

    status_lines = _status_lines(counts, prepared, error_message)
    return PreparedLayerPreview(
        context_svg_text=context_svg,
        page_width_mm=physical.width_mm,
        page_height_mm=physical.height_mm,
        prepared=prepared,
        preparation_error=error_message,
        content_counts=counts,
        status_lines=status_lines,
    )


def _status_lines(
    counts: LayerContentCounts,
    prepared: PreparedPlotSvg | None,
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
    if prepared is not None and counts.stroke_shapes > prepared.path_count:
        ignored += counts.stroke_shapes - prepared.path_count

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


__all__ = [
    "LayerContentCounts",
    "PreparedLayerPreview",
    "build_prepared_layer_preview",
    "count_layer_content",
]
