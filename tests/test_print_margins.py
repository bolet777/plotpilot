"""Print margins, printable area, clipping, preview, and persistence."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from golden_oracle import parse_prepared_polylines
from plotpilot.geometry.plot_viewport import (
    PlotViewportError,
    _validate_output_geometry,
    prepare_positioned_plot_svg,
)
from plotpilot.models.artwork_transform import ArtworkTransform
from plotpilot.models.plot_settings import PlotSettings
from plotpilot.models.plotter_model import get_plotter_model_info
from plotpilot.models.print_margins import (
    MIN_PRINTABLE_MM,
    PrintMargins,
    PrintMarginsError,
    max_symmetric_margin_mm,
    printable_area_for,
)
from plotpilot.models.project_session import ProjectSession
from plotpilot.plotter.fake import FakePlotterBackend
from plotpilot.services.positioned_plot_service import prepare_layer_plot_svg
from plotpilot.services.preview_work_area import (
    FallbackWorkArea,
    PreviewWorkArea,
    WorkAreaOrientation,
    resolve_fallback_work_area_dimensions,
    resolve_preview_work_area,
)
from plotpilot.services.project_file_service import (
    FORMAT_ID,
    ProjectFileError,
    read_project_file,
    write_project_file,
)
from plotpilot.services.settings_service import SettingsService, open_settings_store
from plotpilot.services.svg_loader import load_svg_from_path
from plotpilot.ui.main_window import MainWindow
from plotpilot.ui.preview_widget import LayerPreviewWidget

FIXTURES = Path(__file__).resolve().parent / "fixtures"
_TOLERANCE_MM = 0.01

_FULL_BLEED = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="300mm" height="217.9mm" viewBox="0 0 300 217.9">
  <line x1="0" y1="100" x2="300" y2="100" stroke="black"/>
</svg>"""


def _points(svg_text: str) -> list[tuple[float, float]]:
    return [point for polyline in parse_prepared_polylines(svg_text) for point in polyline]


def _assert_inside(
    points: list[tuple[float, float]],
    x_min: float,
    y_min: float,
    x_max: float,
    y_max: float,
) -> None:
    assert points
    for x, y in points:
        assert x_min - _TOLERANCE_MM <= x <= x_max + _TOLERANCE_MM
        assert y_min - _TOLERANCE_MM <= y <= y_max + _TOLERANCE_MM


def _prepare_box(
    svg: str,
    *,
    width: float,
    height: float,
    margins: PrintMargins | None = None,
    transform: ArtworkTransform | None = None,
) -> str:
    margins = PrintMargins() if margins is None else margins
    area = printable_area_for(width, height, margins)
    prepared = prepare_positioned_plot_svg(
        svg,
        viewport_width_mm=width,
        viewport_height_mm=height,
        transform=transform or ArtworkTransform.identity(),
        clip_x_min_mm=area.x_mm,
        clip_y_min_mm=area.y_mm,
        clip_x_max_mm=area.x_max_mm,
        clip_y_max_mm=area.y_max_mm,
    )
    assert prepared.width_mm == pytest.approx(width)
    assert prepared.height_mm == pytest.approx(height)
    return prepared.svg_text


def test_default_margins_are_ten_millimetres() -> None:
    margins = PrintMargins()
    assert margins.horizontal_mm == pytest.approx(10.0)
    assert margins.vertical_mm == pytest.approx(10.0)
    margins.validate()


def test_zero_margins_cover_the_work_area() -> None:
    margins = PrintMargins(horizontal_mm=0.0, vertical_mm=0.0)
    margins.validate()
    area = printable_area_for(300.0, 217.9, margins)
    assert (area.x_mm, area.y_mm, area.width_mm, area.height_mm) == pytest.approx(
        (0.0, 0.0, 300.0, 217.9)
    )


def test_negative_margins_are_rejected() -> None:
    with pytest.raises(PrintMarginsError, match="cannot be negative"):
        PrintMargins(horizontal_mm=-1.0, vertical_mm=10.0).validate()
    with pytest.raises(PrintMarginsError, match="cannot be negative"):
        PrintMargins(horizontal_mm=10.0, vertical_mm=-0.1).validate()


def test_non_finite_margins_are_rejected() -> None:
    with pytest.raises(PrintMarginsError, match="finite"):
        PrintMargins(horizontal_mm=float("nan"), vertical_mm=10.0).validate()


