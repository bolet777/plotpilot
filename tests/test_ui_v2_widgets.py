"""V2 presentation widgets: theme, layout helpers, preview view state, panel wiring."""

from __future__ import annotations

from pathlib import Path
from xml.etree.ElementTree import Element

import pytest
from PySide6.QtCore import QPointF, QRect, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QPushButton, QWidget

from plotpilot.models.artwork_transform import ArtworkTransform
from plotpilot.models.plotter_status import PlotterConnectionState, PlotterStatus
from plotpilot.models.svg_layer import LayerSource, SvgLayer
from plotpilot.plotter.fake import FakePlotterBackend
from plotpilot.services.preview_work_area import PreviewWorkArea
from plotpilot.services.svg_loader import load_svg_from_path
from plotpilot.ui.action_bar import ActionBar
from plotpilot.ui.layers_panel import LAYER_COUNT_ROLE, layer_secondary_text
from plotpilot.ui.main_window import MainWindow
from plotpilot.ui.preview_widget import (
    VIEW_ZOOM_MAX,
    VIEW_ZOOM_MIN,
    LayerPreviewWidget,
    clamp_view_zoom,
    ruler_step_mm,
)
from plotpilot.ui.properties_panel import TAB_DEVICE, TAB_PLOT_SETTINGS, TAB_TRANSFORM
from plotpilot.ui.theme import apply_theme, build_stylesheet, scaled_font
from plotpilot.ui.top_bar import connection_color, connection_label
from plotpilot.ui.widgets import ElidedLabel, FlowLayout

FIXTURES = Path(__file__).resolve().parent / "fixtures"

_PLOT_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" '
    'viewBox="0 0 100 100"><path d="M10 10 L90 90" stroke="#000" fill="none"/></svg>'
)


# ---------------------------------------------------------------- theme


def test_stylesheet_builds_and_applies(qapp) -> None:
    sheet = build_stylesheet()
    assert "#topBar" in sheet and "#actionBar" in sheet and 'QFrame[role="card"]' in sheet
    previous = qapp.styleSheet()
    try:
        apply_theme(qapp)
        assert qapp.styleSheet() == sheet
    finally:
        qapp.setStyleSheet(previous)


def test_scaled_font_handles_pixel_and_point_sizes() -> None:
    point = QFont()
    point.setPointSizeF(12.0)
    assert scaled_font(point, -2.0).pointSizeF() == pytest.approx(10.0)
    assert scaled_font(point, -20.0, minimum=7.0).pointSizeF() == pytest.approx(7.0)
    pixel = QFont()
    pixel.setPixelSize(12)
    assert pixel.pointSizeF() < 0
    assert scaled_font(pixel, -3.0).pixelSize() == 9
    assert scaled_font(pixel, -30.0, minimum=7.0).pixelSize() == 7


# -------------------------------------------------------------- helpers


def test_elided_label_keeps_full_text_and_single_line(qapp) -> None:
    label = ElidedLabel("first line\nsecond line that is quite long indeed")
    label.resize(80, 20)
    label.show()
    qapp.processEvents()
    assert label.text() == "first line\nsecond line that is quite long indeed"
    rendered = QLabel.text(label)
    assert "\n" not in rendered
    assert rendered.endswith("…")


