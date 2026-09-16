"""PlotterService passes plot settings snapshot to backend."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from plotpilot.models.plot_job import PlotPhase
from plotpilot.models.plot_settings import PlotSettings
from plotpilot.models.plotter_status import PlotterConnectionState, PlotterStatus
from plotpilot.plotter.fake import FakePlotterBackend
from plotpilot.services.layer_service import layers_for_document
from plotpilot.services.plotter_service import PlotterService
from plotpilot.services.settings_service import SettingsService
from plotpilot.services.svg_loader import load_svg_from_path

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def qapp():
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    yield application


def _wait_for_signal(signal, timeout_ms: int = 5000) -> None:
    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    signal.connect(loop.quit)
    timer.start(timeout_ms)
    loop.exec()
    timer.stop()


def test_plot_passes_settings_snapshot(qapp) -> None:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok"),
    )
    settings = SettingsService(organization="PlotPilotTestSvc", application="snap")
    settings.replace(PlotSettings(pen_down_speed=15, model=2))
    service = PlotterService(fake, settings_service=settings)
    service._status = fake.detect_result  # noqa: SLF001
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    layers = layers_for_document(document)
    assert service.start_plot_layer(document, layers[0]) is None
    _wait_for_signal(service.plot_state_changed)
    _wait_for_signal(service.plot_state_changed)
    assert service.plot_state.phase is PlotPhase.SUCCEEDED
    assert fake.plot_settings_used == [PlotSettings(pen_down_speed=15, model=2)]
