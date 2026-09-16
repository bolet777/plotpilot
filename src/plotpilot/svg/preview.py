"""Build isolated SVG previews for a single layer (stdlib only)."""

from __future__ import annotations

import copy
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import Element

from plotpilot.models.svg_document import SvgDocument
from plotpilot.models.svg_layer import SvgLayer
from plotpilot.svg.parse import is_svg_root


def _local_tag(tag: str) -> str:
    if tag.startswith("{"):
        _, _, local = tag.partition("}")
        return local
    return tag


def _is_document_layer(document: SvgDocument, layer: SvgLayer) -> bool:
    return layer.element is document.root or is_svg_root(layer.element)


def _copy_root_shell(source_root: Element) -> Element:
    preview_root = Element(source_root.tag, dict(source_root.attrib))
    return preview_root


def _append_defs(source_root: Element, preview_root: Element) -> None:
    for child in source_root:
        if _local_tag(child.tag) == "defs":
            preview_root.append(copy.deepcopy(child))


def build_layer_preview_svg(document: SvgDocument, layer: SvgLayer) -> str:
    """Return UTF-8 SVG text for *layer* without modifying *document*."""
    if _is_document_layer(document, layer):
        return document.raw_text

    source_root = document.root
    preview_root = _copy_root_shell(source_root)
    _append_defs(source_root, preview_root)
    preview_root.append(copy.deepcopy(layer.element))

    return ET.tostring(preview_root, encoding="unicode", xml_declaration=True)
