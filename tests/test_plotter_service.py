"""PlotterService with fake backend."""

from __future__ import annotations

import time

import pytest
from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from plotpilot.models.plotter_status import PlotterConnectionState, PlotterStatus
from plotpilot.plotter.fake import FakePlotterBackend
from plotpilot.services.plotter_service import PlotterService


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


def test_initial_disconnected_state(qapp) -> None:
    service = PlotterService(FakePlotterBackend())
    assert service.status.state is PlotterConnectionState.DISCONNECTED


def test_successful_detection(qapp) -> None:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(
            state=PlotterConnectionState.CONNECTED,
            message="Firmware 2.7.0",
        )
    )
    service = PlotterService(fake)
    updates: list[PlotterStatus] = []
    service.status_changed.connect(updates.append)
    service.refresh()
    _wait_for_signal(service.status_changed)
    assert fake.detect_calls == 1
    assert updates[-1].is_connected


def test_detection_failure(qapp) -> None:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(
            state=PlotterConnectionState.ERROR,
            message="Timed out",
        )
    )
    service = PlotterService(fake)
    service.refresh()
    _wait_for_signal(service.status_changed)
    assert service.status.state is PlotterConnectionState.ERROR


def test_backend_exception_becomes_error(qapp) -> None:
    class ExplodingBackend(FakePlotterBackend):
        def detect(self) -> PlotterStatus:
            raise RuntimeError("boom")

    service = PlotterService(ExplodingBackend())
    service.refresh()
    _wait_for_signal(service.status_changed)
    assert service.status.state is PlotterConnectionState.ERROR
    assert "boom" in service.status.message


def test_pen_buttons_logic_via_fake(qapp) -> None:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.DISCONNECTED)
    )
    service = PlotterService(fake)
    assert service.pen_up() is False
    QCoreApplication.processEvents()
    assert fake.pen_up_calls == 0

    fake.detect_result = PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok")
    service.refresh()
    _wait_for_signal(service.status_changed)
    assert service.pen_up() is True
    _wait_for_signal(service.status_changed)
    assert fake.pen_up_calls == 1


def test_pen_down_calls_backend(qapp) -> None:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok")
    )
    service = PlotterService(fake)
    service._status = fake.detect_result  # noqa: SLF001 — test setup
    service.pen_down()
    _wait_for_signal(service.status_changed)
    assert fake.pen_down_calls == 1


def test_failed_pen_does_not_crash_service(qapp) -> None:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok"),
        pen_up_raises=RuntimeError("pen failed"),
    )
    service = PlotterService(fake)
    service._status = fake.detect_result  # noqa: SLF001
    service.pen_up()
    _wait_for_signal(service.status_changed)
    assert service.status.state is PlotterConnectionState.ERROR


def test_estimate_finish_does_not_clear_in_flight_pen_up(qapp) -> None:
    """Estimate completion must not release the manual-operation slot used by pen_up."""
    import threading

    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok"),
    )
    pen_started = threading.Event()

    original_pen_up = fake.pen_up

    def slow_pen_up() -> PlotterStatus:
        pen_started.set()
        time.sleep(0.15)
        return original_pen_up()

    fake.pen_up = slow_pen_up  # type: ignore[method-assign]

    service = PlotterService(fake)
    service._status = fake.detect_result  # noqa: SLF001
    assert service.pen_up() is True
    _wait_until(lambda: pen_started.is_set(), qapp)
    assert service._manual_operation == "pen_up"  # noqa: SLF001
    QCoreApplication.processEvents()
    assert service._manual_operation == "pen_up"  # noqa: SLF001
    _wait_for_signal(service.pen_up_finished)
    assert service._manual_operation is None  # noqa: SLF001


def _wait_until(predicate, qapp, timeout_ms: int = 3000) -> None:
    from qt_helpers import wait_until

    wait_until(predicate, timeout_ms=timeout_ms)


def test_coalesced_refresh(qapp) -> None:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.DISCONNECTED)
    )
    service = PlotterService(fake)
    service.refresh()
    service.refresh()
    service.refresh()
    _wait_for_signal(service.status_changed)
    QCoreApplication.processEvents()
    assert fake.detect_calls >= 1
    assert fake.detect_calls <= 2
