"""Small Qt test utilities (avoid missing signals and long busy-waits)."""

from __future__ import annotations

import time
from collections.abc import Callable

from PySide6.QtCore import QCoreApplication
from PySide6.QtTest import QTest

from plotpilot.services.plotter_service import PlotterService


def wait_until(predicate: Callable[[], bool], *, timeout_ms: int = 3000) -> None:
    deadline = time.monotonic() + timeout_ms / 1000.0
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        if predicate():
            return
        QTest.qWait(5)
    raise AssertionError("Timed out waiting for condition")


def wait_for_safe_stop(service: PlotterService, *, timeout_ms: int = 5000) -> None:
    wait_until(lambda: not service._safe_stop_in_flight, timeout_ms=timeout_ms)  # noqa: SLF001
