"""SettingsService QSettings persistence."""

from __future__ import annotations

import uuid

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from plotpilot.models.plot_settings import REORDERING_BASIC, PlotSettings
from plotpilot.services.settings_service import SettingsService


@pytest.fixture(scope="session")
def qapp():
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    yield application


@pytest.fixture
def isolated_settings(qapp):
    org = f"PlotPilotTest-{uuid.uuid4().hex}"
    app = f"PlotPilotTest-{uuid.uuid4().hex}"
    service = SettingsService(organization=org, application=app)
    yield service
    QSettings(org, app).clear()


def test_persist_and_reload(isolated_settings: SettingsService) -> None:
    isolated_settings.replace(
        PlotSettings(pen_down_speed=33, pen_up_speed=44, acceleration=55, model=2),
    )
    reloaded = SettingsService(
        organization=isolated_settings._organization,  # noqa: SLF001
        application=isolated_settings._application,  # noqa: SLF001
    )
    assert reloaded.plot_settings == PlotSettings(
        pen_down_speed=33,
        pen_up_speed=44,
        acceleration=55,
        model=2,
    )


def test_startup_restores_saved_settings(isolated_settings: SettingsService) -> None:
    isolated_settings.replace(PlotSettings(acceleration=42))
    again = SettingsService(
        organization=isolated_settings._organization,  # noqa: SLF001
        application=isolated_settings._application,  # noqa: SLF001
    )
    assert again.plot_settings.acceleration == 42
    assert again.plot_settings.pen_down_speed is None


def test_reset_clears_overrides_and_storage(isolated_settings: SettingsService) -> None:
    isolated_settings.replace(PlotSettings(pen_down_speed=20, model=4))
    isolated_settings.reset_plot_settings()
    assert isolated_settings.plot_settings == PlotSettings()
    store = QSettings(
        isolated_settings._organization,  # noqa: SLF001
        isolated_settings._application,  # noqa: SLF001
    )
    assert not store.contains("plot/pen_down_speed")
    assert not store.contains("plot/model")


def test_path_reordering_persists(isolated_settings: SettingsService) -> None:
    isolated_settings.replace(PlotSettings(path_reordering=REORDERING_BASIC))
    reloaded = SettingsService(
        organization=isolated_settings._organization,  # noqa: SLF001
        application=isolated_settings._application,  # noqa: SLF001
    )
    assert reloaded.plot_settings.path_reordering == REORDERING_BASIC


def test_reset_clears_path_reordering(isolated_settings: SettingsService) -> None:
    isolated_settings.replace(PlotSettings(path_reordering=REORDERING_BASIC))
    isolated_settings.reset_plot_settings()
    store = QSettings(
        isolated_settings._organization,  # noqa: SLF001
        isolated_settings._application,  # noqa: SLF001
    )
    assert isolated_settings.plot_settings.path_reordering is None
    assert not store.contains("plot/path_reordering")
