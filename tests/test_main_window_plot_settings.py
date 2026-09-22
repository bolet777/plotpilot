"""Main window plot settings UI."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from plotpilot.models.plot_job import PlotPhase, PlotResult
from plotpilot.models.plot_settings import REORDERING_BASIC, PlotSettings
from plotpilot.models.plotter_status import PlotterConnectionState, PlotterStatus
from plotpilot.plotter.fake import FakePlotterBackend
from plotpilot.services.settings_service import SettingsService
from plotpilot.services.svg_loader import load_svg_from_path
from plotpilot.ui.main_window import MainWindow
from qt_helpers import wait_for_plot_finished, wait_for_plot_started, wait_for_plot_success

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def qapp():
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    yield application


def _window(qapp) -> tuple[MainWindow, FakePlotterBackend, SettingsService]:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok"),
    )
    settings = SettingsService(
        organization=f"PlotPilotTest-{uuid.uuid4().hex}",
        application=f"PlotPilotTest-{uuid.uuid4().hex}",
    )
    window = MainWindow(plotter_backend=fake, settings_service=settings)
    window.plotter_service._status = fake.detect_result  # noqa: SLF001
    window._apply_plotter_status(fake.detect_result)
    window.set_document(load_svg_from_path(FIXTURES / "preview_two_layers.svg"))
    return window, fake, settings


def test_ui_reflects_settings(qapp) -> None:
    window, _fake, settings = _window(qapp)
    settings.replace(PlotSettings(pen_down_speed=40, model=3))
    assert window._plot_settings._pen_down_slider.value() == 40  # noqa: SLF001
    assert window._plot_settings._model_combo.currentData() == 3  # noqa: SLF001


def test_settings_disabled_while_plotting(qapp, monkeypatch) -> None:
    window, fake, _settings = _window(qapp)
    fake.plot_block_until_cancel = True
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )
    window._on_plot_selected_layer()
    wait_for_plot_started(window.plotter_service)
    assert not window._plot_settings._pen_down_slider.isEnabled()  # noqa: SLF001
    window.plotter_service.cancel_plot()
    wait_for_plot_finished(window.plotter_service)
    assert window._plot_settings._pen_down_slider.isEnabled()  # noqa: SLF001


def test_settings_reenabled_after_success(qapp, monkeypatch) -> None:
    window, _fake, _settings = _window(qapp)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )
    window._on_plot_selected_layer()
    wait_for_plot_success(window.plotter_service)
    assert window.plotter_service.plot_state.phase is PlotPhase.SUCCEEDED
    assert window._plot_settings._model_combo.isEnabled()  # noqa: SLF001


def test_settings_reenabled_after_failure(qapp, monkeypatch) -> None:
    window, fake, _settings = _window(qapp)
    fake.plot_result = PlotResult(success=False, message="fail")
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )
    window._on_plot_selected_layer()
    wait_for_plot_finished(window.plotter_service)
    assert window.plotter_service.plot_state.phase is PlotPhase.FAILED
    assert window._plot_settings._accel_slider.isEnabled()  # noqa: SLF001


def test_changing_slider_does_not_start_plot(qapp) -> None:
    window, fake, _settings = _window(qapp)
    window._plot_settings._pen_down_slider.setValue(50)  # noqa: SLF001
    assert fake.plot_paths == []


def test_optimize_checkbox_reflects_settings(qapp) -> None:
    window, _fake, settings = _window(qapp)
    settings.replace(PlotSettings(path_reordering=REORDERING_BASIC))
    assert window._plot_settings._optimize_checkbox.isChecked()  # noqa: SLF001


def test_toggling_optimize_does_not_start_plot(qapp) -> None:
    window, fake, _settings = _window(qapp)
    window._plot_settings._optimize_checkbox.setChecked(True)  # noqa: SLF001
    assert fake.plot_paths == []


def test_reset_clears_ui_to_defaults(qapp) -> None:
    window, _fake, settings = _window(qapp)
    settings.replace(PlotSettings(pen_down_speed=50))
    window._plot_settings._on_reset()  # noqa: SLF001
    assert settings.plot_settings == PlotSettings()
    assert window._plot_settings._pen_down_slider.value() == 25  # noqa: SLF001
