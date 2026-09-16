"""Main window plotter section."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

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


def _wait_for_signal(signal, timeout_ms: int = 3000) -> None:
    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    signal.connect(loop.quit)
    timer.start(timeout_ms)
    loop.exec()
    timer.stop()


def test_startup_disconnected_pen_disabled(qapp) -> None:
    fake = FakePlotterBackend()
    window = MainWindow(plotter_backend=fake)
    assert fake.detect_calls == 0
    assert not window._pen_up_button.isEnabled()
    assert not window._pen_down_button.isEnabled()
    assert "Not connected" in window._plotter_status_label.text()


def test_refresh_updates_ui(qapp) -> None:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(
            state=PlotterConnectionState.CONNECTED,
            message="Firmware 2.7.0",
        )
    )
    window = MainWindow(plotter_backend=fake)
    window.plotter_service.refresh()
    _wait_for_signal(window.plotter_service.status_changed)
    assert window._pen_up_button.isEnabled()
    assert window._pen_down_button.isEnabled()
    assert "Connected" in window._plotter_status_label.text()


def test_svg_open_works_without_plotter(qapp) -> None:
    fake = FakePlotterBackend()
    window = MainWindow(plotter_backend=fake)
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    window.set_document(document)
    assert window.current_preview_svg is not None
    assert fake.detect_calls == 0


def test_pen_up_from_ui(qapp) -> None:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok")
    )
    window = MainWindow(plotter_backend=fake)
    window.plotter_service._status = fake.detect_result  # noqa: SLF001
    window._apply_plotter_status(fake.detect_result)
    window._pen_up_button.click()
    _wait_for_signal(window.plotter_service.status_changed)
    assert fake.pen_up_calls == 1