def test_impossible_margins_are_rejected() -> None:
    margins = PrintMargins(horizontal_mm=110.0, vertical_mm=10.0)
    with pytest.raises(PrintMarginsError, match="no printable width"):
        margins.validate_for_work_area(210.0, 297.0)
    with pytest.raises(PrintMarginsError, match="no printable height"):
        PrintMargins(horizontal_mm=10.0, vertical_mm=150.0).validate_for_work_area(210.0, 297.0)


def test_margin_limit_leaves_a_positive_printable_span() -> None:
    limit = max_symmetric_margin_mm(210.0)
    assert limit < 210.0 / 2.0
    area = printable_area_for(210.0, 297.0, PrintMargins(horizontal_mm=limit, vertical_mm=10.0))
    assert area.width_mm >= MIN_PRINTABLE_MM


def test_printable_area_for_300_by_217_9() -> None:
    area = printable_area_for(300.0, 217.9, PrintMargins())
    assert area.x_mm == pytest.approx(10.0)
    assert area.y_mm == pytest.approx(10.0)
    assert area.width_mm == pytest.approx(280.0)
    assert area.height_mm == pytest.approx(197.9)
    assert area.x_max_mm == pytest.approx(290.0)
    assert area.y_max_mm == pytest.approx(207.9)


@pytest.mark.parametrize(
    ("size", "orientation"),
    [
        (FallbackWorkArea.A4, WorkAreaOrientation.PORTRAIT),
        (FallbackWorkArea.A4, WorkAreaOrientation.LANDSCAPE),
        (FallbackWorkArea.A3, WorkAreaOrientation.PORTRAIT),
        (FallbackWorkArea.A3, WorkAreaOrientation.LANDSCAPE),
    ],
)
def test_printable_area_follows_paper_orientation(
    size: FallbackWorkArea,
    orientation: WorkAreaOrientation,
) -> None:
    width, height = resolve_fallback_work_area_dimensions(size, orientation)
    area = printable_area_for(width, height, PrintMargins())
    assert area.x_mm == pytest.approx(10.0)
    assert area.y_mm == pytest.approx(10.0)
    assert area.width_mm == pytest.approx(width - 20.0)
    assert area.height_mm == pytest.approx(height - 20.0)


def test_a4_landscape_edges_are_10_to_287_and_10_to_200() -> None:
    width, height = resolve_fallback_work_area_dimensions(
        FallbackWorkArea.A4,
        WorkAreaOrientation.LANDSCAPE,
    )
    area = printable_area_for(width, height, PrintMargins())
    assert (area.x_mm, area.x_max_mm) == pytest.approx((10.0, 287.0))
    assert (area.y_mm, area.y_max_mm) == pytest.approx((10.0, 200.0))


def test_explicit_axidraw_model_uses_the_same_inset() -> None:
    info = get_plotter_model_info(1)
    area = printable_area_for(info.max_width_mm, info.max_height_mm, PrintMargins())
    assert area.x_mm == pytest.approx(10.0)
    assert area.y_mm == pytest.approx(10.0)
    assert area.width_mm == pytest.approx(info.max_width_mm - 20.0)
    assert area.height_mm == pytest.approx(info.max_height_mm - 20.0)
    preview = resolve_preview_work_area(PlotSettings(model=1))
    assert preview is not None
    assert preview.width_mm == pytest.approx(info.max_width_mm)


def test_horizontal_line_is_clipped_to_10_290() -> None:
    svg_text = _prepare_box(_FULL_BLEED, width=300.0, height=217.9)
    points = _points(svg_text)
    xs = [point[0] for point in points]
    assert min(xs) == pytest.approx(10.0, abs=_TOLERANCE_MM)
    assert max(xs) == pytest.approx(290.0, abs=_TOLERANCE_MM)
    _assert_inside(points, 10.0, 10.0, 290.0, 207.9)


def test_vertical_line_is_clipped_to_the_vertical_margin() -> None:
    svg = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="300mm" height="217.9mm" viewBox="0 0 300 217.9">
  <line x1="40" y1="0" x2="40" y2="217.9" stroke="black"/>