def test_flow_layout_wraps_when_narrow(qapp) -> None:
    host = QWidget()
    flow = FlowLayout(host, h_spacing=4, v_spacing=4)
    for _ in range(4):
        button = QPushButton("Wide button label", host)
        flow.addWidget(button)
    one_row_width = flow.sizeHint().width()
    single = flow.heightForWidth(one_row_width + 10)
    wrapped = flow.heightForWidth(one_row_width // 2)
    assert wrapped > single
    assert flow.minimumSize().width() == max(
        flow.itemAt(i).minimumSize().width() for i in range(flow.count())
    )
    flow.setGeometry(QRect(0, 0, one_row_width // 2, wrapped))
    tops = {flow.itemAt(i).geometry().top() for i in range(flow.count())}
    assert len(tops) >= 2


def test_layer_secondary_text_reports_paths_and_hidden() -> None:
    layer = SvgLayer(
        layer_id="a",
        name="Ink",
        order=0,
        element=Element("g"),
        representative_color="#ff0000",
        drawable_count=1,
    )
    assert layer_secondary_text(layer) == "1 path"
    many = SvgLayer(
        layer_id="b",
        name="Ink",
        order=1,
        element=Element("g"),
        representative_color=None,
        drawable_count=2458,
        source=LayerSource.ROOT_GROUP,
        hidden=True,
    )
    assert layer_secondary_text(many).startswith("2")
    assert "paths" in layer_secondary_text(many)
    assert layer_secondary_text(many).endswith("hidden")


def test_connection_labels_and_colors() -> None:
    assert connection_label(PlotterConnectionState.CONNECTED) == "Connected"
    assert connection_label(PlotterConnectionState.DISCONNECTED) == "Not connected"
    assert connection_label(PlotterConnectionState.ERROR) == "Error"
    assert connection_color(PlotterConnectionState.CONNECTED) != connection_color(
        PlotterConnectionState.DISCONNECTED
    )


def test_action_bar_connection_state_text(qapp) -> None:
    bar = ActionBar()
    bar.set_connection_state(PlotterConnectionState.DISCONNECTED)
    assert "Not connected" in bar.plotter_status_label.text()
    assert bar.connect_button.text() == "Connect"
    bar.set_connection_state(PlotterConnectionState.CONNECTED)
    assert "Connected" in bar.plotter_status_label.text()
    assert bar.connect_button.text() == "Reconnect"
    assert bar.progress_row.isHidden()
    assert bar.pen_change_banner.isHidden()


# ----------------------------------------------------------- preview view


def test_zoom_helpers() -> None:
    assert clamp_view_zoom(0.0) == VIEW_ZOOM_MIN
    assert clamp_view_zoom(100.0) == VIEW_ZOOM_MAX
    assert clamp_view_zoom(float("nan")) == 1.0
    step, minor = ruler_step_mm(2.0)
    assert step * 2.0 >= 56.0
    assert minor >= 2
    assert ruler_step_mm(0.0) == (50.0, 5)


def _preview_with_layout(qapp) -> LayerPreviewWidget:
    widget = LayerPreviewWidget()
    widget.resize(600, 400)
    widget.show()
    qapp.processEvents()
    assert widget.set_preview_svg(_PLOT_SVG)
    widget.set_work_area_overlay(
        svg_width_mm=100.0,
        svg_height_mm=100.0,
        work_area=PreviewWorkArea(210.0, 297.0, "A4", True),
    )
    return widget


def test_view_zoom_scales_layout_without_touching_artwork_transform(qapp) -> None:
    widget = _preview_with_layout(qapp)
    base = widget.physical_layout
    assert base is not None
    widget.set_artwork_transform(ArtworkTransform(x_mm=3.0, y_mm=-2.0, scale=1.5))
    widget.zoom_in()
    zoomed = widget.physical_layout
    assert zoomed is not None
    assert zoomed.mm_to_px == pytest.approx(base.mm_to_px * widget.view_zoom)
    assert widget.view_zoom > 1.0
    assert widget.artwork_transform == ArtworkTransform(x_mm=3.0, y_mm=-2.0, scale=1.5)
    widget.pan_by(QPointF(25.0, -10.0))
    panned = widget.physical_layout
    assert panned is not None
    assert panned.workspace_x_px == pytest.approx(zoomed.workspace_x_px + 25.0)
    assert panned.workspace_y_px == pytest.approx(zoomed.workspace_y_px - 10.0)
    widget.fit_view()
    restored = widget.physical_layout
    assert restored is not None
    assert restored.mm_to_px == pytest.approx(base.mm_to_px)
    assert restored.workspace_x_px == pytest.approx(base.workspace_x_px)
    assert widget.view_zoom == 1.0


def test_zoom_keeps_anchor_point_fixed(qapp) -> None:
    widget = _preview_with_layout(qapp)
    anchor = QPointF(300.0, 200.0)
    before = widget.widget_to_mm(anchor)
    assert before is not None
    widget.set_view_zoom(2.0, anchor_px=anchor)
    after = widget.widget_to_mm(anchor)
    assert after is not None
    assert after[0] == pytest.approx(before[0], abs=0.05)
    assert after[1] == pytest.approx(before[1], abs=0.05)


def test_widget_to_mm_matches_layout(qapp) -> None:
    widget = _preview_with_layout(qapp)
    layout = widget.physical_layout
    assert layout is not None
    point = QPointF(layout.workspace_x_px + 50.0 * layout.mm_to_px, layout.workspace_y_px)
    mm = widget.widget_to_mm(point)
    assert mm is not None
    assert mm[0] == pytest.approx(50.0)
    assert mm[1] == pytest.approx(0.0)
    empty = LayerPreviewWidget()
    assert empty.widget_to_mm(QPointF(1.0, 1.0)) is None


def test_rulers_can_be_hidden_and_change_available_rect(qapp) -> None:
    widget = _preview_with_layout(qapp)
    with_rulers = widget._available_rect()  # noqa: SLF001
    widget.set_rulers_visible(False)
    without = widget._available_rect()  # noqa: SLF001
    assert without.width() > with_rulers.width()
    assert without.height() > with_rulers.height()


# ------------------------------------------------------------- main window


def _window(connected: bool = False) -> MainWindow:
    state = PlotterConnectionState.CONNECTED if connected else PlotterConnectionState.DISCONNECTED
    backend = FakePlotterBackend(detect_result=PlotterStatus(state=state, message="x"))
    return MainWindow(plotter_backend=backend, svg_file_chooser=lambda: None)


def test_top_bar_navigation_switches_properties_tabs(qapp) -> None:
    window = _window()
    tabs = window._properties_tabs
    window._top_bar.settings_requested.emit()
    assert tabs.currentIndex() == TAB_PLOT_SETTINGS
    window._top_bar.device_requested.emit()
    assert tabs.currentIndex() == TAB_DEVICE
    window._top_bar.preview_requested.emit()
    assert tabs.currentIndex() == TAB_TRANSFORM
    window._top_bar.plot_requested.emit()
    assert tabs.currentIndex() == TAB_PLOT_SETTINGS
    window.close()


def test_top_bar_open_button_follows_open_action(qapp) -> None:
    window = _window()
    triggered: list[int] = []
    window._open_svg_action.triggered.connect(lambda: triggered.append(1))
    window._top_bar.open_button.click()
    assert triggered == [1]
    window._open_svg_action.setEnabled(False)
    assert not window._top_bar.open_button.isEnabled()
    window.close()


def test_device_chip_and_device_tab_reflect_status(qapp) -> None:
    window = _window()
    window._apply_plotter_status(
        PlotterStatus(
            state=PlotterConnectionState.CONNECTED,
            message="Firmware 2.7.0",
            backend_version="axicli 3.9.6",
        )
    )
    assert window._top_bar.connection_label.text() == "Connected"
    assert "AxiDraw" in window._top_bar.device_model_label.text()
    assert window._device_panel.firmware_value.text() == "axicli 3.9.6"
    assert window._device_panel.message_label.text() == "Firmware 2.7.0"
    window._apply_plotter_status(
        PlotterStatus(state=PlotterConnectionState.DISCONNECTED, message="Not connected")
    )
    assert window._top_bar.connection_label.text() == "Not connected"
    assert window._device_panel.connection_state_label.text() == "Not connected"
    window.close()


def test_device_tab_buttons_mirror_bottom_bar_enabled_state(qapp) -> None:
    window = _window()
    assert not window._pen_up_button.isEnabled()
    assert not window._device_panel.pen_up_button.isEnabled()
    status = PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok")
    window.plotter_service._status = status  # noqa: SLF001
    window._apply_plotter_status(status)
    assert window._pen_up_button.isEnabled()
    assert window._device_panel.pen_up_button.isEnabled()
    assert window._device_panel.home_button.isEnabled()
    assert window._device_panel.motors_off_button.isEnabled()
    assert window._connect_button.isEnabled()
    window.close()


def test_layer_rows_carry_path_counts_and_colors(qapp) -> None:
    window = _window()
    window.set_document(load_svg_from_path(FIXTURES / "five_inkscape_layers.svg"))
    assert window._layers_list.count() == 5
    item = window._layers_list.item(0)
    assert item is not None
    assert "path" in str(item.data(LAYER_COUNT_ROLE))
    assert item.checkState() == Qt.CheckState.Unchecked
    assert window._layers_panel.count_label.text() == "5"
    assert item.flags() & Qt.ItemFlag.ItemIsUserCheckable
    window.close()


def test_pen_change_banner_hidden_when_idle(qapp) -> None:
    window = _window()
    assert window._action_bar.pen_change_banner.isHidden()
    assert window._multi_continue_button.isHidden()
    assert window._action_bar.progress_row.isHidden()
    window.close()


def test_loading_document_resets_preview_zoom(qapp) -> None:
    window = _window()
    window.set_document(load_svg_from_path(FIXTURES / "simple.svg"))
    window._preview.set_view_zoom(2.0)
    assert window._preview.view_zoom == 2.0
    window.set_document(load_svg_from_path(FIXTURES / "simple.svg"))
    assert window._preview.view_zoom == 1.0
    window.close()
