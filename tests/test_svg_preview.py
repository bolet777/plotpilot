"""Unit tests for layer preview SVG generation."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from plotpilot.services.layer_service import layers_for_document
from plotpilot.services.preview_service import preview_svg_for_layer
from plotpilot.services.svg_loader import load_svg_from_path
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


def test_defs_retained_for_gradient_layer() -> None:
    document = _load("preview_with_defs.svg")
    layers = layers_for_document(document)
    grad_layer = layers[0]
    preview = build_layer_preview_svg(document, grad_layer)
    assert "grad1" in preview
    assert "url(#grad1)" in preview
    assert "#00ff00" not in preview


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


def test_styles_stroke_fill_intact() -> None:
    document = _load("preview_layer_transform.svg")
    layer = layers_for_document(document)[0]
    preview = build_layer_preview_svg(document, layer)
    assert 'stroke="#123456"' in preview
    assert 'stroke-width="2"' in preview
