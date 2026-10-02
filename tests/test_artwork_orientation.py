"""Page orientation (Transform → Orientation): model, pipeline, preview parity, UI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtTest import QSignalSpy

from golden_oracle import parse_prepared_polylines, polyline_bbox
from plotpilot.geometry.plot_viewport import (
    PlotViewportError,
    clip_document_polylines,
    prepare_positioned_plot_svg,
)
from plotpilot.models.artwork_transform import (
    ArtworkOrientation,
    ArtworkTransform,
    ArtworkTransformError,
    orient_point,
    oriented_page_size,
    parse_artwork_orientation,
    resolve_rotation_degrees,
    transform_from_scale_percent,
)
from plotpilot.models.plot_settings import PlotSettings
from plotpilot.models.print_margins import PrintMargins, printable_area_for
from plotpilot.models.project_session import ProjectSession
from plotpilot.plotter.fake import FakePlotterBackend
from plotpilot.services.layer_geometry import position_and_clip_geometry, prepare_layer_geometry
from plotpilot.services.layer_service import layers_for_document
from plotpilot.services.positioned_plot_service import prepare_layer_plot_svg
from plotpilot.services.preview_work_area import FallbackWorkArea, PreviewWorkArea
from plotpilot.services.project_file_service import (
    ProjectFileError,
    read_project_file,
    write_project_file,
)
from plotpilot.services.svg_loader import load_svg_from_path
from plotpilot.ui.artwork_transform_controls import ArtworkTransformControls
from plotpilot.ui.main_window import MainWindow
from plotpilot.ui.preview_widget import LayerPreviewWidget
from plotpilot.ui.transform_slider_mapping import (
    ArtworkBoundsMm,
    axis_translation_limits,
    oriented_artwork_bounds,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"

# 100 × 50 mm landscape page with one diagonal stroke from (10, 10) to (90, 20).
LANDSCAPE_PAGE = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="50mm" viewBox="0 0 100 50">'
    '<path d="M 10 10 L 90 20" fill="none" stroke="black"/></svg>'
)
# 50 × 100 mm portrait page with the same stroke rotated into the page.
PORTRAIT_PAGE = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="50mm" height="100mm" viewBox="0 0 50 100">'
    '<path d="M 10 10 L 20 90" fill="none" stroke="black"/></svg>'
)
VIEWPORT = (300.0, 217.9)


def _prepared_points(svg: str, transform: ArtworkTransform) -> list[list[tuple[float, float]]]:
    prepared = prepare_positioned_plot_svg(
        svg,
        viewport_width_mm=VIEWPORT[0],
        viewport_height_mm=VIEWPORT[1],
        transform=transform,
    )
    return parse_prepared_polylines(prepared.svg_text)


def _assert_points(actual: list[list[tuple[float, float]]], expected: list[tuple[float, float]]):
    assert len(actual) == 1
    assert len(actual[0]) == len(expected)
    for (ax, ay), (ex, ey) in zip(actual[0], expected, strict=True):
        assert ax == pytest.approx(ex, abs=0.01)
        assert ay == pytest.approx(ey, abs=0.01)


# ------------------------------------------------------------------- model
def test_identity_preserves_orientation_and_equality_is_unchanged() -> None:
    assert ArtworkTransform.identity().orientation is ArtworkOrientation.PRESERVED
    assert ArtworkTransform(x_mm=1.0) == ArtworkTransform(x_mm=1.0)
    assert ArtworkTransform(orientation=ArtworkOrientation.ROTATE_90_CW) != ArtworkTransform()


def test_validate_rejects_non_enum_orientation() -> None:
    with pytest.raises(ArtworkTransformError):
        ArtworkTransform(orientation="cw").validate()  # type: ignore[arg-type]


def test_scale_percent_keeps_orientation() -> None:
    base = ArtworkTransform(x_mm=2.0, y_mm=3.0, scale=1.0, orientation=ArtworkOrientation.AUTO)
    scaled = transform_from_scale_percent(base, 150.0)
    assert scaled.orientation is ArtworkOrientation.AUTO
    assert (scaled.x_mm, scaled.y_mm, scaled.scale) == (2.0, 3.0, 1.5)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("preserved", ArtworkOrientation.PRESERVED),
        ("AUTO", ArtworkOrientation.AUTO),
        (" cw ", ArtworkOrientation.ROTATE_90_CW),
        ("ccw", ArtworkOrientation.ROTATE_90_CCW),
        ("sideways", None),
        (90, None),
        (None, None),
    ],
)
def test_parse_artwork_orientation(raw: object, expected: ArtworkOrientation | None) -> None:
    assert parse_artwork_orientation(raw) is expected


@pytest.mark.parametrize(
    ("orientation", "page", "printable", "expected"),
    [
        (ArtworkOrientation.PRESERVED, (50.0, 100.0), (280.0, 197.9), 0),
        (ArtworkOrientation.ROTATE_90_CW, (100.0, 50.0), (280.0, 197.9), 90),
        (ArtworkOrientation.ROTATE_90_CCW, (100.0, 50.0), (280.0, 197.9), 270),
        # AUTO: portrait page on landscape printable → CCW quarter turn (axicli default).
        (ArtworkOrientation.AUTO, (50.0, 100.0), (280.0, 197.9), 270),
        # AUTO: landscape page on portrait printable → also rotates.
        (ArtworkOrientation.AUTO, (100.0, 50.0), (190.0, 277.0), 270),
        # AUTO: same orientation → nothing to do.
        (ArtworkOrientation.AUTO, (100.0, 50.0), (280.0, 197.9), 0),
        (ArtworkOrientation.AUTO, (50.0, 100.0), (190.0, 277.0), 0),
        # AUTO: square page or square printable never rotates.
        (ArtworkOrientation.AUTO, (100.0, 100.0), (280.0, 197.9), 0),
        (ArtworkOrientation.AUTO, (50.0, 100.0), (200.0, 200.0), 0),
    ],
)
def test_resolve_rotation_degrees(
    orientation: ArtworkOrientation,
    page: tuple[float, float],
    printable: tuple[float, float],
    expected: int,
) -> None:
    assert (
        resolve_rotation_degrees(
            orientation,
            page_width_mm=page[0],
            page_height_mm=page[1],
            printable_width_mm=printable[0],
            printable_height_mm=printable[1],
        )
        == expected
    )


def test_orient_point_rotates_about_page_and_keeps_origin_corner() -> None:
    page = {"page_width_mm": 100.0, "page_height_mm": 50.0}
    assert orient_point(10.0, 10.0, 0, **page) == (10.0, 10.0)
    assert orient_point(10.0, 10.0, 90, **page) == (40.0, 10.0)
    assert orient_point(10.0, 10.0, 180, **page) == (90.0, 40.0)
    assert orient_point(10.0, 10.0, 270, **page) == (10.0, 90.0)
    # Every page corner lands inside the rotated page starting at (0, 0).
    for rotation in (90, 180, 270):
        w, h = oriented_page_size(100.0, 50.0, rotation)
        for cx, cy in ((0.0, 0.0), (100.0, 0.0), (0.0, 50.0), (100.0, 50.0)):
            ox, oy = orient_point(cx, cy, rotation, **page)
            assert 0.0 <= ox <= w and 0.0 <= oy <= h
    assert oriented_page_size(100.0, 50.0, 90) == (50.0, 100.0)
    assert oriented_page_size(100.0, 50.0, 180) == (100.0, 50.0)
    with pytest.raises(ArtworkTransformError):
        orient_point(0.0, 0.0, 45, **page)


def test_oriented_artwork_bounds_matches_corner_rotation() -> None:
    bounds = ArtworkBoundsMm(10.0, 90.0, 10.0, 40.0)
    cw = oriented_artwork_bounds(bounds, 90, page_width_mm=100.0, page_height_mm=50.0)
    assert cw == ArtworkBoundsMm(10.0, 40.0, 10.0, 90.0)
    ccw = oriented_artwork_bounds(bounds, 270, page_width_mm=100.0, page_height_mm=50.0)
    assert ccw == ArtworkBoundsMm(10.0, 40.0, 10.0, 90.0)
    assert oriented_artwork_bounds(bounds, 0, page_width_mm=1.0, page_height_mm=1.0) is bounds


# ---------------------------------------------------------------- pipeline
def test_preserved_output_is_unchanged() -> None:
    _assert_points(
        _prepared_points(LANDSCAPE_PAGE, ArtworkTransform.identity()),
        [(10.0, 10.0), (90.0, 20.0)],
    )


def test_rotate_cw_maps_page_about_its_height() -> None:
    points = _prepared_points(
        LANDSCAPE_PAGE,
        ArtworkTransform(orientation=ArtworkOrientation.ROTATE_90_CW),
    )
    _assert_points(points, [(40.0, 10.0), (30.0, 90.0)])


def test_rotate_ccw_maps_page_about_its_width() -> None:
    points = _prepared_points(
        LANDSCAPE_PAGE,
        ArtworkTransform(orientation=ArtworkOrientation.ROTATE_90_CCW),
    )
    _assert_points(points, [(10.0, 90.0), (20.0, 10.0)])


def test_rotation_is_applied_before_scale_and_translation() -> None:
    points = _prepared_points(
        LANDSCAPE_PAGE,
        ArtworkTransform(
            x_mm=5.0, y_mm=7.0, scale=2.0, orientation=ArtworkOrientation.ROTATE_90_CW
        ),
    )
    _assert_points(points, [(5.0 + 2 * 40.0, 7.0 + 2 * 10.0), (5.0 + 2 * 30.0, 7.0 + 2 * 90.0)])


def test_auto_rotates_portrait_page_on_landscape_viewport_only() -> None:
    auto = ArtworkTransform(orientation=ArtworkOrientation.AUTO)
    # Portrait page, landscape machine → 90° CCW: (x, y) → (y, W - x) with W = 50.
    _assert_points(_prepared_points(PORTRAIT_PAGE, auto), [(10.0, 40.0), (90.0, 30.0)])
    # Landscape page, landscape machine → untouched.
    _assert_points(_prepared_points(LANDSCAPE_PAGE, auto), [(10.0, 10.0), (90.0, 20.0)])


def test_auto_follows_the_printable_area_not_the_machine() -> None:
    # Landscape 300 × 217.9 machine, but heavy horizontal margins make the printable
    # rectangle portrait (40 × 197.9). A portrait page then stays as drawn; had it
    # been rotated CCW the stroke would run horizontally and be cut at x = 170.
    prepared = prepare_positioned_plot_svg(
        PORTRAIT_PAGE,
        viewport_width_mm=VIEWPORT[0],
        viewport_height_mm=VIEWPORT[1],
        transform=ArtworkTransform(x_mm=130.0, orientation=ArtworkOrientation.AUTO),
        clip_x_min_mm=130.0,
        clip_x_max_mm=170.0,
        clip_y_min_mm=10.0,
        clip_y_max_mm=207.9,
    )
    _assert_points(parse_prepared_polylines(prepared.svg_text), [(140.0, 10.0), (150.0, 90.0)])


def test_clip_document_polylines_requires_page_size_for_rotation() -> None:
    polylines = (((10.0, 10.0), (90.0, 20.0)),)
    preserved = clip_document_polylines(
        polylines,
        ArtworkTransform.identity(),
        viewport_width_mm=VIEWPORT[0],
        viewport_height_mm=VIEWPORT[1],
    )
    assert len(preserved) == 1
    with pytest.raises(PlotViewportError):
        clip_document_polylines(
            polylines,
            ArtworkTransform(orientation=ArtworkOrientation.ROTATE_90_CW),
            viewport_width_mm=VIEWPORT[0],
            viewport_height_mm=VIEWPORT[1],
        )
    rotated = clip_document_polylines(
        polylines,
        ArtworkTransform(orientation=ArtworkOrientation.ROTATE_90_CW),
        viewport_width_mm=VIEWPORT[0],
        viewport_height_mm=VIEWPORT[1],
        page_width_mm=100.0,
        page_height_mm=50.0,
    )
    assert rotated[0][0] == pytest.approx((40.0, 10.0))
    assert rotated[0][-1] == pytest.approx((30.0, 90.0))


@pytest.mark.parametrize(
    "orientation",
    [
        ArtworkOrientation.ROTATE_90_CW,
        ArtworkOrientation.ROTATE_90_CCW,
        ArtworkOrientation.AUTO,
    ],
)
def test_interactive_preview_matches_plot_output(orientation: ArtworkOrientation) -> None:
    """The cached-geometry preview path and the plot path agree point for point."""
    document = load_svg_from_path(FIXTURES / "square_100mm_path.svg")
    layer = layers_for_document(document)[0]
    settings = PlotSettings(model=1)
    transform = ArtworkTransform(x_mm=12.0, y_mm=-3.0, scale=1.5, orientation=orientation)
    margins = PrintMargins(10.0, 10.0)

    geometry = prepare_layer_geometry(document, layer)
    assert geometry.preparation_error is None
    preview = position_and_clip_geometry(
        geometry,
        transform,
        viewport_width_mm=VIEWPORT[0],
        viewport_height_mm=VIEWPORT[1],
        print_margins=margins,
    )
    assert preview.error_message is None

    plot = prepare_layer_plot_svg(
        geometry.context_svg_text,
        plot_settings=settings,
        transform=transform,
        print_margins=margins,
    )
    plot_points = parse_prepared_polylines(plot.svg_text)
    assert len(plot_points) == len(preview.polylines) > 0
    for plotted, previewed in zip(plot_points, preview.polylines, strict=True):
        assert len(plotted) == len(previewed)
        for (px, py), (vx, vy) in zip(plotted, previewed, strict=True):
            assert px == pytest.approx(vx, abs=0.001)
            assert py == pytest.approx(vy, abs=0.001)


def test_rotated_square_bbox_is_the_rotated_stroke() -> None:
    document = load_svg_from_path(FIXTURES / "square_100mm_path.svg")
    layer = layers_for_document(document)[0]
    geometry = prepare_layer_geometry(document, layer)
    clipped = position_and_clip_geometry(
        geometry,
        ArtworkTransform(orientation=ArtworkOrientation.ROTATE_90_CW),
        viewport_width_mm=VIEWPORT[0],
        viewport_height_mm=VIEWPORT[1],
        print_margins=PrintMargins(0.0, 0.0),
    )
    # Square 10..90 on a 100 mm page stays 10..90 after a quarter turn.
    assert polyline_bbox([list(p) for p in clipped.polylines]) == pytest.approx(
        (10.0, 10.0, 90.0, 90.0),
        abs=0.01,
    )


# ------------------------------------------------------------ project file
def test_project_round_trip_keeps_orientation(tmp_path: Path) -> None:
    session = ProjectSession(
        svg_path=(FIXTURES / "simple.svg").resolve(),
        checked_layer_ids=(),
        artwork_transform=ArtworkTransform(
            x_mm=1.0, y_mm=2.0, scale=1.0, orientation=ArtworkOrientation.AUTO
        ),
        plot_settings=PlotSettings(),
        fallback_work_area=FallbackWorkArea.A4,
    )
    project = tmp_path / "o.plotpilot"
    write_project_file(project, session)
    data = json.loads(project.read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert data["artwork_transform"]["orientation"] == "auto"
    assert read_project_file(project) == session


def test_project_without_orientation_key_is_preserved(tmp_path: Path) -> None:
    project = tmp_path / "legacy.plotpilot"
    project.write_text(
        json.dumps(
            {
                "format": "plotpilot-project",
                "version": 1,
                "svg": {"path": str((FIXTURES / "simple.svg").resolve())},
                "artwork_transform": {"x_mm": 0.0, "y_mm": 0.0, "scale": 1.0},
            }
        ),
        encoding="utf-8",
    )
    assert read_project_file(project).artwork_transform.orientation is (
        ArtworkOrientation.PRESERVED
    )


def test_project_with_unknown_orientation_is_rejected(tmp_path: Path) -> None:
    project = tmp_path / "bad.plotpilot"
    project.write_text(
        json.dumps(
            {
                "format": "plotpilot-project",
                "version": 1,
                "svg": {"path": str((FIXTURES / "simple.svg").resolve())},
                "artwork_transform": {"x_mm": 0.0, "y_mm": 0.0, "scale": 1.0, "orientation": "45"},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ProjectFileError):
        read_project_file(project)


# ---------------------------------------------------------------- controls
@pytest.fixture
def controls(qapp) -> ArtworkTransformControls:
    widget = ArtworkTransformControls()
    widget.set_work_area_dimensions(300.0, 217.9)
    widget.set_page_dimensions(100.0, 50.0)
    widget.set_artwork_bounds(ArtworkBoundsMm(10.0, 90.0, 10.0, 40.0))
    widget.show()
    return widget


def test_all_orientation_radios_are_enabled(controls: ArtworkTransformControls) -> None:
    buttons = controls._orientation_buttons
    assert set(buttons) == set(ArtworkOrientation)
    assert all(button.isEnabled() for button in buttons.values())
    assert buttons[ArtworkOrientation.PRESERVED].isChecked()


def test_orientation_radio_emits_transform_and_keeps_other_fields(
    controls: ArtworkTransformControls,
) -> None:
    controls.set_transform(ArtworkTransform(x_mm=5.0, y_mm=-3.0, scale=1.5))
    spy = QSignalSpy(controls.transform_changed)
    controls._orientation_buttons[ArtworkOrientation.ROTATE_90_CW].click()
    assert spy.count() == 1
    emitted = spy.at(0)[0]
    assert emitted == ArtworkTransform(
        x_mm=5.0, y_mm=-3.0, scale=1.5, orientation=ArtworkOrientation.ROTATE_90_CW
    )
    assert controls.orientation is ArtworkOrientation.ROTATE_90_CW
    assert controls.effective_rotation_degrees() == 90


def test_set_transform_syncs_radio_without_emitting(controls: ArtworkTransformControls) -> None:
    spy = QSignalSpy(controls.transform_changed)
    controls.set_transform(ArtworkTransform(orientation=ArtworkOrientation.ROTATE_90_CCW))
    assert spy.count() == 0
    assert controls._orientation_buttons[ArtworkOrientation.ROTATE_90_CCW].isChecked()
    assert not controls._orientation_buttons[ArtworkOrientation.PRESERVED].isChecked()
    assert "90° CCW" in controls._orientation_note.text()


def test_scale_and_position_edits_keep_orientation(controls: ArtworkTransformControls) -> None:
    controls.set_transform(ArtworkTransform(orientation=ArtworkOrientation.AUTO))
    spy = QSignalSpy(controls.transform_changed)
    controls._scale_spin.setValue(200.0)
    controls._x_spin.setValue(4.0)
    controls._preset_buttons[50.0].click()
    controls._reset_x.click()
    for index in range(spy.count()):
        assert spy.at(index)[0].orientation is ArtworkOrientation.AUTO


def test_reset_all_returns_to_preserved(controls: ArtworkTransformControls) -> None:
    controls.set_transform(ArtworkTransform(x_mm=3.0, orientation=ArtworkOrientation.ROTATE_90_CW))
    spy = QSignalSpy(controls.transform_changed)
    controls._reset_all.click()
    assert spy.at(spy.count() - 1)[0] == ArtworkTransform.identity()
    assert controls._orientation_buttons[ArtworkOrientation.PRESERVED].isChecked()


def test_slider_limits_follow_oriented_bounds(controls: ArtworkTransformControls) -> None:
    area = printable_area_for(300.0, 217.9, controls.print_margins())
    controls.set_transform(ArtworkTransform(orientation=ArtworkOrientation.ROTATE_90_CW))
    rotated = oriented_artwork_bounds(
        ArtworkBoundsMm(10.0, 90.0, 10.0, 40.0),
        90,
        page_width_mm=100.0,
        page_height_mm=50.0,
    )
    assert controls.x_translation_limits() == pytest.approx(
        axis_translation_limits(
            artwork_min_mm=rotated.min_x_mm,
            artwork_max_mm=rotated.max_x_mm,
            scale=1.0,
            printable_min_mm=area.x_mm,
            printable_max_mm=area.x_max_mm,
        ),
    )
    assert controls.y_translation_limits() == pytest.approx(
        axis_translation_limits(
            artwork_min_mm=rotated.min_y_mm,
            artwork_max_mm=rotated.max_y_mm,
            scale=1.0,
            printable_min_mm=area.y_mm,
            printable_max_mm=area.y_max_mm,
        ),
    )
    controls.set_transform(ArtworkTransform.identity())
    assert controls.x_translation_limits() == pytest.approx(
        axis_translation_limits(
            artwork_min_mm=10.0,
            artwork_max_mm=90.0,
            scale=1.0,
            printable_min_mm=area.x_mm,
            printable_max_mm=area.x_max_mm,
        ),
    )


def test_auto_note_tracks_page_and_work_area(controls: ArtworkTransformControls) -> None:
    controls.set_transform(ArtworkTransform(orientation=ArtworkOrientation.AUTO))
    # Landscape page on the landscape AxiDraw area → nothing to rotate.
    assert controls.effective_rotation_degrees() == 0
    assert "no rotation" in controls._orientation_note.text()
    controls.set_page_dimensions(50.0, 100.0)
    assert controls.effective_rotation_degrees() == 270
    assert "90° CCW" in controls._orientation_note.text()
    controls.set_work_area_dimensions(210.0, 297.0)
    assert controls.effective_rotation_degrees() == 0


def test_rotation_without_page_size_is_a_noop(qapp) -> None:
    widget = ArtworkTransformControls()
    widget.set_transform(ArtworkTransform(orientation=ArtworkOrientation.ROTATE_90_CW))
    assert widget.effective_rotation_degrees() == 0
    assert "page size" in widget._orientation_note.text()


# ---------------------------------------------------------- preview widget
def _work_area() -> PreviewWorkArea:
    return PreviewWorkArea(width_mm=300.0, height_mm=217.9, label="A", from_fallback=False)


def test_preview_layout_uses_rotated_page_footprint(qapp) -> None:
    widget = LayerPreviewWidget()
    widget.resize(600, 400)
    widget.set_work_area_overlay(svg_width_mm=100.0, svg_height_mm=400.0, work_area=_work_area())
    layout = widget.physical_layout
    assert layout is not None
    assert (layout.svg_rect_mm.width_mm, layout.svg_rect_mm.height_mm) == (100.0, 400.0)
    assert widget.effective_rotation_degrees == 0

    widget.set_artwork_transform(ArtworkTransform(orientation=ArtworkOrientation.ROTATE_90_CW))
    layout = widget.physical_layout
    assert layout is not None
    assert widget.effective_rotation_degrees == 90
    assert (layout.svg_rect_mm.width_mm, layout.svg_rect_mm.height_mm) == (400.0, 100.0)

    widget.set_artwork_transform(ArtworkTransform(orientation=ArtworkOrientation.AUTO))
    assert widget.effective_rotation_degrees == 270
    widget.set_work_area_overlay(svg_width_mm=400.0, svg_height_mm=100.0, work_area=_work_area())
    assert widget.effective_rotation_degrees == 0


def test_preview_drag_preserves_orientation(qapp) -> None:
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    widget = LayerPreviewWidget()
    widget.resize(600, 400)
    widget.show()
    qapp.processEvents()
    assert widget.set_preview_svg(LANDSCAPE_PAGE)
    widget.set_work_area_overlay(svg_width_mm=100.0, svg_height_mm=50.0, work_area=_work_area())
    widget.set_artwork_transform(ArtworkTransform(orientation=ArtworkOrientation.ROTATE_90_CCW))
    widget.mousePressEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(300.0, 200.0),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    widget.mouseMoveEvent(
        QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(340.0, 200.0),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    assert widget.artwork_transform.orientation is ArtworkOrientation.ROTATE_90_CCW
    assert widget.artwork_transform.x_mm > 0.0


def test_preview_paints_rotated_ghost_without_error(qapp) -> None:
    widget = LayerPreviewWidget()
    widget.resize(600, 400)
    widget.show()
    qapp.processEvents()
    assert widget.set_preview_svg(LANDSCAPE_PAGE)
    widget.set_work_area_overlay(svg_width_mm=100.0, svg_height_mm=50.0, work_area=_work_area())
    widget.set_context_polylines((((10.0, 10.0), (90.0, 20.0)),))
    for orientation in ArtworkOrientation:
        widget.set_artwork_transform(ArtworkTransform(orientation=orientation))
        widget.repaint()
        qapp.processEvents()
    widget.close()


# ------------------------------------------------------------ main window
def _wait_preview(window: MainWindow, qapp) -> None:
    from PySide6.QtCore import QThreadPool

    window._preview_prep_timer.stop()
    assert QThreadPool.globalInstance().waitForDone(5000)
    qapp.processEvents()
    window._refresh_prepared_preview()
    assert QThreadPool.globalInstance().waitForDone(5000)
    qapp.processEvents()


def test_main_window_orientation_radio_drives_preview_and_plot_geometry(qapp) -> None:
    window = MainWindow(plotter_backend=FakePlotterBackend(), svg_file_chooser=lambda: None)
    window._settings_service.replace(PlotSettings(model=1))
    window.set_document(load_svg_from_path(FIXTURES / "square_100mm_path.svg"))
    _wait_preview(window, qapp)
    assert window._artwork_controls._page_width_mm == pytest.approx(100.0)
    before = window._preview.clipped_polylines
    assert before

    window._artwork_controls._orientation_buttons[ArtworkOrientation.ROTATE_90_CW].click()
    assert window._preview.artwork_transform.orientation is ArtworkOrientation.ROTATE_90_CW
    assert window.project_dirty is True
    _wait_preview(window, qapp)
    after = window._preview.clipped_polylines
    assert after

    # The square 10..90 is symmetric, so the bbox is unchanged but the vertex
    # order is rotated: first vertex (10, 10) → (100 - 10, 10) = (90, 10).
    assert polyline_bbox([list(p) for p in after]) == pytest.approx(
        polyline_bbox([list(p) for p in before]),
        abs=0.01,
    )
    assert after[0][0] == pytest.approx((90.0, 10.0), abs=0.01)

    # What the preview shows is what the plot service would prepare.
    layer = window._current_layer()
    assert layer is not None
    geometry = window._geometry_cache.lookup(id(window.document), layer.layer_id)
    assert geometry is not None
    plot = prepare_layer_plot_svg(
        geometry.context_svg_text,
        plot_settings=window._settings_service.plot_settings,
        transform=window._preview.artwork_transform,
        print_margins=window._settings_service.print_margins,
    )
    plot_points = parse_prepared_polylines(plot.svg_text)
    assert len(plot_points) == len(after)
    for plotted, shown in zip(plot_points, after, strict=True):
        for (px, py), (sx, sy) in zip(plotted, shown, strict=True):
            assert (px, py) == pytest.approx((sx, sy), abs=0.001)
    window.close()


def test_main_window_project_round_trip_restores_orientation(qapp, tmp_path: Path) -> None:
    project = tmp_path / "rot.plotpilot"
    session = ProjectSession(
        svg_path=(FIXTURES / "square_100mm_path.svg").resolve(),
        checked_layer_ids=(),
        artwork_transform=ArtworkTransform(
            x_mm=5.0, y_mm=-2.0, scale=2.0, orientation=ArtworkOrientation.ROTATE_90_CCW
        ),
        plot_settings=PlotSettings(model=1),
        fallback_work_area=FallbackWorkArea.A4,
    )
    write_project_file(project, session)
    window = MainWindow(
        plotter_backend=FakePlotterBackend(),
        svg_file_chooser=lambda: None,
        project_file_chooser=lambda: str(project),
        save_project_file_chooser=lambda: None,
    )
    window._open_project_action.trigger()
    assert window.document is not None
    assert window._preview.artwork_transform.orientation is ArtworkOrientation.ROTATE_90_CCW
    assert window._artwork_controls._orientation_buttons[
        ArtworkOrientation.ROTATE_90_CCW
    ].isChecked()
    assert window.project_dirty is False
    _wait_preview(window, qapp)
    # Saving writes the orientation back.
    window._save_project_action.trigger()
    assert read_project_file(project).artwork_transform.orientation is (
        ArtworkOrientation.ROTATE_90_CCW
    )
    window.close()


def test_main_window_bounds_status_follows_orientation(qapp) -> None:
    portrait_a4 = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="297mm" '
        'viewBox="0 0 210 297"><path d="M 10 10 L 200 287" fill="none" stroke="black"/></svg>'
    )
    from xml.etree import ElementTree as ET

    from plotpilot.models.plot_bounds import BoundsStatus
    from plotpilot.models.svg_document import SvgDocument

    window = MainWindow(plotter_backend=FakePlotterBackend(), svg_file_chooser=lambda: None)
    window._settings_service.replace(PlotSettings(model=1))
    window.set_document(
        SvgDocument(
            path=FIXTURES / "virtual_a4.svg",
            name="a4",
            raw_text=portrait_a4,
            root=ET.fromstring(portrait_a4),
        )
    )
    assert window._bounds_check is not None
    assert window._bounds_check.status is BoundsStatus.OUT_OF_BOUNDS
    assert window._bounds_check.would_fit_if_rotated

    window._artwork_controls._orientation_buttons[ArtworkOrientation.AUTO].click()
    assert window._bounds_check is not None
    assert window._bounds_check.status is BoundsStatus.OK
    assert "rotated: 297 × 210 mm" in window._bounds_check.message

    window._artwork_controls._orientation_buttons[ArtworkOrientation.PRESERVED].click()
    assert window._bounds_check.status is BoundsStatus.OUT_OF_BOUNDS
    window.close()
