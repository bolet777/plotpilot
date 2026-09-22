"""Automatic AxiDraw presence monitoring in PlotterService."""

from __future__ import annotations

import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer
from PySide6.QtTest import QTest

from plotpilot.models.multi_layer_job import MultiLayerJobState
from plotpilot.models.plot_job import PlotPhase, PlotResult
from plotpilot.models.plotter_status import PlotterConnectionState, PlotterStatus
from plotpilot.plotter.axidraw import AxiDrawCliBackend
from plotpilot.plotter.fake import FakePlotterBackend
from plotpilot.services.layer_service import layers_for_document
from plotpilot.services.multi_layer_plot_service import MultiLayerPlotService
from plotpilot.services.plotter_service import (
    AUTO_DETECT_INTERVAL_MS,
    AUTO_DETECT_RESUME_DELAY_MS,
    PlotterService,
)
from plotpilot.services.svg_loader import load_svg_from_path
from plotpilot.ui.main_window import MainWindow

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _sample_document():
    return load_svg_from_path(FIXTURES / "preview_two_layers.svg")


def _wait_for_signal(signal, timeout_ms: int = 5000) -> None:
    loop = QEventLoop()
    timer = QTimer()
    received = {"ok": False}

    def _mark_received(*_args: object) -> None:
        received["ok"] = True

    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    signal.connect(_mark_received)
    signal.connect(loop.quit)
    timer.start(timeout_ms)
    loop.exec()
    timer.stop()
    if not received["ok"]:
        raise AssertionError("Timed out waiting for Qt signal")


def _wait_until(predicate: Callable[[], bool], timeout_ms: int = 5000) -> None:
    deadline = time.monotonic() + timeout_ms / 1000.0
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        if predicate():
            return
        remaining_ms = int(max(0.0, (deadline - time.monotonic()) * 1000.0))
        QTest.qWait(min(10, remaining_ms))
    raise AssertionError("Timed out waiting for condition")


def _wait_for_detection_idle(service: PlotterService, timeout_ms: int = 8000) -> None:
    _wait_until(
        lambda: not service._detect_in_flight and service._manual_operation is None,  # noqa: SLF001
        timeout_ms=timeout_ms,
    )


def _wait_for_presence_baseline(
    service: PlotterService,
    fake: FakePlotterBackend,
    *,
    timeout_ms: int = 8000,
) -> int:
    """Wait for initial full detect + first presence poll, then a quiet window."""
    _wait_until(lambda: fake.detect_calls >= 1, timeout_ms=timeout_ms)
    _wait_until(lambda: fake.detect_presence_calls >= 1, timeout_ms=timeout_ms)
    _wait_for_detection_idle(service, timeout_ms=timeout_ms)
    return fake.detect_presence_calls


def _assert_presence_stable_for(
    fake: FakePlotterBackend,
    baseline: int,
    duration_ms: int,
) -> None:
    deadline = time.monotonic() + duration_ms / 1000.0
    while time.monotonic() < deadline:
        assert fake.detect_presence_calls == baseline
        QCoreApplication.processEvents()
        remaining_ms = int(max(0.0, (deadline - time.monotonic()) * 1000.0))
        QTest.qWait(min(10, remaining_ms))


def _assert_presence_stable_while(
    fake: FakePlotterBackend,
    baseline: int,
    predicate: Callable[[], bool],
    *,
    timeout_ms: int = 3000,
) -> None:
    deadline = time.monotonic() + timeout_ms / 1000.0
    while time.monotonic() < deadline:
        if not predicate():
            return
        assert fake.detect_presence_calls == baseline
        QCoreApplication.processEvents()
        remaining_ms = int(max(0.0, (deadline - time.monotonic()) * 1000.0))
        QTest.qWait(min(10, remaining_ms))
    raise AssertionError("Timed out while waiting for end condition")


_monitored_services: list[PlotterService] = []


def _wait_plotter_idle(service: PlotterService, timeout_ms: int = 8000) -> None:
    _wait_for_detection_idle(service, timeout_ms=timeout_ms)


def _start_monitor(service: PlotterService) -> None:
    _monitored_services.append(service)
    service.start_automatic_monitoring()


