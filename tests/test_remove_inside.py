"""Remove-inside holes for rectangles, circles, and ellipses."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from golden_oracle import parse_prepared_polylines
from plotpilot.geometry.plot_viewport import (
    PlotViewportError,
    clip_document_polylines,
    prepare_positioned_plot_svg,
)
from plotpilot.models.artwork_transform import ArtworkTransform
from plotpilot.models.clip_shape import ClipEllipse, ClipMode, ClipRectangle
from plotpilot.models.multi_layer_job import MultiLayerJobState
from plotpilot.models.plot_settings import PlotSettings
from plotpilot.models.plotter_status import PlotterConnectionState, PlotterStatus
from plotpilot.models.print_margins import PrintMargins
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
    ProjectFileError,
    read_project_file,
    write_project_file,
)
from plotpilot.services.svg_loader import load_svg_from_path
from plotpilot.ui.preview_widget import LayerPreviewWidget
from plotpilot.ui.preview_workspace import PreviewWorkspace
from qt_helpers import wait_for_plot_success, wait_until

FIXTURES = Path(__file__).resolve().parent / "fixtures"
_EMPTY = "No artwork intersects the plot area."
_REMOVE = ClipMode.REMOVE_INSIDE


@pytest.fixture(scope="session")
def qapp():
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    yield application


def _line(x0: float, y0: float, x1: float, y1: float, *, close: str = "") -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" '
        'viewBox="0 0 100 100">\n'
        f'  <path d="M {x0} {y0} L {x1} {y1}{close}" fill="none" stroke="black"/>\n'
        "</svg>\n"
    )


def _path(d: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" '
        'viewBox="0 0 100 100">\n'
        f'  <path d="{d}" fill="none" stroke="black"/>\n'
        "</svg>\n"
    )


def _prepare(svg: str, shape, *, mode: ClipMode = _REMOVE, clip=None):
    kwargs = {}
    if clip is not None:
        kwargs = {
            "clip_x_min_mm": clip[0],
            "clip_y_min_mm": clip[1],
            "clip_x_max_mm": clip[2],
            "clip_y_max_mm": clip[3],
        }
    prepared = prepare_positioned_plot_svg(
        svg,
        viewport_width_mm=100.0,
        viewport_height_mm=100.0,
        transform=ArtworkTransform.identity(),
        keep_inside=shape,
        clip_mode=mode,
        **kwargs,
    )
    return prepared, parse_prepared_polylines(prepared.svg_text)


def _assert_gap(polylines, x_lo: float, x_hi: float, *, y: float) -> None:
    assert len(polylines) == 2
    xs = [point[0] for line in polylines for point in line]
    assert min(xs) < x_lo
    assert max(xs) > x_hi
    for line in polylines:
        for x_mm, y_mm in line:
            if y_mm == pytest.approx(y, abs=0.05):
                assert x_mm <= x_lo + 0.05 or x_mm >= x_hi - 0.05
    assert prepared_paths_are_separate(polylines)


def prepared_paths_are_separate(polylines) -> bool:
    ends = [line[-1] for line in polylines[:-1]]
    starts = [line[0] for line in polylines[1:]]
    return all(
        abs(end[0] - start[0]) > 1.0 or abs(end[1] - start[1]) > 1.0
        for end, start in zip(ends, starts, strict=True)
    )


def test_rectangle_circle_and_ellipse_holes_split_a_line() -> None:
    svg = _line(0, 50, 100, 50)
    rectangle, _ = _prepare(svg, ClipRectangle(40, 40, 20, 20))
    _assert_gap(parse_prepared_polylines(rectangle.svg_text), 40, 60, y=50)
    circle, _ = _prepare(svg, ClipEllipse(50, 50, 10, 10))
    _assert_gap(parse_prepared_polylines(circle.svg_text), 40, 60, y=50)
    ellipse, _ = _prepare(svg, ClipEllipse(50, 50, 20, 10))
    _assert_gap(parse_prepared_polylines(ellipse.svg_text), 30, 70, y=50)
    assert rectangle.svg_text.count("<path") == 2
    assert "clipPath" not in circle.svg_text


def test_inside_segment_disappears_and_outside_segment_stays() -> None:
    hole = ClipEllipse(50, 50, 10, 10)
    with pytest.raises(PlotViewportError, match=_EMPTY):
        _prepare(_line(45, 50, 55, 50), hole)
    _prepared, outside = _prepare(_line(0, 10, 100, 10), hole)
    assert len(outside) == 1
    assert outside[0][0][1] == pytest.approx(10, abs=0.05)
    assert outside[0][-1][0] == pytest.approx(100, abs=0.05)


def test_tangent_contact_does_not_open_a_hole() -> None:
    _prepared, polylines = _prepare(_line(0, 60, 100, 60), ClipEllipse(50, 50, 10, 10))
    assert len(polylines) == 1
    assert polylines[0][0] == pytest.approx((0, 60), abs=0.05)
    assert polylines[0][-1] == pytest.approx((100, 60), abs=0.05)


def test_multiple_crossings_and_a_closed_path_stay_split() -> None:
    svg = _path("M 0 50 L 100 50 L 100 80 L 0 80")
    _prepared, polylines = _prepare(svg, ClipEllipse(50, 50, 10, 10))
    assert len(polylines) == 2
    assert prepared_paths_are_separate(polylines)
    closed = _path("M 0 50 L 100 50 L 100 70 L 0 70 Z")
    _closed_svg, pieces = _prepare(closed, ClipRectangle(40, 45, 20, 20))
    assert len(pieces) >= 2
    assert prepared_paths_are_separate(pieces)
    for line in pieces:
        for index, point in enumerate(line[:-1]):
            nxt = line[index + 1]
            mid_x = (point[0] + nxt[0]) / 2
            mid_y = (point[1] + nxt[1]) / 2
            inside_hole = 40 < mid_x < 60 and 45 < mid_y < 65
            assert not inside_hole


def test_zero_length_segments_are_dropped() -> None:
    hole = ClipRectangle(40, 40, 20, 20)
    assert (
        clip_document_polylines(
            [((50, 50), (50, 50))],
            ArtworkTransform.identity(),
            viewport_width_mm=100.0,
            viewport_height_mm=100.0,
            keep_inside=hole,
            clip_mode=_REMOVE,
        )
        == []
    )
    assert (
        clip_document_polylines(
            [((5, 5), (5, 5))],
            ArtworkTransform.identity(),
            viewport_width_mm=100.0,
            viewport_height_mm=100.0,
            keep_inside=hole,
            clip_mode=_REMOVE,
        )
        == []
    )


def test_margins_and_a_shape_past_the_printable_edge() -> None:
    hole = ClipRectangle(40, 40, 20, 20)
    _prepared, polylines = _prepare(_line(0, 50, 100, 50), hole, clip=(10, 0, 90, 100))
    for line in polylines:
        for x_mm, y_mm in line:
            assert 10 - 0.05 <= x_mm <= 90.05
            assert 0 <= y_mm <= 100
    _partial, partial_lines = _prepare(
        _line(0, 50, 80, 50),
        ClipRectangle(0, 40, 30, 20),
        clip=(10, 0, 100, 100),
    )
    assert partial_lines[0][0][0] == pytest.approx(30, abs=0.05)
    for line in partial_lines:
        for x_mm, _y_mm in line:
            assert x_mm >= 10 - 0.05
    missed = ClipRectangle(-40, 0, 10, 10)
    plain, plain_lines = _prepare(_line(0, 50, 100, 50), None, mode=ClipMode.KEEP_INSIDE)
    outside, outside_lines = _prepare(_line(0, 50, 100, 50), missed)
    assert plain.svg_text == outside.svg_text
    assert plain_lines == outside_lines
    covered = ClipRectangle(-10, -10, 200, 200)
    with pytest.raises(PlotViewportError, match=_EMPTY):
        _prepare(_line(0, 50, 100, 50), covered)


def test_keep_inside_and_no_shape_are_unchanged() -> None:
    svg = _line(0, 50, 100, 50)
    kept, kept_lines = _prepare(
        svg,
        ClipRectangle(40, 40, 20, 20),
        mode=ClipMode.KEEP_INSIDE,
    )
    assert len(kept_lines) == 1
    assert kept_lines[0][0][0] == pytest.approx(40, abs=0.05)
    assert kept_lines[0][-1][0] == pytest.approx(60, abs=0.05)
    ellipse, ellipse_lines = _prepare(
        svg,
        ClipEllipse(50, 50, 20, 10),
        mode=ClipMode.KEEP_INSIDE,
    )
    assert ellipse_lines[0][0][0] == pytest.approx(30, abs=0.05)
    assert ellipse_lines[0][-1][0] == pytest.approx(70, abs=0.05)
    bare, _bare_lines = _prepare(svg, None, mode=ClipMode.KEEP_INSIDE)
    removed_without_shape, _ = _prepare(svg, None)
    assert bare.svg_text == removed_without_shape.svg_text
    assert "M 0 50 L 100 50" in bare.svg_text or "M 0 50" in bare.svg_text
    assert kept.svg_text != bare.svg_text
    assert ellipse.svg_text != bare.svg_text


def _px(widget: LayerPreviewWidget, x_mm: float, y_mm: float) -> QPointF:
    point = widget._mm_to_widget(x_mm, y_mm)  # noqa: SLF001
    assert point is not None
    return point


def _drag(widget: LayerPreviewWidget, start: QPointF, end: QPointF) -> None:
    button = Qt.MouseButton.LeftButton
    modifiers = Qt.KeyboardModifier.NoModifier
    widget.mousePressEvent(
        QMouseEvent(QMouseEvent.Type.MouseButtonPress, start, button, button, modifiers)
    )
    widget.mouseMoveEvent(QMouseEvent(QMouseEvent.Type.MouseMove, end, button, button, modifiers))
    widget.mouseReleaseEvent(
        QMouseEvent(QMouseEvent.Type.MouseButtonRelease, end, button, button, modifiers)
    )


def test_mode_switch_keeps_the_shape_and_the_view(qapp) -> None:
    widget = LayerPreviewWidget()
    widget.resize(600, 400)
    widget.show()
    qapp.processEvents()
    assert widget.set_preview_svg((FIXTURES / "square_100mm_path.svg").read_text(encoding="utf-8"))
    widget.set_work_area_overlay(
        svg_width_mm=100.0,
        svg_height_mm=100.0,
        work_area=PreviewWorkArea(210.0, 297.0, "A4", True),
    )
    widget.set_clip_tool_active(True)
    widget.set_clip_kind("ellipse")
    _drag(widget, _px(widget, 30, 40), _px(widget, 70, 60))
    drawn = widget.clip_shape
    widget.set_view_zoom(1.6)
    widget.pan_by(QPointF(12, -8))
    zoom = widget.view_zoom
    pan = QPointF(widget._view_pan_px)  # noqa: SLF001
    widget.set_clip_mode(ClipMode.REMOVE_INSIDE)
    assert widget.clip_shape == drawn
    assert widget.view_zoom == zoom
    assert widget._view_pan_px == pan  # noqa: SLF001
    assert isinstance(drawn, ClipEllipse)
    _drag(widget, _px(widget, drawn.cx_mm, drawn.cy_mm), _px(widget, drawn.cx_mm + 8, drawn.cy_mm))
    moved = widget.clip_shape
    assert isinstance(moved, ClipEllipse)
    assert moved.cx_mm == pytest.approx(drawn.cx_mm + 8, abs=0.05)
    assert moved.rx_mm == pytest.approx(drawn.rx_mm)
    workspace = PreviewWorkspace()
    workspace.preview.set_clip_shape(drawn)
    workspace.clip_button.setChecked(True)
    assert workspace.keep_mode_button.isChecked()
    workspace.remove_mode_button.setChecked(True)
    assert workspace.preview.clip_mode is ClipMode.REMOVE_INSIDE
    assert workspace.preview.clip_shape == drawn


def test_project_file_defaults_to_keep_inside_and_stores_remove(tmp_path: Path) -> None:
    svg = (FIXTURES / "simple.svg").resolve()
    rectangle = ClipRectangle(12, 8, 40, 22)
    path = tmp_path / "clip.plotpilot"
    write_project_file(
        path,
        ProjectSession(
            svg_path=svg,
            checked_layer_ids=(),
            artwork_transform=ArtworkTransform.identity(),
            plot_settings=PlotSettings(),
            fallback_work_area=FallbackWorkArea.A4,
            clip_rectangle=rectangle,
        ),
    )
    loaded = read_project_file(path)
    assert loaded.clip_mode is ClipMode.KEEP_INSIDE
    assert "mode" not in json.loads(path.read_text(encoding="utf-8"))["clipping"]
    write_project_file(
        path,
        ProjectSession(
            svg_path=svg,
            checked_layer_ids=(),
            artwork_transform=ArtworkTransform.identity(),
            plot_settings=PlotSettings(),
            fallback_work_area=FallbackWorkArea.A4,
            clip_ellipse=ClipEllipse(40, 50, 15, 10),
            clip_mode=ClipMode.REMOVE_INSIDE,
        ),
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert data["clipping"]["mode"] == "remove_inside"
    assert read_project_file(path).clip_mode is ClipMode.REMOVE_INSIDE
    legacy = tmp_path / "legacy.plotpilot"
    legacy.write_text(
        json.dumps(
            {
                "format": FORMAT_ID,
                "version": 1,
                "svg": {"path": str(svg)},
                "clipping": {
                    "rectangle": {"x_mm": 1, "y_mm": 2, "width_mm": 3, "height_mm": 4},
                },
            }
        ),
        encoding="utf-8",
    )
    assert read_project_file(legacy).clip_mode is ClipMode.KEEP_INSIDE
    bad = tmp_path / "bad.plotpilot"
    bad.write_text(
        json.dumps(
            {
                "format": FORMAT_ID,
                "version": 1,
                "svg": {"path": str(svg)},
                "clipping": {
                    "ellipse": {"cx_mm": 1, "cy_mm": 1, "rx_mm": 4, "ry_mm": 4},
                    "mode": "punch",
                },
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ProjectFileError, match="Clipping"):
        read_project_file(bad)


def test_preview_plot_estimate_and_multi_layer_share_the_hole(qapp) -> None:
    _ = qapp
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    layers = layers_for_document(document)
    hole = ClipEllipse(4, 4, 3, 3)
    margins = PrintMargins(0, 0)
    settings = PlotSettings()
    prepared = prepare_layer_plot_svg(
        plot_svg_for_layer(document, layers[0]),
        plot_settings=settings,
        transform=ArtworkTransform.identity(),
        print_margins=margins,
        keep_inside=hole,
        clip_mode=_REMOVE,
    )
    unclipped = prepare_layer_plot_svg(
        plot_svg_for_layer(document, layers[0]),
        plot_settings=settings,
        transform=ArtworkTransform.identity(),
        print_margins=margins,
    )
    assert prepared.svg_text != unclipped.svg_text
    preview = compute_interactive_preview(
        document,
        layers[0],
        cached_geometry=None,
        transform=ArtworkTransform.identity(),
        plot_settings=settings,
        fallback=FallbackWorkArea.A4,
        fallback_orientation=WorkAreaOrientation.PORTRAIT,
        print_margins=margins,
        keep_inside=hole,
        clip_mode=_REMOVE,
    )
    assert len(preview.clipped.polylines) == len(parse_prepared_polylines(prepared.svg_text))
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok"),
    )
    service = PlotterService(fake)
    service._status = fake.detect_result  # noqa: SLF001
    assert (
        service.start_plot_layer(
            document,
            layers[0],
            plot_settings=settings,
            print_margins=margins,
            keep_inside=hole,
            clip_mode=_REMOVE,
        )
        is None
    )
    wait_for_plot_success(service)
    assert fake.plot_file_contents == [prepared.svg_text]
    assert (
        service.request_pre_plot_estimate(
            document,
            [layers[0]],
            plot_settings=settings,
            print_margins=margins,
            keep_inside=hole,
            clip_mode=_REMOVE,
        )
        is None
    )
    wait_until(lambda: fake.estimate_file_contents == [prepared.svg_text])
    multi = MultiLayerPlotService(service)
    assert (
        multi.start_job(
            document,
            layers,
            settings=settings,
            print_margins=margins,
            keep_inside=hole,
            clip_mode=_REMOVE,
        )
        is None
    )
    wait_until(
        lambda: multi.job.state is MultiLayerJobState.WAITING_FOR_PEN_CHANGE,
        timeout_ms=5000,
    )
    assert multi.continue_after_pen_change() is None
    wait_until(lambda: multi.job.state is MultiLayerJobState.COMPLETED, timeout_ms=5000)
    assert len(fake.plot_file_contents) == 3
    for layer, plotted in zip(layers, fake.plot_file_contents[1:], strict=True):
        layer_svg = prepare_layer_plot_svg(
            plot_svg_for_layer(document, layer),
            plot_settings=settings,
            transform=ArtworkTransform.identity(),
            print_margins=margins,
            keep_inside=hole,
            clip_mode=_REMOVE,
        )
        assert plotted == layer_svg.svg_text
