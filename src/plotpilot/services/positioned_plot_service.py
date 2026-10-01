"""Build clipped plot SVG from isolated layer text."""

from __future__ import annotations

from plotpilot.geometry.plot_viewport import (
    PlotViewportError,
    PreparedPlotSvg,
    prepare_positioned_plot_svg,
)
from plotpilot.models import print_margins as print_margin_model
from plotpilot.models.artwork_transform import ArtworkTransform
from plotpilot.models.plot_settings import PlotSettings
from plotpilot.models.print_margins import PrintMargins, PrintMarginsError, printable_area_for
from plotpilot.services.preview_work_area import (
    FallbackWorkArea,
    PlotViewport,
    WorkAreaOrientation,
    resolve_plot_viewport,
)


def prepare_layer_plot_svg(
    layer_svg_text: str,
    *,
    plot_settings: PlotSettings,
    transform: ArtworkTransform,
    fallback: FallbackWorkArea = FallbackWorkArea.A4,
    fallback_orientation: WorkAreaOrientation = WorkAreaOrientation.PORTRAIT,
    print_margins: PrintMargins | None = None,
) -> PreparedPlotSvg:
    """Transform and clip *layer_svg_text* to the printable area inside the viewport."""
    viewport = resolve_plot_viewport(
        plot_settings,
        fallback=fallback,
        fallback_orientation=fallback_orientation,
    )
    margins = print_margin_model.active_print_margins(print_margins)
    try:
        area = printable_area_for(viewport.width_mm, viewport.height_mm, margins)
    except PrintMarginsError as exc:
        raise PlotViewportError(exc.user_message) from exc
    return prepare_positioned_plot_svg(
        layer_svg_text,
        viewport_width_mm=viewport.width_mm,
        viewport_height_mm=viewport.height_mm,
        transform=transform,
        clip_x_min_mm=area.x_mm,
        clip_y_min_mm=area.y_mm,
        clip_x_max_mm=area.x_max_mm,
        clip_y_max_mm=area.y_max_mm,
    )


def plot_viewport_for_settings(
    plot_settings: PlotSettings,
    *,
    fallback: FallbackWorkArea = FallbackWorkArea.A4,
    fallback_orientation: WorkAreaOrientation = WorkAreaOrientation.PORTRAIT,
) -> PlotViewport:
    return resolve_plot_viewport(
        plot_settings,
        fallback=fallback,
        fallback_orientation=fallback_orientation,
    )


__all__ = [
    "PlotViewportError",
    "PreparedPlotSvg",
    "plot_viewport_for_settings",
    "prepare_layer_plot_svg",
]
