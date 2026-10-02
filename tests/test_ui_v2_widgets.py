"""V2 presentation widgets: theme, layout helpers, preview view state, panel wiring."""

from __future__ import annotations

from pathlib import Path
from xml.etree.ElementTree import Element

import pytest
from PySide6.QtCore import QPointF, QRect, Qt, QThreadPool
from PySide6.QtGui import QFont, QMouseEvent
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
from plotpilot.ui.preview_workspace import PreviewWorkspace
from plotpilot.ui.properties_panel import TAB_DEVICE
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


def test_stylesheet_uses_bundled_check_mark() -> None:
    from plotpilot.ui.theme import build_stylesheet, check_mark_url

    url = check_mark_url()
    assert url.startswith('image: url("') and url.endswith('check.svg");')
    sheet = build_stylesheet()
    assert url in sheet
    # The old Qt-internal resource path does not exist in PySide6.
    assert ":/qt-project.org/" not in sheet
    # Radio indicators must not rely on a thick border (rendered as a rounded square).
    assert "border: 4px" not in sheet


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


# ---------------------------------------------------- move tool vs view pan


def _mouse(kind: QMouseEvent.Type, pos: QPointF, button: Qt.MouseButton) -> QMouseEvent:
    return QMouseEvent(kind, pos, button, button, Qt.KeyboardModifier.NoModifier)


def _drag(widget: LayerPreviewWidget, button: Qt.MouseButton, start: QPointF, end: QPointF) -> None:
    widget.mousePressEvent(_mouse(QMouseEvent.Type.MouseButtonPress, start, button))
    widget.mouseMoveEvent(_mouse(QMouseEvent.Type.MouseMove, end, button))
    widget.mouseReleaseEvent(_mouse(QMouseEvent.Type.MouseButtonRelease, end, button))


def test_move_tool_is_on_by_default(qapp) -> None:
    widget = _preview_with_layout(qapp)
    assert widget.move_tool_active is True
    assert widget.cursor().shape() == Qt.CursorShape.SizeAllCursor


def test_move_tool_drag_moves_artwork_not_the_view(qapp) -> None:
    widget = _preview_with_layout(qapp)
    layout = widget.physical_layout
    assert layout is not None
    emitted: list[ArtworkTransform] = []
    widget.artwork_transform_changed.connect(emitted.append)
    widget.set_move_tool_active(True)

    _drag(widget, Qt.MouseButton.LeftButton, QPointF(300.0, 200.0), QPointF(340.0, 170.0))

    moved = widget.artwork_transform
    assert moved.x_mm == pytest.approx(40.0 / layout.mm_to_px)
    assert moved.y_mm == pytest.approx(-30.0 / layout.mm_to_px)
    assert emitted and emitted[-1] == moved
    # The gesture must not leave a residual view pan: layout origin is unchanged.
    assert widget.view_pan_px.isNull()
    after = widget.physical_layout
    assert after is not None
    assert after.workspace_x_px == pytest.approx(layout.workspace_x_px)
    assert after.workspace_y_px == pytest.approx(layout.workspace_y_px)
    assert widget.view_zoom == 1.0


def test_move_tool_drag_uses_zoomed_scale(qapp) -> None:
    widget = _preview_with_layout(qapp)
    widget.set_view_zoom(2.0)
    zoomed = widget.physical_layout
    assert zoomed is not None
    pan_before = widget.view_pan_px

    _drag(widget, Qt.MouseButton.LeftButton, QPointF(300.0, 200.0), QPointF(350.0, 200.0))

    # 50 px at 2x zoom is half the mm of 50 px at fit: the drawing follows the cursor.
    assert widget.artwork_transform.x_mm == pytest.approx(50.0 / zoomed.mm_to_px)
    assert widget.artwork_transform.y_mm == pytest.approx(0.0)
    assert widget.view_pan_px == pan_before


def test_move_tool_off_makes_left_drag_inert(qapp) -> None:
    widget = _preview_with_layout(qapp)
    widget.set_move_tool_active(False)
    assert widget.cursor().shape() != Qt.CursorShape.SizeAllCursor
    emitted: list[ArtworkTransform] = []
    widget.artwork_transform_changed.connect(emitted.append)

    _drag(widget, Qt.MouseButton.LeftButton, QPointF(300.0, 200.0), QPointF(340.0, 170.0))

    assert widget.artwork_transform == ArtworkTransform.identity()
    assert emitted == []
    assert widget.view_pan_px.isNull()


def test_move_tool_has_no_effect_while_transform_locked(qapp) -> None:
    widget = _preview_with_layout(qapp)
    states: list[bool] = []
    widget.transform_controls_enabled_changed.connect(states.append)
    widget.set_transform_controls_enabled(False)
    assert states == [False]
    assert widget.cursor().shape() != Qt.CursorShape.SizeAllCursor

    _drag(widget, Qt.MouseButton.LeftButton, QPointF(300.0, 200.0), QPointF(340.0, 170.0))

    assert widget.artwork_transform == ArtworkTransform.identity()
    widget.set_transform_controls_enabled(True)
    assert states == [False, True]
    _drag(widget, Qt.MouseButton.LeftButton, QPointF(300.0, 200.0), QPointF(340.0, 200.0))
    assert widget.artwork_transform.x_mm > 0.0


