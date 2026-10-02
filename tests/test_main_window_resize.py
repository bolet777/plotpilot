"""Main window resize behaviour for the V2 layout (splitter + scrollable properties panel).

The intent is unchanged from V1: the window stays resizable, the preview gets
extra space, and no control becomes unreachable on small windows. The
mechanism changed: instead of one page-level scroll area, the right-hand
properties panel scrolls and the bottom action bar wraps its groups.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QScrollArea, QSlider, QSplitter, QWidget

from plotpilot.services.svg_loader import load_svg_from_path
from plotpilot.ui.main_window import MainWindow, splitter_sizes_for_width, window_size_bounds

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _show(qapp, window: MainWindow) -> None:
    window.show()
    qapp.processEvents()
    qapp.processEvents()


def _transform_scroll(window: MainWindow) -> QScrollArea:
    return window._properties_panel.transform_scroll


def _rect_in_window(window: MainWindow, widget: QWidget) -> QRect:
    top_left = widget.mapTo(window, widget.rect().topLeft())
    return QRect(top_left, widget.size())


def test_window_size_bounds_keep_preferred_size_on_a_large_screen() -> None:
    minimum, initial = window_size_bounds(1920, 1200)
    assert minimum == (760, 520)
    assert initial == (1240, 800)


def test_window_size_bounds_clamp_to_usable_screen() -> None:
    minimum, initial = window_size_bounds(1000, 700)
    assert minimum == (760, 520)
    assert initial == (1000, 700)


def test_window_size_bounds_shrink_minimum_when_screen_is_smaller() -> None:
    minimum, initial = window_size_bounds(640, 400)
    assert minimum == (640, 400)
    assert initial == (640, 400)


def test_splitter_sizes_give_preview_the_remainder() -> None:
    layers, preview, properties = splitter_sizes_for_width(1240)
    assert layers == 220
    assert properties == 356
    assert preview == 1240 - 220 - 356


def test_splitter_sizes_shrink_side_panels_on_narrow_windows() -> None:
    layers, preview, properties = splitter_sizes_for_width(760)
    assert layers + preview + properties == 760
    assert preview >= int(760 * 0.38)
    assert layers < 220
    assert properties < 356
    hidden = splitter_sizes_for_width(760, layers_visible=False)
    assert hidden[0] == 0
    assert hidden[1] > preview


def test_launch_size_fits_available_geometry(qapp, main_window: MainWindow) -> None:
    _show(qapp, main_window)
    screen = main_window.screen() or QGuiApplication.primaryScreen()
    assert screen is not None
    available = screen.availableGeometry()
    assert main_window.width() <= available.width()
    assert main_window.height() <= available.height()
    assert main_window.width() <= 1240
    assert main_window.height() <= 800


def test_main_window_is_resizable_and_not_fixed(qapp, main_window: MainWindow) -> None:
    _show(qapp, main_window)
    assert main_window.minimumSize() != main_window.maximumSize()
    assert main_window.maximumWidth() > 10_000
    assert main_window.maximumHeight() > 10_000
    assert main_window.minimumWidth() <= 760
    assert main_window.minimumHeight() <= 520

    main_window.resize(800, 560)
    qapp.processEvents()
    assert main_window.width() < 900
    assert main_window.height() < 700


def test_layout_uses_splitter_with_preview_in_the_middle(main_window: MainWindow) -> None:
    splitter = main_window.findChild(QSplitter, "mainSplitter")
    assert isinstance(splitter, QSplitter)
    assert splitter.count() == 3
    assert splitter.widget(0) is main_window._layers_panel
    assert splitter.widget(1) is main_window._workspace
    assert splitter.widget(2) is main_window._properties_panel
    assert main_window._workspace.isAncestorOf(main_window._preview_stack)


def test_properties_scroll_areas_use_as_needed_policies(main_window: MainWindow) -> None:
    for scroll in main_window._properties_panel.scroll_areas():
        assert scroll.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
        assert scroll.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
        assert scroll.widgetResizable() is True


def test_small_window_makes_transform_panel_scroll_instead_of_clipping(
    qapp, main_window: MainWindow
) -> None:
    _show(qapp, main_window)
    main_window.resize(main_window.minimumWidth(), main_window.minimumHeight())
    qapp.processEvents()
    scroll = _transform_scroll(main_window)
    assert scroll.verticalScrollBar().maximum() > 0
    # Every transform control is still inside the scrollable content.
    content = scroll.widget()
    assert content is not None
    for widget in (
        main_window._artwork_controls,
        main_window._artwork_controls._reset_all,
        main_window._artwork_controls._margin_horizontal,
        main_window._fallback_work_area_row,
    ):
        assert content.isAncestorOf(widget)
    scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
    qapp.processEvents()
    reset = main_window._artwork_controls._reset_all
    viewport = _rect_in_window(main_window, scroll.viewport())
    assert main_window.rect().contains(viewport)
    rect = _rect_in_window(main_window, reset)
    assert rect.intersects(viewport)
    assert viewport.top() <= rect.top() and rect.bottom() <= viewport.bottom()
    # Wider-than-panel content is reachable with the horizontal scrollbar, never clipped.
    scroll.horizontalScrollBar().setValue(scroll.horizontalScrollBar().maximum())
    qapp.processEvents()
    assert _rect_in_window(main_window, reset).right() <= viewport.right()


def test_large_window_expands_preview_and_hides_panel_scrollbars(
    qapp, main_window: MainWindow
) -> None:
    _show(qapp, main_window)
    main_window.resize(1000, 700)
    qapp.processEvents()
    narrow_preview_width = main_window._workspace.width()
    main_window.resize(1500, 1000)
    qapp.processEvents()
    assert main_window._workspace.width() > narrow_preview_width
    assert main_window._preview_stack.height() > main_window._preview.minimumHeight()
    assert _transform_scroll(main_window).verticalScrollBar().maximum() == 0


def test_preview_minimum_does_not_force_oversized_window(main_window: MainWindow) -> None:
    assert main_window._preview.minimumWidth() <= 200
    assert main_window._preview.minimumHeight() <= 200
    assert main_window.minimumWidth() <= 760
    assert main_window.minimumHeight() <= 520


def test_controls_live_in_their_regions(main_window: MainWindow) -> None:
    bar = main_window._action_bar
    for widget in (
        main_window._estimate_button,
        main_window._plot_layer_button,
        main_window._plot_checked_button,
        main_window._plot_stop_button,
        main_window._home_button,
        main_window._motors_off_button,
        main_window._pen_up_button,
        main_window._pen_down_button,
        main_window._plotter_refresh_button,
        main_window._plot_progress_bar,
        main_window._multi_continue_button,
        main_window._plotter_status_label,
    ):
        assert bar.isAncestorOf(widget)
    panel = main_window._properties_panel
    for widget in (
        main_window._artwork_controls,
        main_window._plot_settings,
        main_window._device_panel,
        main_window._bounds_status_label,
    ):
        assert panel.isAncestorOf(widget)
    assert main_window._layers_panel.isAncestorOf(main_window._layers_list)
    assert main_window._artwork_controls.findChildren(QSlider)
    assert main_window._layers_panel.minimumWidth() >= 160


def test_narrow_window_wraps_action_bar_instead_of_clipping(qapp, main_window: MainWindow) -> None:
    _show(qapp, main_window)
    main_window.resize(1400, 800)
    qapp.processEvents()
    wide_height = main_window._action_bar.height()
    main_window.resize(main_window.minimumWidth(), 640)
    qapp.processEvents()
    qapp.processEvents()
    assert main_window._action_bar.height() > wide_height
    for button in (
        main_window._estimate_button,
        main_window._plot_stop_button,
        main_window._plot_checked_button,
        main_window._pen_down_button,
    ):
        rect = _rect_in_window(main_window, button)
        assert main_window.rect().contains(rect), button.text()
        assert button.width() >= button.sizeHint().width() - 4


def test_startup_scroll_stays_at_origin_when_opening_svg(qapp, main_window: MainWindow) -> None:
    _show(qapp, main_window)
    scroll = _transform_scroll(main_window)
    assert scroll.verticalScrollBar().value() == 0
    assert scroll.horizontalScrollBar().value() == 0
    main_window.set_document(load_svg_from_path(FIXTURES / "simple.svg"))
    qapp.processEvents()
    assert scroll.verticalScrollBar().value() == 0
    assert scroll.horizontalScrollBar().value() == 0


def test_resize_and_settings_keep_scroll_position(qapp, main_window: MainWindow) -> None:
    _show(qapp, main_window)
    main_window.resize(main_window.minimumWidth(), main_window.minimumHeight())
    qapp.processEvents()
    scroll = _transform_scroll(main_window)
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


def test_layers_sidebar_can_be_hidden_to_give_room_to_the_preview(
    qapp, main_window: MainWindow
) -> None:
    _show(qapp, main_window)
    main_window.resize(1000, 700)
    qapp.processEvents()
    before = main_window._workspace.width()
    main_window._top_bar.layers_button.setChecked(False)
    qapp.processEvents()
    assert main_window._layers_panel.isHidden()
    assert main_window._workspace.width() > before
    main_window._top_bar.layers_button.setChecked(True)
    qapp.processEvents()
    assert not main_window._layers_panel.isHidden()
