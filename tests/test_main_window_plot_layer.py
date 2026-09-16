"""Main window plot selected layer."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

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


def _wait_for_signal(signal, timeout_ms: int = 5000) -> None:
    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    signal.connect(loop.quit)
    timer.start(timeout_ms)
    loop.exec()
    timer.stop()


def _connected_window(qapp) -> tuple[MainWindow, FakePlotterBackend]:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok")
    )
    window = MainWindow(plotter_backend=fake)
    window.plotter_service._status = fake.detect_result  # noqa: SLF001
    window._apply_plotter_status(fake.detect_result)
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    window.set_document(document)
    return window, fake


def test_plot_button_disabled_without_svg(qapp) -> None:
    fake = FakePlotterBackend()
    window = MainWindow(plotter_backend=fake)
    assert not window._plot_layer_button.isEnabled()


def test_plot_button_disabled_when_disconnected(qapp) -> None:
    window, _fake = _connected_window(qapp)
    window.plotter_service._status = PlotterStatus(  # noqa: SLF001
        state=PlotterConnectionState.DISCONNECTED,
        message="no",
    )
    window._update_plot_controls()
    assert not window._plot_layer_button.isEnabled()


def test_plot_button_enabled_when_ready(qapp) -> None:
    window, _fake = _connected_window(qapp)
    assert window._plot_layer_button.isEnabled()


def test_cancel_confirmation_does_not_plot(qapp, monkeypatch) -> None:
    window, fake = _connected_window(qapp)

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Cancel,
    )
    window._on_plot_selected_layer()
    assert fake.plot_paths == []


def test_confirm_starts_plot(qapp, monkeypatch) -> None:
    window, fake = _connected_window(qapp)

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )
    window._on_plot_selected_layer()
    _wait_for_signal(window.plotter_service.plot_state_changed)
    _wait_for_signal(window.plotter_service.plot_state_changed)
    assert len(fake.plot_paths) == 1
    assert fake.plot_file_contents
    assert "only-in-layer-a" in fake.plot_file_contents[0]


def test_stop_button_while_plotting(qapp, monkeypatch) -> None:
    window, fake = _connected_window(qapp)
    fake.plot_block_until_cancel = True

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )
    window._on_plot_selected_layer()
    _wait_for_signal(window.plotter_service.plot_state_changed)
    assert window._plot_stop_button.isEnabled()
    window._plot_stop_button.click()
    _wait_for_signal(window.plotter_service.safe_stop_finished)


def test_no_auto_plot_on_startup(qapp) -> None:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok")
    )
    window = MainWindow(plotter_backend=fake)
    window.set_document(load_svg_from_path(FIXTURES / "preview_two_layers.svg"))
    assert fake.plot_paths == []


def test_layer_selection_alone_does_not_plot(qapp) -> None:
    window, fake = _connected_window(qapp)
    window._layers_list.setCurrentRow(1)
    assert fake.plot_paths == []
