"""Layer preview orchestration for the UI."""

from __future__ import annotations

from plotpilot.models.svg_document import SvgDocument
from plotpilot.models.svg_layer import SvgLayer
from plotpilot.svg.preview import build_layer_preview_svg


def preview_svg_for_layer(document: SvgDocument, layer: SvgLayer) -> str:
    """Build ephemeral SVG text for preview rendering."""
    return build_layer_preview_svg(document, layer)
