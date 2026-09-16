"""Unit tests for SVG layer extraction."""

from __future__ import annotations

from pathlib import Path

from plotpilot.models.svg_document import SvgDocument
from plotpilot.services.svg_loader import load_svg_from_path
from plotpilot.svg.layers import extract_layers, is_inkscape_layer
from plotpilot.svg.parse import parse_svg_text

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _document_from_text(text: str, name: str = "inline.svg") -> SvgDocument:
    root = parse_svg_text(text)
    return SvgDocument(path=Path(name), name=name, raw_text=text, root=root)


def _document_from_fixture(filename: str) -> SvgDocument:
    return load_svg_from_path(FIXTURES / filename)


def test_five_inkscape_layers_count_and_order() -> None:
    document = _document_from_fixture("five_inkscape_layers.svg")
    layers = extract_layers(document)
    assert len(layers) == 5
    assert [layer.name for layer in layers] == [
        "Orange",
        "Cyan",
        "Yellow",
        "Purple",
        "Pink",
    ]
    assert [layer.order for layer in layers] == [0, 1, 2, 3, 4]


def test_inkscape_label_preferred_over_id() -> None:
    text = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape">
  <g inkscape:groupmode="layer" inkscape:label="Display Name" id="layer-id"/>
</svg>"""
    layers = extract_layers(_document_from_text(text))
    assert layers[0].name == "Display Name"
    assert layers[0].layer_id == "layer-id"


def test_fallback_to_id_when_no_label() -> None:
    text = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape">
  <g inkscape:groupmode="layer" id="my-layer-id"/>
</svg>"""
    layers = extract_layers(_document_from_text(text))
    assert layers[0].name == "my-layer-id"
    assert layers[0].layer_id == "my-layer-id"


def test_generated_layer_name_when_unnamed() -> None:
    text = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape">
  <g inkscape:groupmode="layer"/>
</svg>"""
    layers = extract_layers(_document_from_text(text))
    assert layers[0].name == "Layer 1"
    assert layers[0].layer_id == "layer-0"


def test_direct_stroke_color() -> None:
    text = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape">
  <g inkscape:groupmode="layer" inkscape:label="L">
    <path stroke="#aabbcc" fill="none" d="M0 0"/>
  </g>
</svg>"""
    layers = extract_layers(_document_from_text(text))
    assert layers[0].representative_color == "#aabbcc"


def test_direct_fill_color_when_no_stroke() -> None:
    text = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape">
  <g inkscape:groupmode="layer" inkscape:label="L">
    <rect fill="#010203" x="0" y="0" width="1" height="1"/>
  </g>
</svg>"""
    layers = extract_layers(_document_from_text(text))
    assert layers[0].representative_color == "#010203"


def test_inline_style_stroke_and_fill() -> None:
    stroke_text = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape">
  <g inkscape:groupmode="layer" inkscape:label="L">
    <path style="stroke: #112233; fill: none" d="M0 0"/>
  </g>
</svg>"""
    fill_text = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape">
  <g inkscape:groupmode="layer" inkscape:label="L">
    <path style="fill: #445566" d="M0 0"/>
  </g>
</svg>"""
    assert extract_layers(_document_from_text(stroke_text))[0].representative_color == "#112233"
    assert extract_layers(_document_from_text(fill_text))[0].representative_color == "#445566"


def test_color_none_is_ignored() -> None:
    text = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape">
  <g inkscape:groupmode="layer" inkscape:label="L">
    <path stroke="none" fill="#abcdef" d="M0 0"/>
  </g>
</svg>"""
    layers = extract_layers(_document_from_text(text))
    assert layers[0].representative_color == "#abcdef"


def test_layer_with_no_detectable_color() -> None:
    text = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape">
  <g inkscape:groupmode="layer" inkscape:label="L">
    <path stroke="none" fill="none" d="M0 0"/>
  </g>
</svg>"""
    layers = extract_layers(_document_from_text(text))
    assert layers[0].representative_color is None


def test_ordinary_groups_without_inkscape_layers() -> None:
    document = _document_from_fixture("ordinary_groups.svg")
    layers = extract_layers(document)
    assert len(layers) == 1
    assert layers[0].name == "ordinary_groups.svg"
    assert layers[0].element.tag.endswith("svg") or "svg" in layers[0].element.tag


def test_no_groups_synthetic_layer() -> None:
    document = _document_from_fixture("no_groups.svg")
    layers = extract_layers(document)
    assert len(layers) == 1
    assert layers[0].drawable_count == 1


def test_nested_groups_inside_layer_not_extra_layers() -> None:
    document = _document_from_fixture("nested_in_layer.svg")
    layers = extract_layers(document)
    assert len(layers) == 1
    assert layers[0].name == "Only Layer"
    assert layers[0].representative_color == "#123456"


def test_inkscape_layer_detection_uses_namespace_not_prefix() -> None:
    text = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:ns1="http://www.inkscape.org/namespaces/inkscape">
  <g ns1:groupmode="layer" ns1:label="From prefixed NS"/>
</svg>"""
    root = parse_svg_text(text)
    layer_groups = [el for el in root.iter() if is_inkscape_layer(el)]
    assert len(layer_groups) == 1
    layers = extract_layers(_document_from_text(text))
    assert layers[0].name == "From prefixed NS"


def test_drawable_count_excludes_defs() -> None:
    text = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape">
  <defs><path id="p" d="M0 0"/></defs>
  <g inkscape:groupmode="layer" inkscape:label="L">
    <path d="M0 0"/>
    <rect x="0" y="0" width="1" height="1"/>
  </g>
</svg>"""
    layers = extract_layers(_document_from_text(text))
    assert layers[0].drawable_count == 2
