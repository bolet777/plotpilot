"""Main window project save/open behavior."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from plotpilot.models.artwork_transform import ArtworkTransform
from plotpilot.models.plot_settings import PlotSettings
from plotpilot.services.preview_work_area import FallbackWorkArea
from plotpilot.services.project_file_service import read_project_file, write_project_file
from plotpilot.services.settings_service import SettingsService
from plotpilot.services.svg_loader import load_svg_from_path
from plotpilot.ui.main_window import MainWindow

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def isolated_settings(qapp) -> SettingsService:
    service = SettingsService(organization="PlotPilotTestProject", application="MainWindowProject")
    yield service
    from PySide6.QtCore import QSettings

    QSettings("PlotPilotTestProject", "MainWindowProject").clear()


@pytest.fixture
def project_window(
    qapp,
    fake_plotter_backend,
    isolated_settings: SettingsService,
    monkeypatch,
) -> MainWindow:
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )
    window = MainWindow(
        plotter_backend=fake_plotter_backend,
        settings_service=isolated_settings,
        svg_file_chooser=lambda: None,
        project_file_chooser=lambda: None,
        save_project_file_chooser=lambda: None,
    )
    yield window
    window.close()
    qapp.processEvents()


def _check_layer_by_id(window: MainWindow, layer_id: str) -> None:
    for row in range(window._layers_list.count()):
        item = window._layers_list.item(row)
        if item is not None and item.data(Qt.ItemDataRole.UserRole) == layer_id:
            item.setCheckState(Qt.CheckState.Checked)
            return
    msg = f"layer id not found: {layer_id}"
    raise AssertionError(msg)


def test_save_as_creates_plotpilot(project_window: MainWindow, tmp_path: Path) -> None:
    svg = FIXTURES / "three_root_groups.svg"
    project_window.set_document(load_svg_from_path(svg))
    _check_layer_by_id(project_window, "orange")
    project_window._set_artwork_transform(
        ArtworkTransform(x_mm=1.0, y_mm=2.0, scale=0.5),
        mark_dirty=False,
    )
    target = tmp_path / "job.plotpilot"
    project_window._save_project_file_chooser = lambda: str(target)
    project_window._save_project_as_action.trigger()
    assert target.is_file()
    loaded = read_project_file(target)
    assert "orange" in loaded.checked_layer_ids
    assert loaded.artwork_transform.x_mm == pytest.approx(1.0)


def test_save_overwrites_existing_project_file(project_window: MainWindow, tmp_path: Path) -> None:
    svg = FIXTURES / "simple.svg"
    project_window.set_document(load_svg_from_path(svg))
    path = tmp_path / "existing.plotpilot"
    project_window._project_file_path = path
    project_window._settings_service.begin_project_session(
        PlotSettings(),
        FallbackWorkArea.A4,
    )
    project_window._save_project_action.trigger()
    first = read_project_file(path)
    project_window._set_artwork_transform(ArtworkTransform(x_mm=99.0, y_mm=0.0, scale=1.0))
    project_window._save_project_action.trigger()
    second = read_project_file(path)
    assert second.artwork_transform.x_mm == pytest.approx(99.0)
    assert first.artwork_transform.x_mm != pytest.approx(99.0)


def test_open_project_restores_state(project_window: MainWindow, tmp_path: Path) -> None:
    svg = FIXTURES / "three_root_groups.svg"
    project_file = tmp_path / "saved.plotpilot"
    from plotpilot.models.project_session import ProjectSession

    session = ProjectSession(
        svg_path=svg.resolve(),
        checked_layer_ids=("orange",),
        artwork_transform=ArtworkTransform(x_mm=5.0, y_mm=-2.0, scale=2.0),
        plot_settings=PlotSettings(model=2),
        fallback_work_area=FallbackWorkArea.A3,
    )
    write_project_file(project_file, session)
    project_window._project_file_chooser = lambda: str(project_file)
    project_window._open_project_action.trigger()
    assert project_window.document is not None
    assert project_window.project_file_path == project_file.resolve()
    assert project_window.project_dirty is False
    assert project_window._preview.artwork_transform.scale == pytest.approx(2.0)
    checked = [layer.layer_id for layer in project_window._checked_layers()]
    assert checked == ["orange"]


def test_missing_svg_preserves_session(project_window: MainWindow, tmp_path: Path) -> None:
    svg = FIXTURES / "simple.svg"
    project_window.set_document(load_svg_from_path(svg))
    before = project_window.document
    project_file = tmp_path / "broken.plotpilot"
    from plotpilot.models.project_session import ProjectSession

    write_project_file(
        project_file,
        ProjectSession(
            svg_path=tmp_path / "missing.svg",
            checked_layer_ids=(),
            artwork_transform=ArtworkTransform.identity(),
            plot_settings=PlotSettings(),
            fallback_work_area=FallbackWorkArea.A4,
        ),
    )
    project_window._project_file_chooser = lambda: str(project_file)
    project_window._open_project_action.trigger()
    assert project_window.document is before


def test_malformed_project_preserves_session(project_window: MainWindow, tmp_path: Path) -> None:
    svg = FIXTURES / "simple.svg"
    project_window.set_document(load_svg_from_path(svg))
    before = project_window.document
    bad = tmp_path / "bad.plotpilot"
    bad.write_text("not-json", encoding="utf-8")
    project_window._project_file_chooser = lambda: str(bad)
    project_window._open_project_action.trigger()
    assert project_window.document is before
