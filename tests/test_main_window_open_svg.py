"""Open SVG discoverability in the main window."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from plotpilot.services.svg_loader import load_svg_from_path
from plotpilot.ui.main_window import MainWindow

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def qapp():
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    yield application


def test_empty_state_when_no_document(qapp) -> None:
    window = MainWindow()
    assert window.document is None
    assert window._preview_stack.currentWidget() is window._preview_empty_page
    assert window._open_svg_empty_button.isHidden() is False
    assert window._open_svg_persistent_button.isHidden()


def test_persistent_open_button_after_document_loaded(qapp) -> None:
    window = MainWindow()
    window.set_document(load_svg_from_path(FIXTURES / "valid_basic.svg"))
    assert window._preview_stack.currentWidget() is window._preview
    assert window._open_svg_persistent_button.isHidden() is False
    assert window._open_svg_persistent_button.isEnabled()


def test_open_buttons_trigger_open_svg_action(qapp) -> None:
    window = MainWindow()
    triggered: list[int] = []
    window._open_svg_action.triggered.connect(lambda: triggered.append(1))

    window._open_svg_empty_button.click()
    assert triggered == [1]

    window.set_document(load_svg_from_path(FIXTURES / "valid_basic.svg"))
    triggered.clear()
    window._open_svg_persistent_button.click()
    assert triggered == [1]


def test_menu_open_action_same_as_shortcut_target(qapp) -> None:
    window = MainWindow()
    assert window._open_svg_action.text() == "Open SVG…"
    assert window._open_svg_action.shortcut().toString() != ""
