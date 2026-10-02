"""Persistent plot settings via Qt QSettings."""

from __future__ import annotations

from PySide6.QtCore import QObject, QSettings, Signal

from plotpilot.models.plot_settings import (
    REORDERING_STRICT,
    PlotSettings,
    PlotSettingsValidationError,
)
from plotpilot.models.print_margins import PrintMargins, PrintMarginsError
from plotpilot.services.preview_work_area import FallbackWorkArea, WorkAreaOrientation

ORGANIZATION = "PlotPilot"
APPLICATION = "PlotPilot"

_KEY_PREVIEW_FALLBACK = "preview/fallback_work_area"
_KEY_PREVIEW_FALLBACK_ORIENTATION = "preview/fallback_work_area_orientation"
_KEY_MARGIN_HORIZONTAL = "print/margin_horizontal_mm"
_KEY_MARGIN_VERTICAL = "print/margin_vertical_mm"
_KEY_PEN_DOWN = "plot/pen_down_speed"
_KEY_PEN_UP = "plot/pen_up_speed"
_KEY_ACCEL = "plot/acceleration"
_KEY_MODEL = "plot/model"
_KEY_PATH_REORDERING = "plot/path_reordering"
_KEY_PEN_POS_UP = "plot/pen_pos_up"
_KEY_PEN_POS_DOWN = "plot/pen_pos_down"
_KEY_CONST_SPEED = "plot/const_speed"
_PATH_ORDER_DRIVER = "driver"


def open_settings_store(organization: str, application: str) -> QSettings:
    """Open the user-scope store for *organization*/*application*.

    Uses ``QSettings.defaultFormat()`` explicitly: on PySide6 the two-argument
    constructor ignores ``setDefaultFormat`` and always picks the native
    backend, which tests cannot redirect. In production the default format is
    native, so the file is the same as ``QSettings(organization, application)``.
    """
    return QSettings(
        QSettings.defaultFormat(),
        QSettings.Scope.UserScope,
        organization,
        application,
    )


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
        self._settings = open_settings_store(organization, application)
        self._current = self._load()
        self._project_session_active = False
        self._session_fallback: FallbackWorkArea | None = None
        self._session_fallback_orientation: WorkAreaOrientation | None = None
        self._session_margins: PrintMargins | None = None

    @property
    def plot_settings(self) -> PlotSettings:
        return self._current

    @property
    def preview_fallback_work_area(self) -> FallbackWorkArea:
        if self._session_fallback is not None:
            return self._session_fallback
        return self._load_fallback_work_area()

    @property
    def preview_fallback_work_area_orientation(self) -> WorkAreaOrientation:
        if self._session_fallback_orientation is not None:
            return self._session_fallback_orientation
        return self._load_fallback_work_area_orientation()

    @property
    def print_margins(self) -> PrintMargins:
        if self._session_margins is not None:
            return self._session_margins
        return self._load_print_margins()

    @property
    def project_session_active(self) -> bool:
        return self._project_session_active

    def set_print_margins(self, margins: PrintMargins) -> None:
        """Store margins on the project session, or in QSettings for a plain SVG."""
        margins.validate()
        if self._project_session_active:
            self._session_margins = margins
            return
        self._settings.setValue(_KEY_MARGIN_HORIZONTAL, margins.horizontal_mm)
        self._settings.setValue(_KEY_MARGIN_VERTICAL, margins.vertical_mm)
        self._settings.sync()

    def set_preview_fallback_work_area(self, value: FallbackWorkArea) -> None:
        if self._project_session_active:
            self._session_fallback = value
            return
        self._settings.setValue(_KEY_PREVIEW_FALLBACK, value.value)
        self._settings.sync()

    def set_preview_fallback_work_area_orientation(self, value: WorkAreaOrientation) -> None:
        if self._project_session_active:
            self._session_fallback_orientation = value
            return
        self._settings.setValue(_KEY_PREVIEW_FALLBACK_ORIENTATION, value.value)
        self._settings.sync()

    def begin_project_session(
        self,
        settings: PlotSettings,
        fallback: FallbackWorkArea,
        fallback_orientation: WorkAreaOrientation = WorkAreaOrientation.PORTRAIT,
        print_margins: PrintMargins | None = None,
    ) -> None:
        """Apply project-owned settings without writing global QSettings."""
        settings.validate()
        margins = self.print_margins if print_margins is None else print_margins
        margins.validate()
        self._project_session_active = True
        self._session_fallback = fallback
        self._session_fallback_orientation = fallback_orientation
        self._session_margins = margins
        self._current = settings
        self.settings_changed.emit(settings)

    def end_project_session(self) -> None:
        """Return to global QSettings-backed plot settings, fallback, and margins."""
        self._project_session_active = False
        self._session_fallback = None
        self._session_fallback_orientation = None
        self._session_margins = None
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

    def _load_print_margins(self) -> PrintMargins:
        if not self._settings.contains(_KEY_MARGIN_HORIZONTAL) and not self._settings.contains(
            _KEY_MARGIN_VERTICAL
        ):
            return PrintMargins()
        horizontal = _read_optional_float(self._settings, _KEY_MARGIN_HORIZONTAL, default=10.0)
        vertical = _read_optional_float(self._settings, _KEY_MARGIN_VERTICAL, default=10.0)
        margins = PrintMargins(horizontal_mm=horizontal, vertical_mm=vertical)
        try:
            margins.validate()
        except PrintMarginsError:
            self._settings.remove(_KEY_MARGIN_HORIZONTAL)
            self._settings.remove(_KEY_MARGIN_VERTICAL)
            self._settings.sync()
            return PrintMargins()
        return margins

    def _load_fallback_work_area_orientation(self) -> WorkAreaOrientation:
        if not self._settings.contains(_KEY_PREVIEW_FALLBACK_ORIENTATION):
            return WorkAreaOrientation.PORTRAIT
        raw = self._settings.value(_KEY_PREVIEW_FALLBACK_ORIENTATION)
        if raw == WorkAreaOrientation.LANDSCAPE.value:
            return WorkAreaOrientation.LANDSCAPE
        return WorkAreaOrientation.PORTRAIT


def _read_optional_float(store: QSettings, key: str, *, default: float) -> float:
    if not store.contains(key):
        return default
    value = store.value(key)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


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