def test_middle_drag_pans_the_view_only(qapp) -> None:
    widget = _preview_with_layout(qapp)
    base = widget.physical_layout
    assert base is not None
    widget.set_artwork_transform(ArtworkTransform(x_mm=5.0, y_mm=7.0))

    _drag(widget, Qt.MouseButton.MiddleButton, QPointF(300.0, 200.0), QPointF(325.0, 190.0))

    assert widget.artwork_transform == ArtworkTransform(x_mm=5.0, y_mm=7.0)
    assert widget.view_pan_px == QPointF(25.0, -10.0)
    panned = widget.physical_layout
    assert panned is not None
    assert panned.workspace_x_px == pytest.approx(base.workspace_x_px + 25.0)
    assert panned.workspace_y_px == pytest.approx(base.workspace_y_px - 10.0)
    widget.fit_view()
    assert widget.view_pan_px.isNull()
    assert widget.artwork_transform == ArtworkTransform(x_mm=5.0, y_mm=7.0)


def test_workspace_hand_button_drives_move_tool_and_follows_lock(qapp) -> None:
    workspace = PreviewWorkspace()
    button = workspace.move_button
    tooltip = button.toolTip().lower()
    assert "move" in tooltip and "drawing" in tooltip
    assert "pan the view" not in tooltip.split("\n")[0]
    assert button.isCheckable() and button.isChecked()
    assert workspace.preview.move_tool_active is True

    button.setChecked(False)
    assert workspace.preview.move_tool_active is False
    button.setChecked(True)
    assert workspace.preview.move_tool_active is True

    workspace.preview.set_transform_controls_enabled(False)
    assert not button.isEnabled()
    workspace.preview.set_transform_controls_enabled(True)
    assert button.isEnabled()


# ------------------------------------------------------------- main window


def _window(connected: bool = False) -> MainWindow:
    state = PlotterConnectionState.CONNECTED if connected else PlotterConnectionState.DISCONNECTED
    backend = FakePlotterBackend(detect_result=PlotterStatus(state=state, message="x"))
    return MainWindow(plotter_backend=backend, svg_file_chooser=lambda: None)


def test_top_bar_device_chip_switches_to_device_tab(qapp) -> None:
    window = _window()
    tabs = window._properties_tabs
    window._top_bar.device_requested.emit()
    assert tabs.currentIndex() == TAB_DEVICE
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


def test_hand_drag_syncs_transform_panel_and_marks_dirty(qapp, tmp_path: Path) -> None:
    svg_path = tmp_path / "a4.svg"
    svg_path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="297mm" '
        'viewBox="0 0 210 297"><path d="M10 10 L100 100" stroke="#000" fill="none"/></svg>',
        encoding="utf-8",
    )
    window = _window()
    window.resize(1240, 800)
    window.show()
    qapp.processEvents()
    window.set_document(load_svg_from_path(svg_path))
    window._refresh_preview_work_area()
    assert QThreadPool.globalInstance().waitForDone(5000)
    qapp.processEvents()
    preview = window._preview
    layout = preview.physical_layout
    assert layout is not None
    assert preview.move_tool_active is True
    assert window.project_dirty is False
    controls = window._artwork_controls
    x_before = controls._x_spin.value()  # noqa: SLF001
    y_before = controls._y_spin.value()  # noqa: SLF001

    center = QPointF(preview.rect().center())
    _drag(preview, Qt.MouseButton.LeftButton, center, center + QPointF(60.0, -20.0))
    qapp.processEvents()

    assert preview.view_pan_px.isNull()
    assert preview.view_zoom == 1.0
    assert controls._x_spin.value() == pytest.approx(  # noqa: SLF001
        x_before + 60.0 / layout.mm_to_px, abs=0.05
    )
    assert controls._y_spin.value() == pytest.approx(  # noqa: SLF001
        y_before - 20.0 / layout.mm_to_px, abs=0.05
    )
    assert window.project_dirty is True
    window.close()


def test_hand_button_disabled_while_transform_locked(qapp) -> None:
    window = _window()
    button = window._workspace.move_button
    assert button.isEnabled()
    window._preview.set_transform_controls_enabled(False)
    assert not button.isEnabled()
    window._preview.set_transform_controls_enabled(True)
    assert button.isEnabled()
    window.close()


def test_loading_document_resets_preview_zoom(qapp) -> None:
    window = _window()
    window.set_document(load_svg_from_path(FIXTURES / "simple.svg"))
    window._preview.set_view_zoom(2.0)
    assert window._preview.view_zoom == 2.0
    window.set_document(load_svg_from_path(FIXTURES / "simple.svg"))
    assert window._preview.view_zoom == 1.0
    window.close()
