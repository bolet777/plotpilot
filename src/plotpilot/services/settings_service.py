"""Persistent plot settings via Qt QSettings."""

from __future__ import annotations

from PySide6.QtCore import QObject, QSettings, Signal

from plotpilot.models.plot_settings import (
    REORDERING_STRICT,
    PlotSettings,
    PlotSettingsValidationError,
)
from plotpilot.services.preview_work_area import FallbackWorkArea

ORGANIZATION = "PlotPilot"
APPLICATION = "PlotPilot"

_KEY_PREVIEW_FALLBACK = "preview/fallback_work_area"
_KEY_PEN_DOWN = "plot/pen_down_speed"
_KEY_PEN_UP = "plot/pen_up_speed"
_KEY_ACCEL = "plot/acceleration"
_KEY_MODEL = "plot/model"
_KEY_PATH_REORDERING = "plot/path_reordering"
_KEY_PEN_POS_UP = "plot/pen_pos_up"
_KEY_PEN_POS_DOWN = "plot/pen_pos_down"
_KEY_CONST_SPEED = "plot/const_speed"
_PATH_ORDER_DRIVER = "driver"


class SettingsService(QObject):
    """Loads and saves PlotSettings; emits when values change."""

    settings_changed = Signal(object)

    def __init__(
        self,
        *,
        organization: str = ORGANIZATION,
        application: str = APPLICATION,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._organization = organization
        self._application = application
        self._settings = QSettings(organization, application)
        self._current = self._load()
        self._project_session_active = False
        self._session_fallback: FallbackWorkArea | None = None

    @property
    def plot_settings(self) -> PlotSettings:
        return self._current

    @property
    def preview_fallback_work_area(self) -> FallbackWorkArea:
        if self._session_fallback is not None:
            return self._session_fallback
        return self._load_fallback_work_area()

    @property
    def project_session_active(self) -> bool:
        return self._project_session_active

    def set_preview_fallback_work_area(self, value: FallbackWorkArea) -> None:
        if self._project_session_active:
            self._session_fallback = value
            return
        self._settings.setValue(_KEY_PREVIEW_FALLBACK, value.value)
        self._settings.sync()

    def begin_project_session(
        self,
        settings: PlotSettings,
        fallback: FallbackWorkArea,
    ) -> None:
        """Apply project-owned settings without writing global QSettings."""
        settings.validate()
        self._project_session_active = True
        self._session_fallback = fallback
        self._current = settings
        self.settings_changed.emit(settings)

    def end_project_session(self) -> None:
        """Return to global QSettings-backed plot settings and fallback."""
        self._project_session_active = False
        self._session_fallback = None
        self._current = self._load()
        self.settings_changed.emit(self._current)

    def replace(self, settings: PlotSettings) -> None:
        settings.validate()
        self._current = settings
        if not self._project_session_active:
            self._persist(settings)
        self.settings_changed.emit(settings)

    def reset_plot_settings(self) -> None:
        if self._project_session_active:
            self._current = PlotSettings()
            self.settings_changed.emit(self._current)
            return
        self._settings.remove(_KEY_PEN_DOWN)
        self._settings.remove(_KEY_PEN_UP)
        self._settings.remove(_KEY_ACCEL)
        self._settings.remove(_KEY_MODEL)
        self._settings.remove(_KEY_PATH_REORDERING)
        self._settings.remove(_KEY_PEN_POS_UP)
        self._settings.remove(_KEY_PEN_POS_DOWN)
        self._settings.remove(_KEY_CONST_SPEED)
        self._settings.sync()
        self._current = PlotSettings()
        self.settings_changed.emit(self._current)

    def _load(self) -> PlotSettings:
        pen_down = _read_optional_int(self._settings, _KEY_PEN_DOWN)
        pen_up = _read_optional_int(self._settings, _KEY_PEN_UP)
        accel = _read_optional_int(self._settings, _KEY_ACCEL)
        model = _read_optional_int(self._settings, _KEY_MODEL)
        path_reordering = _read_path_reordering(self._settings)
        pen_pos_up = _read_optional_int(self._settings, _KEY_PEN_POS_UP)
        pen_pos_down = _read_optional_int(self._settings, _KEY_PEN_POS_DOWN)
        const_speed = _read_bool(self._settings, _KEY_CONST_SPEED)
        settings = PlotSettings(
            pen_down_speed=pen_down,
            pen_up_speed=pen_up,
            acceleration=accel,
            model=model,
            path_reordering=path_reordering,
            pen_pos_up=pen_pos_up,
            pen_pos_down=pen_pos_down,
            const_speed=const_speed,
        )
        try:
            settings.validate()
        except PlotSettingsValidationError:
            self._clear_plot_keys()
            return PlotSettings()
        return settings

    def _persist(self, settings: PlotSettings) -> None:
        _write_optional_int(self._settings, _KEY_PEN_DOWN, settings.pen_down_speed)
        _write_optional_int(self._settings, _KEY_PEN_UP, settings.pen_up_speed)
        _write_optional_int(self._settings, _KEY_ACCEL, settings.acceleration)
        _write_optional_int(self._settings, _KEY_MODEL, settings.model)
        _write_path_reordering(self._settings, settings.path_reordering)
        _write_optional_int(self._settings, _KEY_PEN_POS_UP, settings.pen_pos_up)
        _write_optional_int(self._settings, _KEY_PEN_POS_DOWN, settings.pen_pos_down)
        _write_bool(self._settings, _KEY_CONST_SPEED, settings.const_speed)
        self._settings.sync()

    def _clear_plot_keys(self) -> None:
        self._settings.remove(_KEY_PEN_DOWN)
        self._settings.remove(_KEY_PEN_UP)
        self._settings.remove(_KEY_ACCEL)
        self._settings.remove(_KEY_MODEL)
        self._settings.remove(_KEY_PATH_REORDERING)
        self._settings.remove(_KEY_PEN_POS_UP)
        self._settings.remove(_KEY_PEN_POS_DOWN)
        self._settings.remove(_KEY_CONST_SPEED)
        self._settings.sync()

    def _load_fallback_work_area(self) -> FallbackWorkArea:
        if not self._settings.contains(_KEY_PREVIEW_FALLBACK):
            return FallbackWorkArea.A4
        raw = self._settings.value(_KEY_PREVIEW_FALLBACK)
        if raw == FallbackWorkArea.A3.value:
            return FallbackWorkArea.A3
        return FallbackWorkArea.A4


def _read_optional_int(store: QSettings, key: str) -> int | None:
    if not store.contains(key):
        return None
    value = store.value(key)
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _write_optional_int(store: QSettings, key: str, value: int | None) -> None:
    if value is None:
        store.remove(key)
    else:
        store.setValue(key, value)


def _read_path_reordering(store: QSettings) -> int | None:
    """Missing key is strict file order. ``driver`` omits ``-G``."""
    if not store.contains(_KEY_PATH_REORDERING):
        return REORDERING_STRICT
    raw = store.value(_KEY_PATH_REORDERING)
    if raw is None or raw == "" or raw == _PATH_ORDER_DRIVER:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return REORDERING_STRICT


def _write_path_reordering(store: QSettings, value: int | None) -> None:
    if value is None:
        store.setValue(_KEY_PATH_REORDERING, _PATH_ORDER_DRIVER)
    elif value == REORDERING_STRICT:
        store.remove(_KEY_PATH_REORDERING)
    else:
        store.setValue(_KEY_PATH_REORDERING, value)


def _read_bool(store: QSettings, key: str) -> bool:
    if not store.contains(key):
        return False
    value = store.value(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes"}
    return bool(value)


def _write_bool(store: QSettings, key: str, value: bool) -> None:
    if value:
        store.setValue(key, True)
    else:
        store.remove(key)
