"""Interactive keep-inside rectangle: gestures, persistence, and plot parity."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt, QThreadPool
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication, QMessageBox

from golden_oracle import parse_prepared_polylines
from plotpilot.models.artwork_transform import ArtworkTransform
from plotpilot.models.clip_shape import ClipRectangle, drag_rectangle, translate_rectangle
from plotpilot.models.multi_layer_job import MultiLayerJobState
from plotpilot.models.plot_settings import PlotSettings
from plotpilot.models.plotter_status import PlotterConnectionState, PlotterStatus
from plotpilot.models.print_margins import PrintableArea, PrintMargins
from plotpilot.models.project_session import ProjectSession
from plotpilot.plotter.fake import FakePlotterBackend
from plotpilot.services.layer_service import layers_for_document
from plotpilot.services.multi_layer_plot_service import MultiLayerPlotService
from plotpilot.services.plot_service import plot_svg_for_layer
from plotpilot.services.plotter_service import PlotterService
from plotpilot.services.positioned_plot_service import prepare_layer_plot_svg
from plotpilot.services.preview_compute_service import compute_interactive_preview
from plotpilot.services.preview_work_area import (
    FallbackWorkArea,
    PreviewWorkArea,
    WorkAreaOrientation,
)
from plotpilot.services.project_file_service import (
    FORMAT_ID,
    SUPPORTED_VERSION,
    ProjectFileError,
    read_project_file,
    write_project_file,
)
from plotpilot.services.settings_service import SettingsService
from plotpilot.services.svg_loader import load_svg_from_path
from plotpilot.ui.main_window import MainWindow
from plotpilot.ui.preview_widget import LayerPreviewWidget
from plotpilot.ui.preview_workspace import PreviewWorkspace
from qt_helpers import wait_for_plot_success, wait_until

FIXTURES = Path(__file__).resolve().parent / "fixtures"
_PLOT_SVG = (FIXTURES / "square_100mm_path.svg").read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def qapp():
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    yield application


def _preview(qapp) -> LayerPreviewWidget:
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


def _px(widget: LayerPreviewWidget, x_mm: float, y_mm: float) -> QPointF:
    point = widget._mm_to_widget(x_mm, y_mm)  # noqa: SLF001
    assert point is not None
    return point


def _mouse(
    kind: QMouseEvent.Type,
    pos: QPointF,
    button: Qt.MouseButton,
    modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
) -> QMouseEvent:
    return QMouseEvent(kind, pos, button, button, modifiers)


def _drag(
    widget: LayerPreviewWidget,
    start: QPointF,
    end: QPointF,
    *,
    button: Qt.MouseButton = Qt.MouseButton.LeftButton,
    modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
) -> None:
    widget.mousePressEvent(_mouse(QMouseEvent.Type.MouseButtonPress, start, button))
    widget.mouseMoveEvent(_mouse(QMouseEvent.Type.MouseMove, end, button, modifiers))
    widget.mouseReleaseEvent(_mouse(QMouseEvent.Type.MouseButtonRelease, end, button, modifiers))


def _key(widget: LayerPreviewWidget, key: Qt.Key) -> None:
    widget.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier))


def _assert_rect(
    rectangle: ClipRectangle | None,
    x_mm: float,
    y_mm: float,
    width_mm: float,
    height_mm: float,
) -> None:
    assert rectangle is not None
    assert rectangle.x_mm == pytest.approx(x_mm, abs=0.05)
    assert rectangle.y_mm == pytest.approx(y_mm, abs=0.05)
    assert rectangle.width_mm == pytest.approx(width_mm, abs=0.05)
    assert rectangle.height_mm == pytest.approx(height_mm, abs=0.05)


def _assert_same_polylines(actual, expected) -> None:
    assert len(actual) == len(expected)
    for left, right in zip(actual, expected, strict=True):
        assert len(left) == len(right)
        for point, other in zip(left, right, strict=True):
            assert point[0] == pytest.approx(other[0], abs=0.02)
            assert point[1] == pytest.approx(other[1], abs=0.02)


# --------------------------------------------------------------- geometry helpers


def test_drag_rectangle_and_shift_square() -> None:
    rect = drag_rectangle(20, 20, 60, 50, square=False, x_min=0, y_min=0, x_max=210, y_max=297)
    _assert_rect(rect, 20, 20, 40, 30)
    square = drag_rectangle(20, 20, 50, 30, square=True, x_min=0, y_min=0, x_max=210, y_max=297)
    _assert_rect(square, 20, 20, 30, 30)
    tiny = drag_rectangle(20, 20, 20.4, 40, square=False, x_min=0, y_min=0, x_max=210, y_max=297)
    assert tiny is None


def test_drag_rectangle_shrinks_square_to_the_bounds() -> None:
    square = drag_rectangle(90, 10, 200, 200, square=True, x_min=0, y_min=0, x_max=100, y_max=100)
    _assert_rect(square, 90, 10, 10, 10)


def test_translate_rectangle_stops_at_the_bounds() -> None:
    moved = translate_rectangle(
        ClipRectangle(20, 20, 40, 30),
        -100,
        5,
        x_min=10,
        y_min=10,
        x_max=200,
        y_max=280,
    )
    _assert_rect(moved, 10, 25, 40, 30)


# ------------------------------------------------------------------- widget tool


def test_clip_tool_draws_moves_resizes_and_deletes(qapp) -> None:
    widget = _preview(qapp)
    widget.set_clip_tool_active(True)
    assert widget.move_tool_active is False

    _drag(widget, _px(widget, 20, 20), _px(widget, 60, 50))
    _assert_rect(widget.clip_rectangle, 20, 20, 40, 30)
    assert widget.artwork_transform == ArtworkTransform.identity()

    _drag(widget, _px(widget, 40, 35), _px(widget, 50, 40))
    _assert_rect(widget.clip_rectangle, 30, 25, 40, 30)

    _drag(widget, _px(widget, 70, 55), _px(widget, 80, 70))
    _assert_rect(widget.clip_rectangle, 30, 25, 50, 45)

    _key(widget, Qt.Key.Key_Delete)
    assert widget.clip_rectangle is None


def test_shift_constrains_draw_and_resize_to_a_square(qapp) -> None:
    widget = _preview(qapp)
    widget.set_clip_tool_active(True)
    shift = Qt.KeyboardModifier.ShiftModifier
    _drag(widget, _px(widget, 20, 20), _px(widget, 50, 35), modifiers=shift)
    _assert_rect(widget.clip_rectangle, 20, 20, 30, 30)

    _drag(widget, _px(widget, 50, 50), _px(widget, 70, 90), modifiers=shift)
    _assert_rect(widget.clip_rectangle, 20, 20, 70, 70)


def test_backspace_deletes_and_other_tools_do_not(qapp) -> None:
    widget = _preview(qapp)
    widget.set_clip_tool_active(True)
    _drag(widget, _px(widget, 20, 20), _px(widget, 50, 40))
    widget.set_move_tool_active(True)
    _key(widget, Qt.Key.Key_Delete)
    assert widget.clip_rectangle is not None
    widget.set_clip_tool_active(True)
    _key(widget, Qt.Key.Key_Backspace)
    assert widget.clip_rectangle is None


def test_tiny_drag_does_not_replace_the_rectangle(qapp) -> None:
    widget = _preview(qapp)
    widget.set_clip_tool_active(True)
    existing = ClipRectangle(40, 40, 20, 20)
    widget.set_clip_rectangle(existing)
    _drag(widget, _px(widget, 10, 10), _px(widget, 10.4, 10.2))
    assert widget.clip_rectangle == existing


def test_rectangle_stays_in_machine_mm_across_zoom_pan_and_transform(qapp) -> None:
    widget = _preview(qapp)
    widget.set_clip_tool_active(True)
    widget.set_view_zoom(2.0)
    widget.pan_by(QPointF(35, -15))
    _drag(widget, _px(widget, 30, 40), _px(widget, 70, 55))
    _assert_rect(widget.clip_rectangle, 30, 40, 40, 15)
    drawn = widget.clip_rectangle

    widget.set_view_zoom(3.0)
    widget.pan_by(QPointF(-20, 10))
    widget.set_artwork_transform(ArtworkTransform(x_mm=12.0, y_mm=-4.0, scale=1.5))
    assert widget.clip_rectangle == drawn

    start = _px(widget, 30, 40)
    end = _px(widget, 70, 55)
    assert widget.widget_to_mm(start)[0] == pytest.approx(drawn.x_mm, abs=0.05)
    assert widget.widget_to_mm(end)[0] == pytest.approx(drawn.x_max_mm, abs=0.05)


def test_draw_is_clamped_to_the_printable_area(qapp) -> None:
    widget = _preview(qapp)
    widget.set_work_area_overlay(
        svg_width_mm=100.0,
        svg_height_mm=100.0,
        work_area=PreviewWorkArea(210.0, 297.0, "A4", True),
        printable_area=PrintableArea(x_mm=10, y_mm=10, width_mm=190, height_mm=277),
    )
    widget.set_clip_tool_active(True)
    _drag(widget, _px(widget, 5, 5), _px(widget, 40, 40))
    assert widget.clip_rectangle is None
    _drag(widget, _px(widget, 16, 18), _px(widget, 2, 4))
    _assert_rect(widget.clip_rectangle, 10, 10, 6, 8)


def test_middle_drag_pans_without_moving_the_rectangle(qapp) -> None:
    widget = _preview(qapp)
    widget.set_clip_tool_active(True)
    widget.set_clip_rectangle(ClipRectangle(20, 20, 30, 30))
    before = widget.physical_layout
    assert before is not None
    _drag(
        widget,
        QPointF(300, 200),
        QPointF(330, 180),
        button=Qt.MouseButton.MiddleButton,
    )
    assert widget.clip_rectangle == ClipRectangle(20, 20, 30, 30)
    assert widget.artwork_transform == ArtworkTransform.identity()
    after = widget.physical_layout
    assert after is not None
    assert after.workspace_x_px == pytest.approx(before.workspace_x_px + 30)


def test_clip_and_move_tools_are_mutually_exclusive(qapp) -> None:
    workspace = PreviewWorkspace()
    assert workspace.move_button.isChecked()
    assert not workspace.clip_button.isChecked()

    workspace.clip_button.setChecked(True)
    assert workspace.preview.clip_tool_active is True
    assert workspace.preview.move_tool_active is False
    assert not workspace.move_button.isChecked()

    workspace.move_button.setChecked(True)
    assert workspace.preview.move_tool_active is True
    assert workspace.preview.clip_tool_active is False
    assert not workspace.clip_button.isChecked()

    workspace.preview.set_transform_controls_enabled(False)
    assert not workspace.clip_button.isEnabled()
    assert not workspace.move_button.isEnabled()


def test_clip_overlay_is_amber_and_distinct_from_the_printable_outline(qapp) -> None:
    widget = _preview(qapp)
    widget.set_work_area_overlay(
        svg_width_mm=100.0,
        svg_height_mm=100.0,
        work_area=PreviewWorkArea(210.0, 297.0, "A4", True),
        printable_area=PrintableArea(x_mm=10, y_mm=10, width_mm=190, height_mm=277),
    )
    widget.set_clip_tool_active(True)
    widget.set_clip_rectangle(ClipRectangle(40, 50, 30, 20))
    qapp.processEvents()
    image = widget.grab().toImage()
    corner = _px(widget, 40, 50)
    handle = image.pixelColor(int(corner.x()), int(corner.y()))
    outline = _px(widget, 10, 10)
    printable = image.pixelColor(int(outline.x()), int(outline.y()))
    assert handle.red() > handle.blue()
    assert printable.blue() > printable.red()


# --------------------------------------------------------------- save and plot


def _sample_session(svg: Path, rectangle: ClipRectangle | None) -> ProjectSession:
    return ProjectSession(
        svg_path=svg,
        checked_layer_ids=(),
        artwork_transform=ArtworkTransform.identity(),
        plot_settings=PlotSettings(),
        fallback_work_area=FallbackWorkArea.A4,
        clip_rectangle=rectangle,
    )


def test_project_round_trip_keeps_version_and_omits_an_absent_rectangle(tmp_path: Path) -> None:
    svg = FIXTURES / "simple.svg"
    project_file = tmp_path / "job.plotpilot"
    write_project_file(project_file, _sample_session(svg.resolve(), None))
    bare = json.loads(project_file.read_text(encoding="utf-8"))
    assert bare["version"] == SUPPORTED_VERSION
    assert "clipping" not in bare
    assert read_project_file(project_file).clip_rectangle is None

    rectangle = ClipRectangle(12.5, 8.0, 40.0, 22.0)
    write_project_file(project_file, _sample_session(svg.resolve(), rectangle))
    saved = json.loads(project_file.read_text(encoding="utf-8"))
    assert saved["version"] == 1
    assert saved["format"] == FORMAT_ID
    assert read_project_file(project_file).clip_rectangle == rectangle


def test_old_project_without_clipping_still_opens(tmp_path: Path) -> None:
    project_file = tmp_path / "legacy.plotpilot"
    project_file.write_text(
        json.dumps(
            {
                "format": FORMAT_ID,
                "version": 1,
                "svg": {"path": str(FIXTURES / "simple.svg")},
            }
        ),
        encoding="utf-8",
    )
    assert read_project_file(project_file).clip_rectangle is None


def test_invalid_clipping_is_rejected(tmp_path: Path) -> None:
    project_file = tmp_path / "bad.plotpilot"
    project_file.write_text(
        json.dumps(
            {
                "format": FORMAT_ID,
                "version": 1,
                "svg": {"path": str(FIXTURES / "simple.svg")},
                "clipping": {"rectangle": {"x_mm": 0, "y_mm": 0, "width_mm": 0, "height_mm": 10}},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ProjectFileError, match="Clipping"):
        read_project_file(project_file)


def _connected_plotter(qapp):
    _ = qapp
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok"),
    )
    service = PlotterService(fake)
    service._status = fake.detect_result  # noqa: SLF001
    return service, fake


def test_preview_plot_and_estimate_use_the_same_rectangle(qapp) -> None:
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    layer = layers_for_document(document)[0]
    rectangle = ClipRectangle(0, 0, 1, 1)
    margins = PrintMargins(0, 0)
    settings = PlotSettings()
    prepared = prepare_layer_plot_svg(
        plot_svg_for_layer(document, layer),
        plot_settings=settings,
        transform=ArtworkTransform.identity(),
        print_margins=margins,
        keep_inside=rectangle,
    )
    unclipped = prepare_layer_plot_svg(
        plot_svg_for_layer(document, layer),
        plot_settings=settings,
        transform=ArtworkTransform.identity(),
        print_margins=margins,
    )
    assert prepared.svg_text != unclipped.svg_text
    assert "clipPath" not in prepared.svg_text
    assert "<rect" not in prepared.svg_text

    preview = compute_interactive_preview(
        document,
        layer,
        cached_geometry=None,
        transform=ArtworkTransform.identity(),
        plot_settings=settings,
        fallback=FallbackWorkArea.A4,
        fallback_orientation=WorkAreaOrientation.PORTRAIT,
        print_margins=margins,
        keep_inside=rectangle,
    )
    _assert_same_polylines(preview.clipped.polylines, parse_prepared_polylines(prepared.svg_text))

    service, fake = _connected_plotter(qapp)
    assert (
        service.start_plot_layer(
            document,
            layer,
            plot_settings=settings,
            print_margins=margins,
            keep_inside=rectangle,
        )
        is None
    )
    wait_for_plot_success(service)
    assert fake.plot_file_contents == [prepared.svg_text]

    assert (
        service.request_pre_plot_estimate(
            document,
            [layer],
            plot_settings=settings,
            print_margins=margins,
            keep_inside=rectangle,
        )
        is None
    )
    wait_until(lambda: fake.estimate_file_contents == [prepared.svg_text])


def test_margins_still_limit_the_keep_inside_rectangle() -> None:
    document = load_svg_from_path(FIXTURES / "square_100mm_path.svg")
    layer = layers_for_document(document)[0]
    prepared = prepare_layer_plot_svg(
        plot_svg_for_layer(document, layer),
        plot_settings=PlotSettings(),
        transform=ArtworkTransform.identity(),
        print_margins=PrintMargins(10, 10),
        keep_inside=ClipRectangle(0, 0, 30, 30),
    )
    polylines = parse_prepared_polylines(prepared.svg_text)
    assert polylines
    for line in polylines:
        for x_mm, y_mm in line:
            assert 10 - 0.05 <= x_mm <= 30.05
            assert 10 - 0.05 <= y_mm <= 30.05


def test_multi_layer_plot_uses_the_rectangle_on_every_layer(qapp) -> None:
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    layers = layers_for_document(document)
    rectangle = ClipRectangle(0, 0, 6, 6)
    margins = PrintMargins(0, 0)
    settings = PlotSettings()
    service, fake = _connected_plotter(qapp)
    multi = MultiLayerPlotService(service)
    assert (
        multi.start_job(
            document,
            layers,
            settings=settings,
            print_margins=margins,
            keep_inside=rectangle,
        )
        is None
    )
    wait_until(
        lambda: multi.job.state is MultiLayerJobState.WAITING_FOR_PEN_CHANGE,
        timeout_ms=5000,
    )
    assert multi.continue_after_pen_change() is None
    wait_until(lambda: multi.job.state is MultiLayerJobState.COMPLETED, timeout_ms=5000)
    assert len(fake.plot_file_contents) == 2
    for layer, plotted in zip(layers, fake.plot_file_contents, strict=True):
        prepared = prepare_layer_plot_svg(
            plot_svg_for_layer(document, layer),
            plot_settings=settings,
            transform=ArtworkTransform.identity(),
            print_margins=margins,
            keep_inside=rectangle,
        )
        assert plotted == prepared.svg_text
        assert "clipPath" not in plotted


def _window(qapp) -> MainWindow:
    _ = qapp
    settings = SettingsService(organization="PlotPilotTestClipTool", application="clip-tool")
    return MainWindow(
        plotter_backend=FakePlotterBackend(),
        settings_service=settings,
        svg_file_chooser=lambda: None,
    )


def _wait_for_preview(window: MainWindow, qapp) -> None:
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        qapp.processEvents()
        if (
            not window._preview_prep_timer.isActive()
            and QThreadPool.globalInstance().activeThreadCount() == 0
            and not window._preview.clip_pending
        ):
            qapp.processEvents()
            return
        time.sleep(0.02)
    raise AssertionError("Timed out waiting for the preview clip")


def test_main_window_passes_the_rectangle_and_reuses_flattened_geometry(qapp, monkeypatch) -> None:
    window = _window(qapp)
    window.resize(1100, 720)
    window.show()
    window.set_document(load_svg_from_path(FIXTURES / "square_100mm_path.svg"))
    _wait_for_preview(window, qapp)
    prepared = window._geometry_cache.prepare_count
    clipped = window._geometry_cache.clip_count
    assert prepared >= 1

    rectangle = ClipRectangle(40, 40, 20, 20)
    for index in range(8):
        window._preview.set_clip_rectangle(
            ClipRectangle(40, 40, 20 + index, 20),
        )
    _wait_for_preview(window, qapp)
    assert window._geometry_cache.prepare_count == prepared
    assert window._geometry_cache.clip_count == clipped + 1
    assert window._project_dirty is True

    captured: list[tuple[str, object]] = []

    def record(name):
        def spy(*_args, **kwargs):
            captured.append((name, kwargs.get("keep_inside")))
            return None

        return spy

    monkeypatch.setattr(window._plotter_service, "request_pre_plot_estimate", record("estimate"))
    monkeypatch.setattr(window._plotter_service, "start_plot_layer", record("plot"))
    monkeypatch.setattr(window._multi_layer_service, "start_job", record("multi"))
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Ok,
    )
    window._preview.set_clip_rectangle(rectangle)
    item = window._layers_list.item(0)
    assert item is not None
    item.setCheckState(Qt.CheckState.Checked)
    window._on_estimate_plot()
    window._on_plot_selected_layer()
    window._on_plot_checked_layers()
    assert captured == [("estimate", rectangle), ("plot", rectangle), ("multi", rectangle)]
    window.close()


def test_opening_a_project_restores_or_clears_the_rectangle(qapp, tmp_path: Path) -> None:
    svg = (FIXTURES / "simple.svg").resolve()
    rectangle = ClipRectangle(15, 25, 30, 18)
    project_file = tmp_path / "kept.plotpilot"
    write_project_file(project_file, _sample_session(svg, rectangle))
    chosen = {"path": str(project_file)}

    def choose() -> str:
        return chosen["path"]

    settings = SettingsService(organization="PlotPilotTestClipOpen", application="clip-open")
    window = MainWindow(
        plotter_backend=FakePlotterBackend(),
        settings_service=settings,
        project_file_chooser=choose,
    )
    window.set_document(load_svg_from_path(svg))
    window._preview.set_clip_rectangle(ClipRectangle(1, 1, 10, 10))
    window._open_project()
    _wait_for_preview(window, qapp)
    assert window._preview.clip_rectangle == rectangle
    assert window._project_dirty is False

    legacy = tmp_path / "legacy.plotpilot"
    legacy.write_text(
        json.dumps({"format": FORMAT_ID, "version": 1, "svg": {"path": str(svg)}}),
        encoding="utf-8",
    )
    chosen["path"] = str(legacy)
    window._open_project()
    assert window._preview.clip_rectangle is None
    assert window._project_dirty is False
    window.close()
