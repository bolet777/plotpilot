"""Build clipped plot SVG from isolated layer text."""

from __future__ import annotations

from plotpilot.geometry.plot_viewport import (
    PlotViewportError,
    PreparedPlotSvg,
    prepare_positioned_plot_svg,
)
from plotpilot.models.artwork_transform import ArtworkTransform
from plotpilot.models.plot_settings import PlotSettings
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
) -> PreparedPlotSvg:
    """Transform and clip *layer_svg_text* to the resolved machine viewport."""
    viewport = resolve_plot_viewport(
        plot_settings,
        fallback=fallback,
        fallback_orientation=fallback_orientation,
    )
    return prepare_positioned_plot_svg(
        layer_svg_text,
        viewport_width_mm=viewport.width_mm,
        viewport_height_mm=viewport.height_mm,
        transform=transform,
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