@pytest.mark.slow
def test_startup_triggers_full_detect_without_blocking(qapp) -> None:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(
            state=PlotterConnectionState.CONNECTED,
            message="Firmware 2.7.0",
        )
    )
    service = PlotterService(fake)
    _start_monitor(service)
    QCoreApplication.processEvents()
    assert fake.detect_calls == 0
    _wait_until(lambda: fake.detect_calls >= 1)
    assert fake.detect_calls == 1


@pytest.mark.slow
def test_periodic_presence_poll(qapp) -> None:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(
            state=PlotterConnectionState.CONNECTED,
            message="Firmware 2.7.0",
        ),
        detect_presence_result=PlotterStatus(
            state=PlotterConnectionState.CONNECTED,
            message="Connected",
        ),
    )
    service = PlotterService(fake)
    service._status = fake.detect_result  # noqa: SLF001
    _start_monitor(service)
    _wait_until(lambda: fake.detect_calls >= 1)
    before = fake.detect_presence_calls
    _wait_until(lambda: fake.detect_presence_calls > before, timeout_ms=3000)
    assert fake.detect_presence_calls >= before + 1


@pytest.mark.slow
def test_detect_calls_never_overlap(qapp) -> None:
    lock = threading.Lock()
    in_detect = {"count": 0, "max": 0}

    class SlowFake(FakePlotterBackend):
        def detect_presence(self) -> PlotterStatus:
            with lock:
                in_detect["count"] += 1
                in_detect["max"] = max(in_detect["max"], in_detect["count"])
            try:
                time.sleep(0.03)
                return super().detect_presence()
            finally:
                with lock:
                    in_detect["count"] -= 1

    fake = SlowFake(
        detect_result=PlotterStatus(
            state=PlotterConnectionState.CONNECTED,
            message="Firmware",
        ),
        detect_presence_result=PlotterStatus(
            state=PlotterConnectionState.CONNECTED,
            message="Connected",
        ),
    )
    service = PlotterService(fake)
    service._status = PlotterStatus(  # noqa: SLF001
        state=PlotterConnectionState.CONNECTED,
        message="Firmware",
    )
    _start_monitor(service)
    _wait_until(lambda: fake.detect_presence_calls >= 2, timeout_ms=8000)
    assert in_detect["max"] == 1


@pytest.mark.slow
def test_polling_suspended_during_plot(qapp) -> None:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok"),
        detect_presence_result=PlotterStatus(
            state=PlotterConnectionState.CONNECTED,
            message="Connected",
        ),
        plot_block_until_cancel=True,
    )
    service = PlotterService(fake)
    service._status = fake.detect_result  # noqa: SLF001
    _start_monitor(service)
    presence_before = _wait_for_presence_baseline(service, fake)
    document = _sample_document()
    layer = layers_for_document(document)[0]
    service.start_plot_layer(document, layer)
    _wait_until(lambda: fake.plot_paths, timeout_ms=2000)
    _assert_presence_stable_for(fake, presence_before, duration_ms=250)
    service.cancel_plot()
    _wait_until(lambda: not service._plot_in_flight)  # noqa: SLF001
    _wait_until(
        lambda: fake.detect_presence_calls > presence_before,
        timeout_ms=8000,
    )


@pytest.mark.slow
def test_polling_suspended_during_safe_stop(qapp) -> None:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok"),
        detect_presence_result=PlotterStatus(
            state=PlotterConnectionState.CONNECTED,
            message="Connected",
        ),
        plot_block_until_cancel=True,
    )
    service = PlotterService(fake)
    service._status = fake.detect_result  # noqa: SLF001
    _start_monitor(service)
    presence_before = _wait_for_presence_baseline(service, fake)
    document = _sample_document()
    layer = layers_for_document(document)[0]
    service.start_plot_layer(document, layer)
    _wait_until(lambda: fake.plot_paths)
    safe_stop_done = {"ok": False}
    service.safe_stop_finished.connect(lambda *_: safe_stop_done.__setitem__("ok", True))
    service.request_safe_stop()
    _assert_presence_stable_while(
        fake,
        presence_before,
        lambda: not safe_stop_done["ok"],
        timeout_ms=8000,
    )
    if not safe_stop_done["ok"]:
        _wait_for_signal(service.safe_stop_finished, timeout_ms=8000)
    _wait_until(lambda: not service.plot_state.is_active, timeout_ms=8000)
    _wait_until(lambda: not service._auto_detect_paused)  # noqa: SLF001
    _wait_until(lambda: fake.detect_presence_calls > presence_before, timeout_ms=8000)


