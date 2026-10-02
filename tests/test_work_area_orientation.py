"""Fallback work area portrait / landscape (Default CLI)."""

from __future__ import annotations

from pathlib import Path

import pytest

from plotpilot.geometry.plot_viewport import PlotViewportError
from plotpilot.models.artwork_transform import ArtworkTransform
from plotpilot.models.plot_settings import PlotSettings, build_axicli_plot_argv
from plotpilot.models.plotter_model import get_plotter_model_info
from plotpilot.models.project_session import ProjectSession
from plotpilot.services.positioned_plot_service import (
    plot_viewport_for_settings,
    prepare_layer_plot_svg,
)
from plotpilot.services.preview_work_area import (
    FallbackWorkArea,
    WorkAreaOrientation,
    compute_physical_preview_layout,
    mm_rect_to_px,
    resolve_fallback_work_area_dimensions,
    resolve_plot_viewport,
    resolve_preview_work_area,
)
from plotpilot.services.project_file_service import FORMAT_ID, read_project_file, write_project_file
from plotpilot.services.settings_service import SettingsService, open_settings_store
from plotpilot.ui.main_window import MainWindow

FIXTURES = Path(__file__).resolve().parent / "fixtures"

_X250_SVG = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="300mm" height="50mm" viewBox="0 0 300 50">
  <line x1="245" y1="10" x2="255" y2="10" stroke="black"/>
</svg>"""


@pytest.mark.parametrize(
    ("size", "orientation", "width", "height"),
    [
        (FallbackWorkArea.A4, WorkAreaOrientation.PORTRAIT, 210.0, 297.0),
        (FallbackWorkArea.A4, WorkAreaOrientation.LANDSCAPE, 297.0, 210.0),
        (FallbackWorkArea.A3, WorkAreaOrientation.PORTRAIT, 297.0, 420.0),
        (FallbackWorkArea.A3, WorkAreaOrientation.LANDSCAPE, 420.0, 297.0),
    ],
)
def test_resolve_fallback_dimensions(
    size: FallbackWorkArea,
    orientation: WorkAreaOrientation,
    width: float,
    height: float,
) -> None:
    w, h = resolve_fallback_work_area_dimensions(size, orientation)
    assert w == pytest.approx(width)
    assert h == pytest.approx(height)
    area = resolve_preview_work_area(
        PlotSettings(),
        fallback=size,
        fallback_orientation=orientation,
    )
    assert area is not None
    assert area.width_mm == pytest.approx(width)
    assert area.height_mm == pytest.approx(height)


def test_explicit_model_ignores_fallback_orientation() -> None:
    info = get_plotter_model_info(1)
    viewport = resolve_plot_viewport(
        PlotSettings(model=1),
        fallback=FallbackWorkArea.A4,
        fallback_orientation=WorkAreaOrientation.LANDSCAPE,
    )
    assert viewport.width_mm == pytest.approx(info.max_width_mm)
    assert viewport.height_mm == pytest.approx(info.max_height_mm)


def test_plot_viewport_matches_preview_for_default_cli() -> None:
    preview = resolve_preview_work_area(
        PlotSettings(),
        fallback=FallbackWorkArea.A4,
        fallback_orientation=WorkAreaOrientation.LANDSCAPE,
    )
    viewport = plot_viewport_for_settings(
        PlotSettings(),
        fallback=FallbackWorkArea.A4,
        fallback_orientation=WorkAreaOrientation.LANDSCAPE,
    )
    assert preview is not None
    assert viewport.width_mm == preview.width_mm
    assert viewport.height_mm == preview.height_mm


def test_preview_layout_aspect_swaps_with_landscape() -> None:
    portrait = compute_physical_preview_layout(
        210.0,
        297.0,
        *resolve_fallback_work_area_dimensions(FallbackWorkArea.A4, WorkAreaOrientation.PORTRAIT),
        600.0,
        600.0,
    )
    landscape = compute_physical_preview_layout(
        210.0,
        297.0,
        *resolve_fallback_work_area_dimensions(FallbackWorkArea.A4, WorkAreaOrientation.LANDSCAPE),
        600.0,
        600.0,
    )
    assert portrait is not None and landscape is not None
    _, _, pw, ph = mm_rect_to_px(portrait, portrait.work_area_rect_mm)
    _, _, lw, lh = mm_rect_to_px(landscape, landscape.work_area_rect_mm)
    assert pw < ph
    assert lw > lh


def test_clipping_at_x250_portrait_vs_landscape() -> None:
    settings = PlotSettings()
    transform = ArtworkTransform.identity()
    with pytest.raises(PlotViewportError, match="No artwork intersects"):
        prepare_layer_plot_svg(
            _X250_SVG,
            plot_settings=settings,
            transform=transform,
            fallback=FallbackWorkArea.A4,
            fallback_orientation=WorkAreaOrientation.PORTRAIT,
        )
    prepared = prepare_layer_plot_svg(
        _X250_SVG,
        plot_settings=settings,
        transform=transform,
        fallback=FallbackWorkArea.A4,
        fallback_orientation=WorkAreaOrientation.LANDSCAPE,
    )
    assert prepared.path_count >= 1
    assert prepared.width_mm == pytest.approx(297.0)


def test_orientation_does_not_change_artwork_transform() -> None:
    inner_svg = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100">
  <line x1="10" y1="50" x2="90" y2="50" stroke="black"/>
</svg>"""
    transform = ArtworkTransform(x_mm=12.0, y_mm=-3.0, scale=1.25)
    portrait = prepare_layer_plot_svg(
        inner_svg,
        plot_settings=PlotSettings(),
        transform=transform,
        fallback=FallbackWorkArea.A4,
        fallback_orientation=WorkAreaOrientation.PORTRAIT,
    )
    landscape = prepare_layer_plot_svg(
        inner_svg,
        plot_settings=PlotSettings(),
        transform=transform,
        fallback=FallbackWorkArea.A4,
        fallback_orientation=WorkAreaOrientation.LANDSCAPE,
    )
    assert portrait.width_mm != landscape.width_mm
    assert transform.x_mm == pytest.approx(12.0)
    assert transform.y_mm == pytest.approx(-3.0)
    assert transform.scale == pytest.approx(1.25)


