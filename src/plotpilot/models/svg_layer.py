"""Logical layer extracted from an SVG document."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from xml.etree.ElementTree import Element


class LayerSource(StrEnum):
    """How the layer was detected in the SVG."""

    INKSCAPE = "inkscape"
    ROOT_GROUP = "root_group"
    DOCUMENT = "document"


@dataclass(frozen=True, slots=True)
class SvgLayer:
    """One user-visible layer (Inkscape, root group, or synthetic document layer)."""

    layer_id: str
    name: str
    order: int
    element: Element
    representative_color: str | None
    drawable_count: int
    source: LayerSource = LayerSource.INKSCAPE
