"""Prepare isolated layer SVG strings for plotting."""

from __future__ import annotations

from plotpilot.models.svg_document import SvgDocument
from plotpilot.models.svg_layer import SvgLayer
from plotpilot.svg.plot_dimensions import validate_plot_svg_dimensions
from plotpilot.svg.preview import build_layer_preview_svg


def plot_svg_for_layer(document: SvgDocument, layer: SvgLayer) -> str:
    """Build plot-ready SVG for *layer* (same isolation as preview)."""
    return build_layer_preview_svg(document, layer)


def validate_layer_plot_svg(svg_text: str) -> tuple[float, float]:
    """Ensure *svg_text* has plottable page dimensions; return size in mm."""
    return validate_plot_svg_dimensions(svg_text)
