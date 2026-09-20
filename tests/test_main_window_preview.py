"""Main window preview integration."""

from __future__ import annotations

from pathlib import Path

import pytest

from plotpilot.services.svg_loader import SvgLoadError, load_svg_from_path
from plotpilot.ui.main_window import MainWindow

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_first_layer_selected_after_open(main_window: MainWindow) -> None:
    document = load_svg_from_path(FIXTURES / "five_inkscape_layers.svg")
    main_window.set_document(document)
    assert main_window._layers_list.currentRow() == 0
    assert main_window.current_preview_svg is not None
    assert "Orange" in main_window.layers[0].name or main_window.layers[0].name == "Orange"


def test_changing_selection_updates_preview(main_window: MainWindow) -> None:
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    main_window.set_document(document)
    first_preview = main_window.current_preview_svg
    assert first_preview is not None
    assert "only-in-layer-a" in first_preview

    main_window._layers_list.setCurrentRow(1)
    second_preview = main_window.current_preview_svg
    assert second_preview is not None
    assert second_preview != first_preview
    assert "only-in-layer-b" in second_preview


def test_opening_second_document_resets_to_first_layer(main_window: MainWindow) -> None:
    main_window.set_document(load_svg_from_path(FIXTURES / "preview_two_layers.svg"))
    main_window._layers_list.setCurrentRow(1)

    main_window.set_document(load_svg_from_path(FIXTURES / "no_groups.svg"))
    assert main_window._layers_list.currentRow() == 0
    assert main_window.current_preview_svg == main_window.document.raw_text


def test_failed_open_preserves_preview_state(main_window: MainWindow) -> None:
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    main_window.set_document(document)
    main_window._layers_list.setCurrentRow(1)
    preview_before = main_window.current_preview_svg
    layers_before = main_window.layers

    with pytest.raises(SvgLoadError):
        load_svg_from_path(FIXTURES / "malformed.xml")

    assert main_window.layers == layers_before
    assert main_window.current_preview_svg == preview_before
    assert main_window._layers_list.currentRow() == 1
