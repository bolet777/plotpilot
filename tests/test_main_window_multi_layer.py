"""Main window multi-layer plotting."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from plotpilot.models.multi_layer_job import MultiLayerJobState
from plotpilot.models.plotter_status import PlotterConnectionState, PlotterStatus
from plotpilot.plotter.fake import FakePlotterBackend
from plotpilot.services.multi_layer_plot_service import MultiLayerPlotService
from plotpilot.services.svg_loader import load_svg_from_path
from plotpilot.ui.main_window import MainWindow
from qt_helpers import wait_for_plot_success, wait_until

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def qapp():
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    yield application


def _wait_for_job_state(service: MultiLayerPlotService, state: MultiLayerJobState) -> None:
    wait_until(lambda: service.job.state is state, timeout_ms=5000)
    assert service.job.state is state


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


def _check_row(window: MainWindow, row: int) -> None:
    item = window._layers_list.item(row)
    assert item is not None
    window._updating_layers = True
    item.setCheckState(Qt.CheckState.Checked)
    window._updating_layers = False


def test_preview_independent_from_checked(qapp) -> None:
    window, _fake = _connected_window(qapp)
    _check_row(window, 1)
    window._layers_list.setCurrentRow(0)
    assert window._layers_list.currentRow() == 0
    item = window._layers_list.item(1)
    assert item is not None
    assert item.checkState() is Qt.CheckState.Checked


def test_plot_checked_disabled_without_checks(qapp) -> None:
    window, _fake = _connected_window(qapp)
    assert not window._plot_checked_button.isEnabled()


def test_checking_layer_does_not_plot(qapp) -> None:
    window, fake = _connected_window(qapp)
    _check_row(window, 0)
    assert fake.plot_paths == []


def test_multi_confirm_required(qapp, monkeypatch) -> None:
    window, fake = _connected_window(qapp)
    _check_row(window, 0)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Cancel,
    )
    window._on_plot_checked_layers()
    assert fake.plot_paths == []


def test_multi_plot_flow(qapp, monkeypatch) -> None:
    window, fake = _connected_window(qapp)
    _check_row(window, 0)
    _check_row(window, 1)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )
    window._on_plot_checked_layers()
    wait_for_plot_success(window.plotter_service)
    _wait_for_job_state(window.multi_layer_service, MultiLayerJobState.WAITING_FOR_PEN_CHANGE)
    assert len(fake.plot_paths) == 1
    window._on_multi_continue()
    wait_for_plot_success(window.plotter_service)
    _wait_for_job_state(window.multi_layer_service, MultiLayerJobState.COMPLETED)
    assert len(fake.plot_paths) == 2


def test_single_layer_plot_still_works(qapp, monkeypatch) -> None:
    window, fake = _connected_window(qapp)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )
    window._on_plot_selected_layer()
    wait_for_plot_success(window.plotter_service)
    assert len(fake.plot_paths) == 1


def test_checkboxes_disabled_during_job(qapp, monkeypatch) -> None:
    window, _fake = _connected_window(qapp)
    _check_row(window, 0)
    _check_row(window, 1)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )
    window._on_plot_checked_layers()
    wait_for_plot_success(window.plotter_service)
    _wait_for_job_state(window.multi_layer_service, MultiLayerJobState.WAITING_FOR_PEN_CHANGE)
    item = window._layers_list.item(0)
    assert item is not None
    assert not (item.flags() & Qt.ItemFlag.ItemIsUserCheckable)


def test_synthetic_document_layer(qapp, monkeypatch) -> None:
    """Synthetic single-layer doc: viewport prep may reject tiny px-only art (no modal hang)."""
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok")
    )
    window = MainWindow(plotter_backend=fake)
    window.plotter_service._status = fake.detect_result  # noqa: SLF001
    window._apply_plotter_status(fake.detect_result)
    window.set_document(load_svg_from_path(FIXTURES / "no_groups.svg"))
    _check_row(window, 0)
    warnings: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: warnings.append(str(args[2]) if len(args) > 2 else ""),
    )
    window._on_plot_checked_layers()
    assert fake.plot_paths == []
    assert any("intersects" in message.lower() for message in warnings)