</svg>"""
    points = _points(_prepare_box(svg, width=300.0, height=217.9))
    ys = [point[1] for point in points]
    assert min(ys) == pytest.approx(10.0, abs=_TOLERANCE_MM)
    assert max(ys) == pytest.approx(207.9, abs=_TOLERANCE_MM)
    _assert_inside(points, 10.0, 10.0, 290.0, 207.9)


def test_polyline_that_exits_and_reenters_is_split_at_the_margin() -> None:
    svg = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="300mm" height="100mm" viewBox="0 0 300 100">
  <path d="M 40 50 L 0 50 L 0 80 L 40 80" fill="none" stroke="black"/>
</svg>"""
    prepared = prepare_positioned_plot_svg(
        svg,
        viewport_width_mm=300.0,
        viewport_height_mm=100.0,
        transform=ArtworkTransform.identity(),
        clip_x_min_mm=10.0,
        clip_y_min_mm=10.0,
        clip_x_max_mm=290.0,
        clip_y_max_mm=90.0,
    )
    polylines = parse_prepared_polylines(prepared.svg_text)
    assert len(polylines) == 2
    points = [point for polyline in polylines for point in polyline]
    _assert_inside(points, 10.0, 10.0, 290.0, 90.0)
    assert min(point[0] for point in points) == pytest.approx(10.0, abs=_TOLERANCE_MM)


def test_curve_crossing_the_margin_stays_inside() -> None:
    svg = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="300mm" height="200mm" viewBox="0 0 300 200">
  <path d="M 40 80 C -40 80 -40 140 80 140" fill="none" stroke="black"/>
</svg>"""
    points = _points(
        _prepare_box(svg, width=300.0, height=200.0),
    )
    _assert_inside(points, 10.0, 10.0, 290.0, 190.0)
    assert min(point[0] for point in points) == pytest.approx(10.0, abs=0.05)


def test_scaled_artwork_is_clipped_without_autofit() -> None:
    svg = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="160mm" height="20mm" viewBox="0 0 160 20">
  <line x1="0" y1="10" x2="160" y2="10" stroke="black"/>
</svg>"""
    points = _points(
        _prepare_box(
            svg,
            width=300.0,
            height=217.9,
            transform=ArtworkTransform(x_mm=0.0, y_mm=0.0, scale=2.0),
        )
    )
    xs = [point[0] for point in points]
    assert min(xs) == pytest.approx(10.0, abs=_TOLERANCE_MM)
    assert max(xs) == pytest.approx(290.0, abs=_TOLERANCE_MM)


def test_translated_artwork_is_clipped_in_machine_space() -> None:
    svg = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="20mm" viewBox="0 0 100 20">
  <line x1="0" y1="10" x2="100" y2="10" stroke="black"/>
</svg>"""
    points = _points(
        _prepare_box(
            svg,
            width=300.0,
            height=100.0,
            transform=ArtworkTransform(x_mm=-30.0, y_mm=0.0, scale=1.0),
        )
    )
    xs = [point[0] for point in points]
    assert min(xs) == pytest.approx(10.0, abs=_TOLERANCE_MM)
    assert max(xs) == pytest.approx(70.0, abs=_TOLERANCE_MM)


def test_validator_rejects_a_point_inside_the_margin() -> None:
    leaked = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="300mm" height="200mm">
  <path d="M 5 40 L 20 40"/>
</svg>"""
    with pytest.raises(PlotViewportError, match="printable area"):
        _validate_output_geometry(
            leaked,
            300.0,
            200.0,
            x_min_mm=10.0,
            y_min_mm=10.0,
            x_max_mm=290.0,
            y_max_mm=190.0,
        )


def test_product_path_uses_default_margins_on_a4_landscape() -> None:
    svg = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="297mm" height="210mm" viewBox="0 0 297 210">
  <line x1="0" y1="100" x2="297" y2="100" stroke="black"/>
</svg>"""
    prepared = prepare_layer_plot_svg(
        svg,
        plot_settings=PlotSettings(),
        transform=ArtworkTransform.identity(),
        fallback=FallbackWorkArea.A4,
        fallback_orientation=WorkAreaOrientation.LANDSCAPE,
    )
    points = _points(prepared.svg_text)
    xs = [point[0] for point in points]
    assert min(xs) == pytest.approx(10.0, abs=_TOLERANCE_MM)
    assert max(xs) == pytest.approx(287.0, abs=_TOLERANCE_MM)
    assert prepared.width_mm == pytest.approx(297.0)


def test_zero_margins_on_the_product_path_keep_the_machine_edge() -> None:
    svg = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="297mm" height="210mm" viewBox="0 0 297 210">
  <line x1="0" y1="100" x2="297" y2="100" stroke="black"/>
</svg>"""
    prepared = prepare_layer_plot_svg(
        svg,
        plot_settings=PlotSettings(),
        transform=ArtworkTransform.identity(),
        fallback=FallbackWorkArea.A4,
        fallback_orientation=WorkAreaOrientation.LANDSCAPE,
        print_margins=PrintMargins(0.0, 0.0),
    )
    xs = [point[0] for point in _points(prepared.svg_text)]
    assert min(xs) == pytest.approx(0.0, abs=_TOLERANCE_MM)
    assert max(xs) == pytest.approx(297.0, abs=_TOLERANCE_MM)