@pytest.mark.slow
def test_polling_suspended_during_pen_commands(qapp) -> None:
    lock = threading.Event()

    class PenSlowFake(FakePlotterBackend):
        def pen_up(self) -> PlotterStatus:
            lock.set()
            time.sleep(0.03)
            return super().pen_up()

    fake = PenSlowFake(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok"),
        detect_presence_result=PlotterStatus(
            state=PlotterConnectionState.CONNECTED,
            message="Connected",
        ),
    )
    service = PlotterService(fake)
    service._status = fake.detect_result  # noqa: SLF001
    _start_monitor(service)
    _wait_until(lambda: fake.detect_calls >= 1)
    _wait_plotter_idle(service)
    presence_before = fake.detect_presence_calls
    pen_done = {"ok": False}
    service.status_changed.connect(lambda *_: pen_done.__setitem__("ok", True))
    service.pen_up()
    _wait_until(lambda: lock.is_set(), timeout_ms=8000)
    _assert_presence_stable_while(
        fake,
        presence_before,
        lambda: service._manual_operation is not None and not pen_done["ok"],  # noqa: SLF001
        timeout_ms=3000,
    )
    if not pen_done["ok"]:
        _wait_for_signal(service.status_changed)
    _wait_until(lambda: fake.detect_presence_calls > presence_before, timeout_ms=8000)


@pytest.mark.slow
def test_automatic_disconnect(qapp) -> None:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="Firmware"),
        detect_presence_result=PlotterStatus(
            state=PlotterConnectionState.CONNECTED,
            message="Connected",
        ),
    )
    service = PlotterService(fake)
    updates: list[PlotterStatus] = []
    service.status_changed.connect(updates.append)
    _start_monitor(service)
    _wait_for_signal(service.status_changed)
    fake.detect_presence_result = PlotterStatus(
        state=PlotterConnectionState.DISCONNECTED,
        message="Not connected",
    )
    _wait_until(
        lambda: service.status.state is PlotterConnectionState.DISCONNECTED,
        timeout_ms=4000,
    )
    assert updates[-1].state is PlotterConnectionState.DISCONNECTED


@pytest.mark.slow
def test_automatic_reconnect_runs_full_detect(qapp) -> None:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(
            state=PlotterConnectionState.CONNECTED,
            message="Firmware 2.7.0",
        ),
        detect_presence_result=PlotterStatus(
            state=PlotterConnectionState.DISCONNECTED,
            message="Not connected",
        ),
    )
    service = PlotterService(fake)
    _start_monitor(service)
    _wait_for_signal(service.status_changed)
    assert service.status.state is PlotterConnectionState.CONNECTED
    fake.detect_presence_result = PlotterStatus(
        state=PlotterConnectionState.DISCONNECTED,
        message="Not connected",
    )
    _wait_until(
        lambda: service.status.state is PlotterConnectionState.DISCONNECTED,
        timeout_ms=4000,
    )
    fake.detect_presence_result = PlotterStatus(
        state=PlotterConnectionState.CONNECTED,
        message="Connected",
    )
    _wait_until(lambda: fake.detect_calls >= 2, timeout_ms=4000)
    _wait_plotter_idle(service)
    _wait_until(lambda: service.status.message == "Firmware 2.7.0", timeout_ms=4000)


@pytest.mark.slow
def test_identical_state_does_not_spam_signals(qapp) -> None:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="Firmware"),
        detect_presence_result=PlotterStatus(
            state=PlotterConnectionState.CONNECTED,
            message="Connected",
        ),
    )
    service = PlotterService(fake)
    emissions = {"count": 0}

    def _count(_status: PlotterStatus) -> None:
        emissions["count"] += 1

    service.status_changed.connect(_count)
    _start_monitor(service)
    _wait_for_signal(service.status_changed)
    baseline = emissions["count"]
    _wait_until(lambda: fake.detect_presence_calls >= 2, timeout_ms=4000)
    assert emissions["count"] == baseline


