"""Layer preview orchestration for the UI."""

from __future__ import annotations

from collections.abc import Sequence

from plotpilot.models.svg_document import SvgDocument
from plotpilot.models.svg_layer import SvgLayer
from plotpilot.svg.preview import (
    build_layer_preview_svg,
    build_layers_preview_svg,
    composite_preview_layers,
)


def preview_svg_for_layer(document: SvgDocument, layer: SvgLayer) -> str:
    """Build ephemeral SVG text for preview rendering."""
    return build_layer_preview_svg(document, layer)


def preview_svg_for_layers(document: SvgDocument, layers: Sequence[SvgLayer]) -> str:
    """Build ephemeral SVG text for the normalized checked-layer set."""
    source = composite_preview_layers(document, layers)
    if len(source) == 1:
        return build_layer_preview_svg(document, source[0])
    if not source:
        message = "No layers to preview"
        raise ValueError(message)
    return build_layers_preview_svg(document, source)


__all__ = [
    "composite_preview_layers",
    "preview_svg_for_layer",
    "preview_svg_for_layers",
]