def test_preview_shows_inner_boundary_and_clipped_strokes(qapp: QApplication) -> None:
    widget = LayerPreviewWidget()
    widget.resize(480, 360)
    source = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="300mm" height="100mm" viewBox="0 0 300 100">
  <line x1="0" y1="50" x2="300" y2="50" stroke="black"/>
</svg>"""
    assert widget.set_preview_svg(source)
    work = PreviewWorkArea(
        width_mm=300.0,
        height_mm=217.9,
        label="Test — 300 × 217.9 mm",
        from_fallback=False,
    )
    printable = printable_area_for(300.0, 217.9, PrintMargins())
    widget.set_work_area_overlay(
        svg_width_mm=300.0,
        svg_height_mm=100.0,
        work_area=work,
        printable_area=printable,
    )
    prepared = _prepare_box(source, width=300.0, height=217.9)
    polylines = tuple(tuple(points) for points in parse_prepared_polylines(prepared))
    widget.set_clipped_plot(polylines=polylines, error_message=None)
    _assert_inside(
        [point for line in widget.clipped_polylines for point in line],
        10.0,
        10.0,
        290.0,
        207.9,
    )
    image = QImage(widget.size(), QImage.Format.Format_ARGB32_Premultiplied)
    widget.render(image)
    assert widget.painted_printable_boundary is True
    assert widget.printable_area == printable


@pytest.fixture
def margin_window(qapp: QApplication) -> MainWindow:
    org = f"PlotPilotMargins-{uuid.uuid4().hex}"
    app_name = "Margins"
    open_settings_store(org, app_name).clear()
    window = MainWindow(
        plotter_backend=FakePlotterBackend(),
        settings_service=SettingsService(organization=org, application=app_name),
        svg_file_chooser=lambda: None,
        project_file_chooser=lambda: None,
        save_project_file_chooser=lambda: None,
    )
    yield window
    window.close()
    qapp.processEvents()
    open_settings_store(org, app_name).clear()


def test_margin_controls_default_and_accept_zero(margin_window: MainWindow) -> None:
    controls = margin_window._artwork_controls
    assert controls.print_margins() == PrintMargins()
    assert controls._margin_horizontal.decimals() == 1
    assert controls._margin_horizontal.singleStep() == pytest.approx(1.0)
    controls._margin_horizontal.setValue(0.0)
    controls._margin_vertical.setValue(0.0)
    assert controls.print_margins() == PrintMargins(0.0, 0.0)
    assert "Printable:" in controls._printable_label.text()


def test_qsettings_round_trip_and_invalid_recovery(qapp: QApplication) -> None:
    org = f"PlotPilotMarginsStore-{uuid.uuid4().hex}"
    app_name = "Store"
    service = SettingsService(organization=org, application=app_name)
    service.set_print_margins(PrintMargins(horizontal_mm=4.5, vertical_mm=6.0))
    reloaded = SettingsService(organization=org, application=app_name)
    assert reloaded.print_margins == PrintMargins(horizontal_mm=4.5, vertical_mm=6.0)

    store = open_settings_store(org, app_name)
    store.setValue("print/margin_horizontal_mm", -3)
    store.sync()
    recovered = SettingsService(organization=org, application=app_name)
    assert recovered.print_margins == PrintMargins()
    open_settings_store(org, app_name).clear()


def test_project_session_does_not_overwrite_global_defaults(qapp: QApplication) -> None:
    org = f"PlotPilotMarginsGlobal-{uuid.uuid4().hex}"
    app_name = "Global"
    service = SettingsService(organization=org, application=app_name)
    service.set_print_margins(PrintMargins(3.0, 4.0))
    service.begin_project_session(
        PlotSettings(),
        FallbackWorkArea.A4,
        print_margins=PrintMargins(8.0, 9.0),
    )
    service.set_print_margins(PrintMargins(1.0, 2.0))
    assert service.print_margins == PrintMargins(1.0, 2.0)
    service.end_project_session()
    assert service.print_margins == PrintMargins(3.0, 4.0)
    open_settings_store(org, app_name).clear()


def test_project_round_trip_and_legacy_default(tmp_path: Path) -> None:
    svg = FIXTURES / "simple.svg"
    project = tmp_path / "job.plotpilot"
    session = ProjectSession(
        svg_path=svg.resolve(),
        checked_layer_ids=(),
        artwork_transform=ArtworkTransform.identity(),
        plot_settings=PlotSettings(),
        fallback_work_area=FallbackWorkArea.A4,
        print_margins=PrintMargins(horizontal_mm=4.0, vertical_mm=6.5),
    )
    write_project_file(project, session)
    payload = json.loads(project.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert payload["print"]["margin_horizontal_mm"] == pytest.approx(4.0)
    assert payload["print"]["margin_vertical_mm"] == pytest.approx(6.5)
    loaded = read_project_file(project)
    assert loaded.print_margins == session.print_margins

    legacy = tmp_path / "legacy.plotpilot"
    legacy.write_text(
        json.dumps(
            {
                "format": FORMAT_ID,
                "version": 1,
                "svg": {"path": str(svg)},
            }
        ),
        encoding="utf-8",
    )
    assert read_project_file(legacy).print_margins == PrintMargins()


def test_invalid_project_margins_are_rejected(tmp_path: Path) -> None:
    svg = FIXTURES / "simple.svg"
    project = tmp_path / "bad.plotpilot"
    project.write_text(
        json.dumps(
            {
                "format": FORMAT_ID,
                "version": 1,
                "svg": {"path": str(svg)},
                "preview": {
                    "fallback_work_area": "A4",
                    "fallback_work_area_orientation": "Portrait",
                },
                "print": {"margin_horizontal_mm": 110, "margin_vertical_mm": 10},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ProjectFileError, match="no printable width"):
        read_project_file(project)


def test_margin_change_marks_project_dirty_and_restore_updates_ui(
    margin_window: MainWindow,
    tmp_path: Path,
) -> None:
    svg = FIXTURES / "simple.svg"
    margin_window.set_document(load_svg_from_path(svg))
    project = tmp_path / "saved.plotpilot"
    write_project_file(
        project,
        ProjectSession(
            svg_path=svg.resolve(),
            checked_layer_ids=(),
            artwork_transform=ArtworkTransform.identity(),
            plot_settings=PlotSettings(),
            fallback_work_area=FallbackWorkArea.A4,
            print_margins=PrintMargins(horizontal_mm=7.0, vertical_mm=8.0),
        ),
    )
    margin_window._project_file_chooser = lambda: str(project)
    margin_window._open_project_action.trigger()
    assert margin_window.project_dirty is False
    assert margin_window._artwork_controls.print_margins() == PrintMargins(7.0, 8.0)

    margin_window._artwork_controls._margin_horizontal.setValue(12.0)
    assert margin_window.project_dirty is True
    assert margin_window._settings_service.print_margins.horizontal_mm == pytest.approx(12.0)


def test_margin_change_reuses_flattened_geometry(
    margin_window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from plotpilot.services import layer_geometry

    flatten_calls: list[str] = []
    original = layer_geometry.flatten_document_geometry

    def wrapped(svg_text: str):
        flatten_calls.append("flatten")
        return original(svg_text)

    monkeypatch.setattr(layer_geometry, "flatten_document_geometry", wrapped)
    queued: list[object] = []
    margin_window._preview_compute.submit = lambda operation: (  # type: ignore[method-assign]
        queued.append(operation) or 0
    )
    margin_window.set_document(load_svg_from_path(FIXTURES / "square_100mm_path.svg"))
    margin_window._preview_prep_timer.stop()
    queued.clear()
    flatten_calls.clear()

    margin_window._refresh_prepared_preview()
    assert queued
    first = queued[0]()  # type: ignore[operator]
    assert flatten_calls == ["flatten"]
    assert first.fresh_geometry is not None
    margin_window._geometry_cache.store(
        first.document_id,
        first.layer_id,
        first.fresh_geometry,
    )

    flatten_calls.clear()
    queued.clear()
    margin_window._artwork_controls._margin_horizontal.setValue(15.0)
    margin_window._preview_prep_timer.stop()
    margin_window._refresh_prepared_preview()
    assert queued
    second = queued[0]()  # type: ignore[operator]
    assert flatten_calls == []
    assert second.fresh_geometry is None
    assert second.printable_area is not None
    assert second.printable_area.x_mm == pytest.approx(15.0)
    margin_window.close()
