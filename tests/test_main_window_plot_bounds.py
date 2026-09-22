"""Main window bounds preflight UI and plot blocking."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from plotpilot.models.plot_settings import PlotSettings
from plotpilot.models.plotter_status import PlotterConnectionState, PlotterStatus
from plotpilot.plotter.fake import FakePlotterBackend
from plotpilot.services.svg_loader import load_svg_from_path
from plotpilot.ui.main_window import MainWindow

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def qapp():
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    yield application


def _connected_window(
    qapp,
    *,
    svg_name: str = "preview_two_layers.svg",
) -> tuple[MainWindow, FakePlotterBackend]:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok")
    )
    window = MainWindow(plotter_backend=fake)
    window.plotter_service._status = fake.detect_result  # noqa: SLF001
    window._apply_plotter_status(fake.detect_result)
    document = load_svg_from_path(FIXTURES / svg_name)
    window.set_document(document)
    return window, fake


def test_bounds_status_updates_after_svg_load(qapp) -> None:
    window, _fake = _connected_window(qapp)
    assert "Document:" in window._bounds_status_label.text()


def test_bounds_status_updates_after_model_change(qapp) -> None:
    window, _fake = _connected_window(qapp)
    window._settings_service.replace(PlotSettings(model=2))
    window._refresh_bounds_status()
    assert "AxiDraw V3/A3" in window._bounds_status_label.text()


def test_oversize_shows_status_but_allows_plot_start(qapp, tmp_path: Path) -> None:
    oversize = tmp_path / "big.svg"
    oversize.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="500mm" height="500mm">'
        '<line x1="0" y1="0" x2="10" y2="0" stroke="black"/></svg>',
        encoding="utf-8",
    )
    window, fake = _connected_window(qapp, svg_name="preview_two_layers.svg")
    window.set_document(load_svg_from_path(oversize))
    window._settings_service.replace(PlotSettings(model=1))
    window._refresh_bounds_status()
    assert "exceeds" in window._bounds_status_label.text().lower()
    assert window._plot_layer_button.isEnabled()


def test_oversize_does_not_call_backend(qapp, tmp_path: Path) -> None:
    oversize = tmp_path / "big.svg"
    oversize.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="500mm" height="500mm">'
        '<line x1="0" y1="0" x2="10" y2="0" stroke="black"/></svg>',
        encoding="utf-8",
    )
    window, fake = _connected_window(qapp)
    document = load_svg_from_path(oversize)
    window.set_document(document)
    window._settings_service.replace(PlotSettings(model=1))
    layer = window._current_layer()
    assert layer is not None
    error = window.plotter_service.start_plot_layer(document, layer)
    assert error is not None
    assert fake.plot_paths == []


def test_default_cli_still_allows_plot_when_connected(qapp) -> None:
    window, _fake = _connected_window(qapp)
    window._settings_service.reset_plot_settings()
    window._refresh_bounds_status()
    assert "Default (CLI)" in window._bounds_status_label.text()
    assert window._plot_layer_button.isEnabled()


def test_fallback_work_area_selector_visible_for_default_cli(qapp) -> None:
    window, _fake = _connected_window(qapp)
    window._settings_service.reset_plot_settings()
    window._sync_fallback_work_area_visibility()
    assert not window._fallback_work_area_row.isHidden()


def test_fallback_work_area_selector_hidden_for_explicit_model(qapp) -> None:
    window, _fake = _connected_window(qapp)
    window._settings_service.replace(PlotSettings(model=1))
    window._sync_fallback_work_area_visibility()
    assert window._fallback_work_area_row.isHidden()


def test_explicit_model_sets_preview_physical_layout(qapp, tmp_path: Path) -> None:
    svg_path = tmp_path / "a4.svg"
    svg_path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="297mm">'
        '<path d="M0 0"/></svg>',
        encoding="utf-8",
    )
    window, _fake = _connected_window(qapp)
    window.set_document(load_svg_from_path(svg_path))
    window._settings_service.replace(PlotSettings(model=1))
    window._refresh_preview_work_area()
    assert window._preview.physical_layout is not None