def test_refresh_still_works_when_idle(qapp) -> None:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok"),
    )
    service = PlotterService(fake)
    service.refresh()
    _wait_for_signal(service.status_changed)
    assert fake.detect_calls == 1


@pytest.mark.slow
def test_refresh_coalesced_during_plot(qapp) -> None:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok"),
        plot_block_until_cancel=True,
    )
    service = PlotterService(fake)
    service._status = fake.detect_result  # noqa: SLF001
    document = _sample_document()
    layer = layers_for_document(document)[0]
    service.start_plot_layer(document, layer)
    _wait_until(lambda: fake.plot_paths)
    service.refresh()
    assert service._pending_refresh  # noqa: SLF001
    service.cancel_plot()
    _wait_until(lambda: not service._plot_in_flight, timeout_ms=8000)  # noqa: SLF001
    _wait_until(
        lambda: service.plot_state.phase in (PlotPhase.CANCELLED, PlotPhase.IDLE),
        timeout_ms=8000,
    )
    _wait_plotter_idle(service)
    _wait_until(lambda: fake.detect_calls >= 1, timeout_ms=8000)


@pytest.mark.slow
def test_shutdown_stops_monitor_timer(qapp) -> None:
    fake = FakePlotterBackend()
    service = PlotterService(fake)
    _start_monitor(service)
    assert service._monitor_timer.isActive()  # noqa: SLF001
    service.stop_automatic_monitoring()
    assert not service._monitor_timer.isActive()  # noqa: SLF001


@pytest.mark.slow
def test_multi_layer_pen_change_suspends_presence(qapp) -> None:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok"),
        detect_presence_result=PlotterStatus(
            state=PlotterConnectionState.CONNECTED,
            message="Connected",
        ),
        plot_result=PlotResult(success=True, message="done"),
    )
    plotter = PlotterService(fake)
    multi = MultiLayerPlotService(plotter)
    plotter._status = fake.detect_result  # noqa: SLF001
    _start_monitor(plotter)
    _wait_until(lambda: fake.detect_calls >= 1)
    document = _sample_document()
    layers = layers_for_document(document)
    assert multi.start_job(document, layers, settings=plotter._snapshot_plot_settings()) is None  # noqa: SLF001
    _wait_until(
        lambda: multi.job.state is MultiLayerJobState.WAITING_FOR_PEN_CHANGE,
        timeout_ms=8000,
    )
    presence_at_wait = fake.detect_presence_calls
    _assert_presence_stable_for(fake, presence_at_wait, duration_ms=200)


@pytest.mark.slow
def test_main_window_starts_monitoring(qapp) -> None:
    fake = FakePlotterBackend(
        detect_result=PlotterStatus(state=PlotterConnectionState.CONNECTED, message="ok"),
    )
    window = MainWindow(plotter_backend=fake)
    assert window.plotter_service._monitor_timer.isActive()  # noqa: SLF001
    window.close()
    QCoreApplication.processEvents()


def test_detect_presence_uses_list_names_only() -> None:
    calls: list[list[str]] = []

    def runner(argv: list[str], _timeout: float) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv[-1] == "--version":
            return subprocess.CompletedProcess(argv, 0, stdout="AxiDraw CLI 3.9.6\n", stderr="")
        if argv[-1] == "list_names":
            return subprocess.CompletedProcess(
                argv,
                0,
                stdout="List of attached AxiDraw units:\n/dev/cu.test\n",
                stderr="",
            )
        raise AssertionError(f"unexpected argv: {argv}")

    backend = AxiDrawCliBackend(cli_path="axicli", _runner=runner)
    status = backend.detect_presence()
    assert status.is_connected
    assert all("fw_version" not in call for call in calls)


def test_constants_are_sensible() -> None:
    assert AUTO_DETECT_INTERVAL_MS >= 5000
    assert AUTO_DETECT_RESUME_DELAY_MS >= 1000
