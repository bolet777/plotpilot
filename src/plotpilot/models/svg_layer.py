"""Logical layer extracted from an SVG document."""

from __future__ import annotations

from dataclasses import dataclass
from xml.etree.ElementTree import Element


@dataclass(frozen=True, slots=True)
class SvgLayer:
    """One user-visible layer (Inkscape layer or synthetic whole-document layer)."""

    layer_id: str
    name: str
    order: int
    element: Element
    representative_color: str | None
    drawable_count: int
