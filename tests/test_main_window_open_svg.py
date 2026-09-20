"""Open SVG discoverability in the main window."""

from __future__ import annotations

from pathlib import Path

from plotpilot.services.svg_loader import load_svg_from_path
from plotpilot.ui.main_window import MainWindow

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_empty_state_when_no_document(main_window: MainWindow) -> None:
    assert main_window.document is None
    assert main_window._preview_stack.currentWidget() is main_window._preview_empty_page
    assert main_window._open_svg_empty_button.isHidden() is False
    assert main_window._open_svg_persistent_button.isHidden()


def test_persistent_open_button_after_document_loaded(main_window: MainWindow) -> None:
    main_window.set_document(load_svg_from_path(FIXTURES / "simple.svg"))
    assert main_window._preview_stack.currentWidget() is main_window._preview
    assert main_window._open_svg_persistent_button.isHidden() is False
    assert main_window._open_svg_persistent_button.isEnabled()


def test_open_buttons_trigger_open_svg_action(main_window: MainWindow) -> None:
    triggered: list[int] = []
    main_window._open_svg_action.triggered.connect(lambda: triggered.append(1))

    main_window._open_svg_empty_button.click()
    assert triggered == [1]

    main_window.set_document(load_svg_from_path(FIXTURES / "simple.svg"))
    triggered.clear()
    main_window._open_svg_persistent_button.click()
    assert triggered == [1]


def test_menu_open_action_same_as_shortcut_target(main_window: MainWindow) -> None:
    assert main_window._open_svg_action.text() == "Open SVG…"
    assert main_window._open_svg_action.shortcut().toString() != ""


def test_open_svg_action_loads_injected_path(main_window: MainWindow) -> None:
    fixture_path = str(FIXTURES / "five_inkscape_layers.svg")
    main_window._svg_file_chooser = lambda: fixture_path
    main_window._open_svg_action.trigger()
    assert main_window.document is not None
    assert len(main_window.layers) >= 1


def test_open_svg_cancelled_leaves_document_unchanged(main_window: MainWindow) -> None:
    main_window.set_document(load_svg_from_path(FIXTURES / "simple.svg"))
    before = main_window.document
    main_window._svg_file_chooser = lambda: None
    main_window._open_svg_action.trigger()
    assert main_window.document is before
