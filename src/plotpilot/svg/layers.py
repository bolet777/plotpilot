"""Inkscape layer detection and metadata extraction (stdlib only)."""

from __future__ import annotations

from xml.etree.ElementTree import Element

from plotpilot.models.svg_document import SvgDocument
from plotpilot.models.svg_layer import SvgLayer
from plotpilot.svg.parse import is_svg_root

INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"

DRAWABLE_TAGS = frozenset(
    {
        "path",
        "line",
        "rect",
        "circle",
        "ellipse",
        "polyline",
        "polygon",
        "text",
    }
)

_TRANSPARENT_VALUES = frozenset({"none", "transparent"})


def _local_tag(tag: str) -> str:
    if tag.startswith("{"):
        _, _, local = tag.partition("}")
        return local
    return tag


def _inkscape_attr(element: Element, local_name: str) -> str | None:
    return element.get(f"{{{INKSCAPE_NS}}}{local_name}")


def is_inkscape_layer(element: Element) -> bool:
    if _local_tag(element.tag) != "g":
        return False
    return _inkscape_attr(element, "groupmode") == "layer"


def _layer_display_name(element: Element, fallback_index: int) -> str:
    label = _inkscape_attr(element, "label")
    if label and label.strip():
        return label.strip()
    element_id = element.get("id")
    if element_id and element_id.strip():
        return element_id.strip()
    return f"Layer {fallback_index}"


def _layer_stable_id(element: Element, order: int) -> str:
    element_id = element.get("id")
    if element_id and element_id.strip():
        return element_id.strip()
    return f"layer-{order}"


def _parse_style_property(style: str, prop: str) -> str | None:
    for part in style.split(";"):
        piece = part.strip()
        if not piece or ":" not in piece:
            continue
        key, _, value = piece.partition(":")
        if key.strip().lower() == prop.lower():
            cleaned = value.strip()
            if cleaned:
                return cleaned
    return None


def _color_from_element(element: Element) -> str | None:
    stroke = element.get("stroke")
    if stroke is None:
        stroke = _parse_style_property(element.get("style") or "", "stroke")
    if stroke and stroke.strip().lower() not in _TRANSPARENT_VALUES:
        return stroke.strip()

    fill = element.get("fill")
    if fill is None:
        fill = _parse_style_property(element.get("style") or "", "fill")
    if fill and fill.strip().lower() not in _TRANSPARENT_VALUES:
        return fill.strip()

    return None


def _element_path(root: Element, target: Element) -> list[Element] | None:
    if root is target:
        return [root]

    for child in root:
        sub = _element_path(child, target)
        if sub is not None:
            return [root, *sub]
    return None


def _is_under_defs(root: Element, element: Element) -> bool:
    path = _element_path(root, element)
    if path is None:
        return False
    return any(_local_tag(node.tag) == "defs" for node in path)


def _iter_subtree(element: Element):
    yield element
    for child in element:
        yield from _iter_subtree(child)


def _representative_color(layer_element: Element, document_root: Element) -> str | None:
    for node in _iter_subtree(layer_element):
        if node is layer_element:
            continue
        if _local_tag(node.tag) not in DRAWABLE_TAGS:
            continue
        if _is_under_defs(document_root, node):
            continue
        color = _color_from_element(node)
        if color is not None:
            return color
    return None


def _count_drawables(layer_element: Element, document_root: Element) -> int:
    count = 0
    for node in _iter_subtree(layer_element):
        if node is layer_element:
            continue
        if _local_tag(node.tag) not in DRAWABLE_TAGS:
            continue
        if _is_under_defs(document_root, node):
            continue
        count += 1
    return count


def _build_layer(element: Element, order: int, name_index: int, document_root: Element) -> SvgLayer:
    return SvgLayer(
        layer_id=_layer_stable_id(element, order),
        name=_layer_display_name(element, name_index),
        order=order,
        element=element,
        representative_color=_representative_color(element, document_root),
        drawable_count=_count_drawables(element, document_root),
    )


def _synthetic_document_layer(document: SvgDocument) -> SvgLayer:
    root = document.root
    name = document.name if document.name else "Document"
    layer_id = root.get("id") or "document"
    if layer_id.strip():
        layer_id = layer_id.strip()
    else:
        layer_id = "document"
    return SvgLayer(
        layer_id=layer_id,
        name=name,
        order=0,
        element=root,
        representative_color=_representative_color(root, root),
        drawable_count=_count_drawables(root, root),
    )


def extract_layers(document: SvgDocument) -> list[SvgLayer]:
    """Return Inkscape layers in document order, or one synthetic document layer."""
    root = document.root
    if not is_svg_root(root):
        return [_synthetic_document_layer(document)]

    layer_elements = [el for el in root.iter() if is_inkscape_layer(el)]
    if not layer_elements:
        return [_synthetic_document_layer(document)]

    layers: list[SvgLayer] = []
    unnamed_counter = 0
    for order, element in enumerate(layer_elements):
        has_label = bool((_inkscape_attr(element, "label") or "").strip())
        has_id = bool((element.get("id") or "").strip())
        if not has_label and not has_id:
            unnamed_counter += 1
            name_index = unnamed_counter
        else:
            name_index = order + 1
        layers.append(_build_layer(element, order, name_index, root))
    return layers