def test_axicli_still_receives_n_flag() -> None:
    argv = build_axicli_plot_argv("layer.svg", PlotSettings(model=1))
    assert "-N" in argv


def test_orientation_persists_in_qsettings(qapp) -> None:
    org, app = "PlotPilotTestOrientation", "QSettings"
    service = SettingsService(organization=org, application=app)
    service.set_preview_fallback_work_area_orientation(WorkAreaOrientation.LANDSCAPE)
    reloaded = SettingsService(organization=org, application=app)
    assert reloaded.preview_fallback_work_area_orientation is WorkAreaOrientation.LANDSCAPE
    open_settings_store(org, app).clear()


def test_project_round_trip_orientation(tmp_path: Path) -> None:
    svg = FIXTURES / "simple.svg"
    session = ProjectSession(
        svg_path=svg.resolve(),
        checked_layer_ids=(),
        artwork_transform=ArtworkTransform.identity(),
        plot_settings=PlotSettings(),
        fallback_work_area=FallbackWorkArea.A3,
        fallback_work_area_orientation=WorkAreaOrientation.LANDSCAPE,
    )
    project = tmp_path / "orient.plotpilot"
    write_project_file(project, session)
    loaded = read_project_file(project)
    assert loaded.fallback_work_area_orientation is WorkAreaOrientation.LANDSCAPE


def test_legacy_project_defaults_orientation_portrait(tmp_path: Path) -> None:
    import json

    project = tmp_path / "legacy.plotpilot"
    project.write_text(
        json.dumps(
            {
                "format": FORMAT_ID,
                "version": 1,
                "svg": {"path": str(FIXTURES / "simple.svg")},
                "preview": {"fallback_work_area": "A3"},
            }
        ),
        encoding="utf-8",
    )
    loaded = read_project_file(project)
    assert loaded.fallback_work_area is FallbackWorkArea.A3
    assert loaded.fallback_work_area_orientation is WorkAreaOrientation.PORTRAIT


@pytest.fixture
def orientation_window(qapp, fake_plotter_backend, monkeypatch) -> MainWindow:
    from PySide6.QtWidgets import QMessageBox

    org, app_name = "PlotPilotTestOrientation", "MainWindow"
    open_settings_store(org, app_name).clear()

    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )
    service = SettingsService(
        organization=org,
        application=app_name,
    )
    window = MainWindow(
        plotter_backend=fake_plotter_backend,
        settings_service=service,
        svg_file_chooser=lambda: None,
        project_file_chooser=lambda: None,
        save_project_file_chooser=lambda: None,
    )
    yield window
    window.close()
    qapp.processEvents()
    open_settings_store("PlotPilotTestOrientation", "MainWindow").clear()


def test_orientation_change_marks_project_dirty(
    qapp,
    orientation_window: MainWindow,
    tmp_path: Path,
) -> None:
    svg = tmp_path / "doc.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm"/>',
        encoding="utf-8",
    )
    from plotpilot.services.svg_loader import load_svg_from_path

    orientation_window.set_document(load_svg_from_path(svg))
    orientation_window._project_file_path = tmp_path / "p.plotpilot"
    orientation_window._project_dirty = False
    portrait_idx = orientation_window._fallback_work_area_orientation_combo.findData(
        WorkAreaOrientation.PORTRAIT,
    )
    landscape_idx = orientation_window._fallback_work_area_orientation_combo.findData(
        WorkAreaOrientation.LANDSCAPE,
    )
    orientation_window._fallback_work_area_orientation_combo.setCurrentIndex(portrait_idx)
    orientation_window._project_dirty = False
    orientation_window._fallback_work_area_orientation_combo.setCurrentIndex(landscape_idx)
    qapp.processEvents()
    assert orientation_window.project_dirty is True
