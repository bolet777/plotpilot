"""PlotterService layer plotting."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from plotpilot.models.plot_job import PlotPhase, PlotResult
from plotpilot.models.plotter_status import PlotterConnectionState, PlotterStatus
from plotpilot.plotter.fake import FakePlotterBackend
from plotpilot.services.layer_service import layers_for_document
from plotpilot.services.plotter_service import PlotterService
from plotpilot.services.svg_loader import load_svg_from_path
from qt_helpers import (
    wait_for_plot_finished,
    wait_for_plot_started,
    wait_for_plot_success,
    wait_for_safe_stop,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def qapp():
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    yield application


def _connected_fake() -> FakePlotterBackend:
    return FakePlotterBackend(
        detect_result=PlotterStatus(
            state=PlotterConnectionState.CONNECTED,
            message="ok",
        )
    )


def test_start_plot_requires_connection(qapp) -> None:
    service = PlotterService(FakePlotterBackend())
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    layers = layers_for_document(document)
    assert service.start_plot_layer(document, layers[0]) is not None


def test_plot_success_and_temp_cleanup(qapp) -> None:
    fake = _connected_fake()
    service = PlotterService(fake)
    service._status = fake.detect_result  # noqa: SLF001
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    layers = layers_for_document(document)
    assert service.start_plot_layer(document, layers[0]) is None
    wait_for_plot_success(service)
    assert fake.plot_file_existed
    temp_path = fake.plot_paths[0]
    assert not temp_path.exists()


def test_plot_failure_returns_failed_phase(qapp) -> None:
    fake = _connected_fake()
    fake.plot_result = PlotResult(success=False, message="bounds exceeded")
    service = PlotterService(fake)
    service._status = fake.detect_result  # noqa: SLF001
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    layers = layers_for_document(document)
    service.start_plot_layer(document, layers[0])
    wait_for_plot_finished(service)
    assert service.plot_state.phase is PlotPhase.FAILED


def test_cancel_plot(qapp) -> None:
    fake = _connected_fake()
    fake.plot_block_until_cancel = True
    service = PlotterService(fake)
    service._status = fake.detect_result  # noqa: SLF001
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    layers = layers_for_document(document)
    service.start_plot_layer(document, layers[0])
    wait_for_plot_started(service)
    service.request_safe_stop()
    wait_for_safe_stop(service)
    assert fake.cancel_plot_calls >= 1
    assert service.plot_state.phase is PlotPhase.IDLE
    assert "motors disabled" in service.plot_state.message.lower()


def test_double_start_blocked(qapp) -> None:
    fake = _connected_fake()
    fake.plot_block_until_cancel = True
    service = PlotterService(fake)
    service._status = fake.detect_result  # noqa: SLF001
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    layers = layers_for_document(document)
    assert service.start_plot_layer(document, layers[0]) is None
    assert service.start_plot_layer(document, layers[1]) is not None
    service.cancel_plot()
    wait_for_plot_finished(service)
