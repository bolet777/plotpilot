"""Small Qt test utilities (avoid missing signals and long busy-waits)."""

from __future__ import annotations

import time
from collections.abc import Callable

from PySide6.QtCore import QCoreApplication
from PySide6.QtTest import QTest

from plotpilot.models.plot_job import PlotPhase
from plotpilot.services.plotter_service import PlotterService

_TERMINAL_PLOT_PHASES = frozenset(
    {
        PlotPhase.SUCCEEDED,
        PlotPhase.FAILED,
        PlotPhase.CANCELLED,
        PlotPhase.IDLE,
    }
)


def wait_until(predicate: Callable[[], bool], *, timeout_ms: int = 3000) -> None:
    """Poll the Qt event loop until ``predicate()`` is true."""
    deadline = time.monotonic() + timeout_ms / 1000.0
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        if predicate():
            return
        QTest.qWait(2)
    raise AssertionError("Timed out waiting for condition")


def wait_for_plot_phase(
    service: PlotterService,
    phase: PlotPhase,
    *,
    timeout_ms: int = 3000,
) -> None:
    wait_until(lambda: service.plot_state.phase is phase, timeout_ms=timeout_ms)


def wait_for_plot_started(service: PlotterService, *, timeout_ms: int = 3000) -> None:
    wait_until(
        lambda: service.plot_state.phase is PlotPhase.RUNNING or service._plot_in_flight,  # noqa: SLF001
        timeout_ms=timeout_ms,
    )


def wait_for_plot_finished(service: PlotterService, *, timeout_ms: int = 3000) -> None:
    wait_until(
        lambda: service.plot_state.phase in _TERMINAL_PLOT_PHASES and not service._plot_in_flight,  # noqa: SLF001
        timeout_ms=timeout_ms,
    )


def wait_for_plot_success(service: PlotterService, *, timeout_ms: int = 3000) -> None:
    wait_for_plot_finished(service, timeout_ms=timeout_ms)
    if service.plot_state.phase is not PlotPhase.SUCCEEDED:
        raise AssertionError(
            f"Expected plot success, got {service.plot_state.phase}: {service.plot_state.message}"
        )


def wait_for_safe_stop(service: PlotterService, *, timeout_ms: int = 5000) -> None:
    wait_until(lambda: not service._safe_stop_in_flight, timeout_ms=timeout_ms)  # noqa: SLF001


def wait_for_detect_calls(fake: object, minimum: int = 1, *, timeout_ms: int = 3000) -> None:
    wait_until(lambda: getattr(fake, "detect_calls", 0) >= minimum, timeout_ms=timeout_ms)
