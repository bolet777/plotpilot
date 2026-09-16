"""Layer listing for the current SVG document."""

from __future__ import annotations

from plotpilot.models.svg_document import SvgDocument
from plotpilot.models.svg_layer import SvgLayer
from plotpilot.svg.layers import extract_layers


def layers_for_document(document: SvgDocument) -> list[SvgLayer]:
    """Return layers for *document* (Inkscape layers or one synthetic layer)."""
    return extract_layers(document)
