"""Unit tests for layer preview SVG generation."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from plotpilot.models.svg_document import SvgDocument
from plotpilot.services.layer_service import layers_for_document
from plotpilot.services.preview_service import preview_svg_for_layer
from plotpilot.services.svg_loader import load_svg_from_path
from plotpilot.svg.parse import parse_svg_text
from plotpilot.svg.preview import build_layer_preview_svg

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load(name: str):
    return load_svg_from_path(FIXTURES / name)


def test_preview_for_simple_layer() -> None:
    document = _load("preview_two_layers.svg")
    layers = layers_for_document(document)
    preview = build_layer_preview_svg(document, layers[0])
    assert preview.startswith("<?xml")
    assert "only-in-layer-a" in preview


def test_only_selected_layer_content() -> None:
    document = _load("preview_two_layers.svg")
    layers = layers_for_document(document)
    preview_a = build_layer_preview_svg(document, layers[0])
    assert "only-in-layer-a" in preview_a
    assert "only-in-layer-b" not in preview_a

    preview_b = build_layer_preview_svg(document, layers[1])
    assert "only-in-layer-b" in preview_b
    assert "only-in-layer-a" not in preview_b


def test_original_document_tree_unchanged() -> None:
    document = _load("preview_two_layers.svg")
    before = ET.tostring(document.root, encoding="unicode")
    layers = layers_for_document(document)
    _ = build_layer_preview_svg(document, layers[0])
    _ = build_layer_preview_svg(document, layers[1])
    after = ET.tostring(document.root, encoding="unicode")
    assert before == after


def test_viewbox_preserved() -> None:
    document = _load("preview_two_layers.svg")
    layer = layers_for_document(document)[0]
    preview = build_layer_preview_svg(document, layer)
    root = ET.fromstring(preview)
    assert root.get("viewBox") == "0 0 100 100"


def test_width_height_preserved_when_present() -> None:
    document = _load("preview_two_layers.svg")
    layer = layers_for_document(document)[0]
    preview = build_layer_preview_svg(document, layer)
    root = ET.fromstring(preview)
    assert root.get("width") == "100"
    assert root.get("height") == "100"


def test_root_style_retained_for_isolated_layer() -> None:
    text = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">
  <style type="text/css">.st0{fill:none;stroke:#000000;}</style>
  <g id="layer-a"><rect class="st0" x="1" y="2" width="3" height="4"/></g>
  <g id="layer-b"><rect class="st0" x="10" y="10" width="1" height="1"/></g>
</svg>"""
    document = SvgDocument(
        path=FIXTURES / "inline.svg",
        name="inline.svg",
        raw_text=text,
        root=parse_svg_text(text),
    )
    layers = layers_for_document(document)
    preview = build_layer_preview_svg(document, layers[0])
    assert ".st0" in preview
    assert "layer-b" not in preview
    assert 'class="st0"' in preview


def test_defs_retained_for_gradient_layer() -> None:
    document = _load("preview_with_defs.svg")
    layers = layers_for_document(document)
    grad_layer = layers[0]
    preview = build_layer_preview_svg(document, grad_layer)
    assert "grad1" in preview
    assert "url(#grad1)" in preview
    assert "#00ff00" not in preview


def test_nested_layer_keeps_ancestor_transform_and_excludes_siblings() -> None:
    text = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
     width="100" height="100" viewBox="0 0 100 100">
  <g inkscape:groupmode="layer" inkscape:label="Parent" transform="translate(5,6)" stroke="black">
    <g inkscape:groupmode="layer" inkscape:label="Child">
      <rect id="keep-me" x="0" y="0" width="1" height="1"/>
    </g>
    <rect id="sibling" x="20" y="20" width="1" height="1"/>
  </g>
</svg>"""
    document = SvgDocument(
        path=FIXTURES / "inline.svg",
        name="inline.svg",
        raw_text=text,
        root=parse_svg_text(text),
    )
    child = next(layer for layer in layers_for_document(document) if layer.name == "Child")
    preview = build_layer_preview_svg(document, child)
    assert 'transform="translate(5,6)"' in preview
    assert 'stroke="black"' in preview
    assert "keep-me" in preview
    assert "sibling" not in preview


def test_transform_preserved_on_layer() -> None:
    document = _load("preview_layer_transform.svg")
    layer = layers_for_document(document)[0]
    preview = build_layer_preview_svg(document, layer)
    assert 'transform="translate(10, 10)"' in preview
    assert "#123456" in preview


def test_synthetic_layer_uses_full_document() -> None:
    document = _load("no_groups.svg")
    layers = layers_for_document(document)
    assert len(layers) == 1
    preview = preview_svg_for_layer(document, layers[0])
    assert preview == document.raw_text


def test_root_group_preview_isolates_selected_group() -> None:
    document = _load("three_root_groups.svg")
    layers = layers_for_document(document)
    preview = build_layer_preview_svg(document, layers[0])
    assert "#ff8800" in preview
    assert "#00cccc" not in preview
    assert "#ffff00" not in preview
    assert "g1" in preview


def test_styles_stroke_fill_intact() -> None:
    document = _load("preview_layer_transform.svg")
    layer = layers_for_document(document)[0]
    preview = build_layer_preview_svg(document, layer)
    assert 'stroke="#123456"' in preview
    assert 'stroke-width="2"' in preview
