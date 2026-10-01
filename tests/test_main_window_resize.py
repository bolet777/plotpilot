"""Main window resize and page scrolling."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QGuiApplication, QWheelEvent
from PySide6.QtWidgets import QApplication, QScrollArea, QSlider

from plotpilot.services.svg_loader import load_svg_from_path
from plotpilot.ui.main_window import MainWindow, window_size_bounds

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _scroll(window: MainWindow) -> QScrollArea:
    scroll = window.findChild(QScrollArea, "mainContentScroll")
    assert isinstance(scroll, QScrollArea)
    return scroll


def _show(qapp, window: MainWindow) -> QScrollArea:
    window.show()
    qapp.processEvents()
    return _scroll(window)


def test_window_size_bounds_keep_preferred_size_on_a_large_screen() -> None:
    minimum, initial = window_size_bounds(1920, 1200)
    assert minimum == (480, 320)
    assert initial == (900, 560)


def test_window_size_bounds_clamp_to_usable_screen() -> None:
    minimum, initial = window_size_bounds(700, 500)
    assert minimum == (480, 320)
    assert initial == (700, 500)


def test_window_size_bounds_shrink_minimum_when_screen_is_smaller() -> None:
    minimum, initial = window_size_bounds(400, 280)
    assert minimum == (400, 280)
    assert initial == (400, 280)


def test_launch_size_fits_available_geometry(qapp, main_window: MainWindow) -> None:
    _show(qapp, main_window)
    screen = main_window.screen() or QGuiApplication.primaryScreen()
    assert screen is not None
    available = screen.availableGeometry()
    assert main_window.width() <= available.width()
    assert main_window.height() <= available.height()
    assert main_window.width() <= 900
    assert main_window.height() <= 560


def test_main_window_is_resizable_and_not_fixed(qapp, main_window: MainWindow) -> None:
    scroll = _show(qapp, main_window)
    assert main_window.minimumSize() != main_window.maximumSize()
    assert main_window.maximumWidth() > 10_000
    assert main_window.maximumHeight() > 10_000
    assert main_window.minimumWidth() <= 480
    assert main_window.minimumHeight() <= 320

    main_window.resize(520, 400)
    qapp.processEvents()
    assert main_window.width() < 700
    assert main_window.height() < 500
    assert scroll.widgetResizable() is True


def test_scroll_area_uses_as_needed_policies(main_window: MainWindow) -> None:
    scroll = _scroll(main_window)
    content = scroll.widget()
    assert content is not None
    assert content.objectName() == "mainContent"
    assert scroll.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    assert scroll.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    assert scroll.widgetResizable() is True


def test_shrinking_enables_both_scrollbars(qapp, main_window: MainWindow) -> None:
    scroll = _show(qapp, main_window)
    main_window.resize(main_window.minimumWidth(), main_window.minimumHeight())
    qapp.processEvents()
    assert scroll.verticalScrollBar().maximum() > 0
    assert scroll.horizontalScrollBar().maximum() > 0


def test_large_window_hides_scrollbars_and_expands_preview(qapp, main_window: MainWindow) -> None:
    scroll = _show(qapp, main_window)
    content = scroll.widget()
    assert content is not None
    hint = content.minimumSizeHint()
    main_window.resize(hint.width() + 240, hint.height() + 240)
    qapp.processEvents()
    assert scroll.verticalScrollBar().maximum() == 0
    assert scroll.horizontalScrollBar().maximum() == 0
    assert main_window._preview_stack.height() > main_window._preview.minimumHeight()


def test_preview_minimum_does_not_force_oversized_window(main_window: MainWindow) -> None:
    assert main_window._preview.minimumWidth() <= 200
    assert main_window._preview.minimumHeight() <= 200
    assert main_window.minimumWidth() < 800
    assert main_window.minimumHeight() < 600


def test_bottom_and_transform_controls_stay_in_scrollable_content(
    main_window: MainWindow,
) -> None:
    content = _scroll(main_window).widget()
    assert content is not None
    for widget in (
        main_window._plot_settings,
        main_window._estimate_button,
        main_window._plot_layer_button,
        main_window._plot_checked_button,
        main_window._plot_stop_button,
        main_window._home_button,
        main_window._motors_off_button,
        main_window._pen_up_button,
        main_window._plot_progress_bar,
        main_window._multi_continue_button,
        main_window._artwork_controls,
        main_window._layers_list,
        main_window._preview_stack,
    ):
        assert content.isAncestorOf(widget)
    assert main_window._artwork_controls.findChildren(QSlider)
    assert main_window._layers_list.minimumWidth() >= 160


def test_narrow_window_does_not_clip_transform_controls(qapp, main_window: MainWindow) -> None:
    scroll = _show(qapp, main_window)
    content = scroll.widget()
    assert content is not None
    main_window.resize(main_window.minimumWidth(), 640)
    qapp.processEvents()
    reset = main_window._artwork_controls._reset_all
    assert reset.width() >= reset.sizeHint().width() - 4
    assert reset.geometry().right() <= content.width()
    assert scroll.horizontalScrollBar().maximum() > 0


def test_startup_scroll_stays_at_origin_when_opening_svg(qapp, main_window: MainWindow) -> None:
    scroll = _show(qapp, main_window)
    assert scroll.verticalScrollBar().value() == 0
    assert scroll.horizontalScrollBar().value() == 0
    main_window.set_document(load_svg_from_path(FIXTURES / "simple.svg"))
    qapp.processEvents()
    assert scroll.verticalScrollBar().value() == 0
    assert scroll.horizontalScrollBar().value() == 0


def test_resize_and_settings_keep_scroll_position(qapp, main_window: MainWindow) -> None:
    scroll = _show(qapp, main_window)
    main_window.resize(main_window.minimumWidth(), main_window.minimumHeight())
    qapp.processEvents()
    maximum = scroll.verticalScrollBar().maximum()
    assert maximum > 20
    scroll.verticalScrollBar().setValue(20)
    main_window.resize(main_window.minimumWidth(), main_window.minimumHeight() + 40)
    qapp.processEvents()
    assert scroll.verticalScrollBar().value() == 20

    slider = main_window._plot_settings._pen_down_slider
    next_value = slider.value() + 1 if slider.value() < slider.maximum() else slider.value() - 1
    slider.setValue(next_value)
    qapp.processEvents()
    assert scroll.verticalScrollBar().value() == 20


def test_wheel_on_idle_layer_list_scrolls_the_page(qapp, main_window: MainWindow) -> None:
    scroll = _show(qapp, main_window)
    main_window.resize(main_window.minimumWidth(), main_window.minimumHeight())
    qapp.processEvents()
    assert main_window._layers_list.verticalScrollBar().maximum() == 0
    assert scroll.verticalScrollBar().maximum() > 0
    local = main_window._layers_list.rect().center()
    event = QWheelEvent(
        local,
        main_window._layers_list.mapToGlobal(local),
        QPoint(0, 0),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(main_window._layers_list, event)
    qapp.processEvents()
    assert scroll.verticalScrollBar().value() > 0
