"""Main window layer list behavior (Qt)."""

from __future__ import annotations

from pathlib import Path

import pytest

from plotpilot.services.svg_loader import SvgLoadError, load_svg_from_path
from plotpilot.ui.main_window import MainWindow

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_opening_second_svg_replaces_layer_list(main_window: MainWindow) -> None:
    first = load_svg_from_path(FIXTURES / "five_inkscape_layers.svg")
    second = load_svg_from_path(FIXTURES / "no_groups.svg")

    main_window.set_document(first)
    assert len(main_window.layers) == 5
    assert main_window._layers_list.count() == 5

    main_window.set_document(second)
    assert len(main_window.layers) == 1
    assert main_window._layers_list.count() == 1
    assert main_window.layers[0].name == "no_groups.svg"


def test_failed_load_preserves_document_and_layers(main_window: MainWindow) -> None:
    document = load_svg_from_path(FIXTURES / "five_inkscape_layers.svg")
    main_window.set_document(document)

    layers_before = main_window.layers
    document_before = main_window.document
    list_count_before = main_window._layers_list.count()

    with pytest.raises(SvgLoadError):
        load_svg_from_path(FIXTURES / "malformed.xml")

    assert main_window.document is document_before
    assert main_window.layers == layers_before
    assert main_window._layers_list.count() == list_count_before
