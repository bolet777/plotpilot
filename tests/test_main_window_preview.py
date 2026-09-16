"""Main window preview integration."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from plotpilot.services.svg_loader import SvgLoadError, load_svg_from_path
from plotpilot.ui.main_window import MainWindow

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def qapp():
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    yield application


def test_first_layer_selected_after_open(qapp) -> None:
    window = MainWindow()
    document = load_svg_from_path(FIXTURES / "five_inkscape_layers.svg")
    window.set_document(document)
    assert window._layers_list.currentRow() == 0
    assert window.current_preview_svg is not None
    assert "Orange" in window.layers[0].name or window.layers[0].name == "Orange"


def test_changing_selection_updates_preview(qapp) -> None:
    window = MainWindow()
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    window.set_document(document)
    first_preview = window.current_preview_svg
    assert first_preview is not None
    assert "only-in-layer-a" in first_preview

    window._layers_list.setCurrentRow(1)
    second_preview = window.current_preview_svg
    assert second_preview is not None
    assert second_preview != first_preview
    assert "only-in-layer-b" in second_preview


def test_opening_second_document_resets_to_first_layer(qapp) -> None:
    window = MainWindow()
    window.set_document(load_svg_from_path(FIXTURES / "preview_two_layers.svg"))
    window._layers_list.setCurrentRow(1)

    window.set_document(load_svg_from_path(FIXTURES / "no_groups.svg"))
    assert window._layers_list.currentRow() == 0
    assert window.current_preview_svg == window.document.raw_text


def test_failed_open_preserves_preview_state(qapp) -> None:
    window = MainWindow()
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    window.set_document(document)
    window._layers_list.setCurrentRow(1)
    preview_before = window.current_preview_svg
    layers_before = window.layers

    with pytest.raises(SvgLoadError):
        load_svg_from_path(FIXTURES / "malformed.xml")

    assert window.layers == layers_before
    assert window.current_preview_svg == preview_before
    assert window._layers_list.currentRow() == 1
