"""Plot SVG preparation for layers."""

from __future__ import annotations

from pathlib import Path

from plotpilot.services.layer_service import layers_for_document
from plotpilot.services.plot_service import plot_svg_for_layer, validate_layer_plot_svg
from plotpilot.services.svg_loader import load_svg_from_path

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_layer_plot_svg_contains_only_selected_layer() -> None:
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    layers = layers_for_document(document)
    svg_a = plot_svg_for_layer(document, layers[0])
    assert "only-in-layer-a" in svg_a
    assert "only-in-layer-b" not in svg_a


def test_synthetic_layer_uses_full_document() -> None:
    document = load_svg_from_path(FIXTURES / "no_groups.svg")
    layers = layers_for_document(document)
    assert plot_svg_for_layer(document, layers[0]) == document.raw_text


def test_original_document_unchanged_after_plot_svg_build() -> None:
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    before = document.raw_text
    layers = layers_for_document(document)
    _ = plot_svg_for_layer(document, layers[1])
    assert document.raw_text == before


def test_validate_accepts_fixture_sizes() -> None:
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    layers = layers_for_document(document)
    svg = plot_svg_for_layer(document, layers[0])
    validate_layer_plot_svg(svg)
