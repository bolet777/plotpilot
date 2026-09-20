"""Shared pytest hooks for Qt / plotter tests."""

from __future__ import annotations

import time

import pytest
from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication

from plotpilot.services.plotter_service import shutdown_all_plotter_services

_THREAD_POOL_DRAIN_SECONDS = 5.0


def _close_visible_windows(application: QApplication) -> None:
    for widget in application.topLevelWidgets():
        if widget.isVisible():
            widget.close()
    for _ in range(5):
        application.processEvents()


def _drain_qt_runtime() -> None:
    application = QApplication.instance()
    if application is not None:
        _close_visible_windows(application)

    shutdown_all_plotter_services()

    pool = QThreadPool.globalInstance()
    deadline = time.monotonic() + _THREAD_POOL_DRAIN_SECONDS
    while time.monotonic() < deadline:
        if pool.activeThreadCount() == 0:
            break
        if application is not None:
            application.processEvents()
        pool.waitForDone(50)

    if application is not None:
        application.processEvents()


@pytest.fixture(autouse=True)
def _qt_plotter_hygiene() -> None:
    yield
    _drain_qt_runtime()


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    _drain_qt_runtime()
