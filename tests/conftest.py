"""Shared pytest hooks for Qt / plotter tests."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QCoreApplication, QThreadPool
from PySide6.QtWidgets import QApplication

from plotpilot.services.plotter_service import shutdown_all_plotter_services

_THREAD_POOL_DRAIN_MS = 5000


def _drain_qt_runtime() -> None:
    shutdown_all_plotter_services()
    application = QApplication.instance()
    if application is not None:
        for _ in range(20):
            application.processEvents()
    pool = QThreadPool.globalInstance()
    pool.waitForDone(_THREAD_POOL_DRAIN_MS)
    if application is not None:
        QCoreApplication.processEvents()


@pytest.fixture(autouse=True)
def _qt_plotter_hygiene() -> None:
    yield
    _drain_qt_runtime()


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    _drain_qt_runtime()
