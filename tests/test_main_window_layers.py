"""Main window layer list behavior (Qt)."""

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


def test_opening_second_svg_replaces_layer_list(qapp) -> None:
    window = MainWindow()
    first = load_svg_from_path(FIXTURES / "five_inkscape_layers.svg")
    second = load_svg_from_path(FIXTURES / "no_groups.svg")

    window.set_document(first)
    assert len(window.layers) == 5
    assert window._layers_list.count() == 5

    window.set_document(second)
    assert len(window.layers) == 1
    assert window._layers_list.count() == 1
    assert window.layers[0].name == "no_groups.svg"


def test_failed_load_preserves_document_and_layers(qapp) -> None:
    window = MainWindow()
    document = load_svg_from_path(FIXTURES / "five_inkscape_layers.svg")
    window.set_document(document)

    layers_before = window.layers
    document_before = window.document
    list_count_before = window._layers_list.count()

    with pytest.raises(SvgLoadError):
        load_svg_from_path(FIXTURES / "malformed.xml")

    assert window.document is document_before
    assert window.layers == layers_before
    assert window._layers_list.count() == list_count_before
