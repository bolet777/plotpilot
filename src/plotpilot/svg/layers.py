"""Inkscape layer detection and metadata extraction (stdlib only)."""

from __future__ import annotations

import re
from xml.etree.ElementTree import Element

from plotpilot.models.svg_document import SvgDocument
from plotpilot.models.svg_layer import LayerSource, SvgLayer
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


def _humanize_id(element_id: str) -> str:
    stripped = element_id.strip()
    if not stripped:
        return stripped
    if re.search(r"[-_]", stripped):
        result = " ".join(re.split(r"[-_]+", stripped))
    else:
        result = stripped
    return result[0].upper() + result[1:] if result else result


def _root_group_display_name(element: Element, fallback_index: int) -> str:
    label = _inkscape_attr(element, "label")
    if label and label.strip():
        return label.strip()
    aria = element.get("aria-label")
    if aria and aria.strip():
        return aria.strip()
    element_id = element.get("id")
    if element_id and element_id.strip():
        return _humanize_id(element_id)
    return f"Group {fallback_index}"


def _is_meaningful_root_group(
    element: Element,
    document_root: Element,
    parent_map: dict[Element, Element],
) -> bool:
    return _count_drawables(element, document_root, parent_map) > 0


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


def _build_parent_map(root: Element) -> dict[Element, Element]:
    parent_map: dict[Element, Element] = {}
    for parent in root.iter():
        for child in parent:
            parent_map[child] = parent
    return parent_map


def _is_under_defs(
    document_root: Element,
    element: Element,
    parent_map: dict[Element, Element],
) -> bool:
    node: Element | None = element
    while node is not None and node is not document_root:
        if _local_tag(node.tag) == "defs":
            return True
        node = parent_map.get(node)
    return False


def _is_layer_hidden(element: Element) -> bool:
    display = element.get("display")
    if display is not None and display.strip().lower() == "none":
        return True
    visibility = element.get("visibility")
    if visibility is not None and visibility.strip().lower() in {"hidden", "collapse"}:
        return True
    style = element.get("style") or ""
    hidden_display = _parse_style_property(style, "display")
    if hidden_display is not None and hidden_display.strip().lower() == "none":
        return True
    hidden_visibility = _parse_style_property(style, "visibility")
    if hidden_visibility is not None and hidden_visibility.strip().lower() in {
        "hidden",
        "collapse",
    }:
        return True
    return False


def _iter_subtree(element: Element):
    yield element
    for child in element:
        yield from _iter_subtree(child)


def _representative_color(
    layer_element: Element,
    document_root: Element,
    parent_map: dict[Element, Element],
) -> str | None:
    for node in _iter_subtree(layer_element):
        if node is layer_element:
            continue
        if _local_tag(node.tag) not in DRAWABLE_TAGS:
            continue
        if _is_under_defs(document_root, node, parent_map):
            continue
        color = _color_from_element(node)
        if color is not None:
            return color
    return None


def _count_drawables(
    layer_element: Element,
    document_root: Element,
    parent_map: dict[Element, Element],
) -> int:
    count = 0
    for node in _iter_subtree(layer_element):
        if node is layer_element:
            continue
        if _local_tag(node.tag) not in DRAWABLE_TAGS:
            continue
        if _is_under_defs(document_root, node, parent_map):
            continue
        count += 1
    return count


def _build_layer(
    element: Element,
    order: int,
    name_index: int,
    document_root: Element,
    parent_map: dict[Element, Element],
    *,
    source: LayerSource,
    display_name_fn=_layer_display_name,
) -> SvgLayer:
    return SvgLayer(
        layer_id=_layer_stable_id(element, order),
        name=display_name_fn(element, name_index),
        order=order,
        element=element,
        representative_color=_representative_color(element, document_root, parent_map),
        drawable_count=_count_drawables(element, document_root, parent_map),
        source=source,
        hidden=_is_layer_hidden(element),
    )


def _synthetic_document_layer(
    document: SvgDocument,
    parent_map: dict[Element, Element],
) -> SvgLayer:
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
        representative_color=_representative_color(root, root, parent_map),
        drawable_count=_count_drawables(root, root, parent_map),
        source=LayerSource.DOCUMENT,
    )


def _extract_inkscape_layers(
    root: Element,
    parent_map: dict[Element, Element],
) -> list[SvgLayer]:
    layer_elements = [
        el
        for el in root.iter()
        if is_inkscape_layer(el) and not _is_under_defs(root, el, parent_map)
    ]
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
        layers.append(
            _build_layer(
                element,
                order,
                name_index,
                root,
                parent_map,
                source=LayerSource.INKSCAPE,
            )
        )
    return layers


def _extract_root_group_layers(
    root: Element,
    parent_map: dict[Element, Element],
) -> list[SvgLayer]:
    group_elements: list[Element] = []
    for child in root:
        if _local_tag(child.tag) != "g":
            continue
        if _is_meaningful_root_group(child, root, parent_map):
            group_elements.append(child)

    layers: list[SvgLayer] = []
    unnamed_counter = 0
    for order, element in enumerate(group_elements):
        has_label = bool((_inkscape_attr(element, "label") or "").strip())
        has_aria = bool((element.get("aria-label") or "").strip())
        has_id = bool((element.get("id") or "").strip())
        if not has_label and not has_aria and not has_id:
            unnamed_counter += 1
            name_index = unnamed_counter
        else:
            name_index = order + 1
        layers.append(
            _build_layer(
                element,
                order,
                name_index,
                root,
                parent_map,
                source=LayerSource.ROOT_GROUP,
                display_name_fn=_root_group_display_name,
            )
        )
    return layers


def extract_layers(document: SvgDocument) -> list[SvgLayer]:
    """Return layers: Inkscape, else root groups, else one synthetic document layer."""
    root = document.root
    parent_map = _build_parent_map(root)
    if not is_svg_root(root):
        return [_synthetic_document_layer(document, parent_map)]

    inkscape_layers = _extract_inkscape_layers(root, parent_map)
    if inkscape_layers:
        return inkscape_layers

    root_group_layers = _extract_root_group_layers(root, parent_map)
    if root_group_layers:
        return root_group_layers

    return [_synthetic_document_layer(document, parent_map)]
