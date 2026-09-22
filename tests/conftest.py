"""Shared pytest hooks for Qt / plotter tests."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication

from plotpilot.models.plotter_status import PlotterConnectionState, PlotterStatus
from plotpilot.plotter.fake import FakePlotterBackend
from plotpilot.services.plotter_service import shutdown_all_plotter_services
from plotpilot.ui.main_window import MainWindow

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

_THREAD_POOL_DRAIN_SECONDS = 0.2
_PLOT_EXIT_WAIT_SECONDS_TEST = 0.5
_TEST_AUTO_DETECT_INTERVAL_MS = 25
_TEST_AUTO_DETECT_RESUME_DELAY_MS = 15


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "hardware: requires a connected AxiDraw (opt-in only)")
    config.addinivalue_line(
        "markers",
        "slow: longer integration tests (exclude with -m 'not slow')",
    )


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--hardware",
        action="store_true",
        default=False,
        help="Run tests marked @pytest.mark.hardware (default: excluded)",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--hardware"):
        return
    skip_hardware = pytest.mark.skip(reason="hardware tests require: uv run pytest -m hardware")
    for item in items:
        if "hardware" in item.keywords:
            item.add_marker(skip_hardware)


def _close_visible_windows(application: QApplication) -> None:
    for widget in application.topLevelWidgets():
        widget.close()
    for _ in range(3):
        application.processEvents()


def _drain_qt_runtime(*, full: bool = False) -> None:
    application = QApplication.instance()
    if application is not None:
        _close_visible_windows(application)

    shutdown_all_plotter_services()

    pool = QThreadPool.globalInstance()
    if pool.activeThreadCount() == 0:
        if application is not None:
            application.processEvents()
        return

    deadline = time.monotonic() + (_THREAD_POOL_DRAIN_SECONDS if full else 0.15)
    while time.monotonic() < deadline:
        if pool.activeThreadCount() == 0:
            break
        if application is not None:
            application.processEvents()
        pool.waitForDone(1)

    if application is not None:
        application.processEvents()


@pytest.fixture(scope="session")
def qapp():
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    yield application


@pytest.fixture(autouse=True)
def _fast_plot_exit_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "plotpilot.services.plotter_service.PLOT_EXIT_WAIT_SECONDS",
        _PLOT_EXIT_WAIT_SECONDS_TEST,
    )


@pytest.fixture(autouse=True)
def _fast_plotter_monitor_intervals(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "plotpilot.services.plotter_service.AUTO_DETECT_INTERVAL_MS",
        _TEST_AUTO_DETECT_INTERVAL_MS,
    )
    monkeypatch.setattr(
        "plotpilot.services.plotter_service.AUTO_DETECT_RESUME_DELAY_MS",
        _TEST_AUTO_DETECT_RESUME_DELAY_MS,
    )


@pytest.fixture(autouse=True)
def _qt_plotter_hygiene() -> None:
    yield
    _drain_qt_runtime()


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    _drain_qt_runtime(full=True)


@pytest.fixture
def fake_plotter_backend() -> FakePlotterBackend:
    return FakePlotterBackend(
        detect_result=PlotterStatus(
            state=PlotterConnectionState.DISCONNECTED,
            message="Not connected",
        ),
    )


@pytest.fixture
def main_window(qapp, fake_plotter_backend: FakePlotterBackend) -> MainWindow:
    window = MainWindow(
        plotter_backend=fake_plotter_backend,
        svg_file_chooser=lambda: None,
    )
    yield window
    window.close()
    qapp.processEvents()


@pytest.fixture
def svg_file_chooser() -> Callable[[], str | None]:
    """Override in tests to simulate File → Open SVG without a modal dialog."""

    def _cancel() -> str | None:
        return None

    return _cancel
