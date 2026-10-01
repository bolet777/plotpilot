"""Compact plot settings controls."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QSlider,
    QWidget,
)

from plotpilot.models.plot_settings import (
    ACCEL_MAX,
    ACCEL_MIN,
    AXIDRAW_MODELS,
    PATH_ORDER_OPTIONS,
    PEN_POS_MAX,
    PEN_POS_MIN,
    REFERENCE_ACCELERATION,
    REFERENCE_PEN_DOWN_POSITION,
    REFERENCE_PEN_DOWN_SPEED,
    REFERENCE_PEN_UP_POSITION,
    REFERENCE_PEN_UP_SPEED,
    SPEED_MAX,
    SPEED_MIN,
    PlotSettings,
)
from plotpilot.services.settings_service import SettingsService

_PEN_POS_TOOLTIP = (
    "Servo position from 0 to 100, not a height in millimeters. "
    "Leave unchanged and use Reset to keep the driver default."
)
_CONST_SPEED_TOOLTIP = (
    "Constant pen-down speed (axicli -C). Drawing moves skip acceleration and "
    "deceleration, which can look smoother but is usually slower: the driver "
    "reduces the pen-down speed limit (0.4× in the default high-resolution mode). "
    "Off leaves the driver default, which is not constant speed."
)
_PATH_ORDER_TOOLTIP = (
    "How axicli orders paths (-G). Driver default omits the flag and uses "
    "axidraw_conf.py. Strict file order preserves the SVG. Basic reorder "
    "speeds travel without reversing paths. Full reorder may reverse paths."
)
_ORIENTATION_TOOLTIP = (
    "PlotPilot always passes axicli -N. Portrait pages stay in the same "
    "orientation as the preview. axicli cannot force auto-rotate on from the "
    "command line, and the rotation direction is only a config-file setting."
)


class PlotSettingsWidget(QGroupBox):
    """Pen speeds, heights, path order, and model; persists via SettingsService."""

    user_changed = Signal()

    def __init__(
        self,
        settings_service: SettingsService,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("Plot Settings", parent)
        self._service = settings_service
        self._block_sync = False

        grid = QGridLayout(self)
        row = 0

        self._pen_down_slider, self._pen_down_value = self._add_slider_row(
            grid,
            row,
            "Pen-down speed",
            REFERENCE_PEN_DOWN_SPEED,
        )
        row += 1
        self._pen_up_slider, self._pen_up_value = self._add_slider_row(
            grid,
            row,
            "Pen-up speed",
            REFERENCE_PEN_UP_SPEED,
        )
        row += 1
        self._accel_slider, self._accel_value = self._add_slider_row(
            grid,
            row,
            "Acceleration",
            REFERENCE_ACCELERATION,
            minimum=ACCEL_MIN,
            maximum=ACCEL_MAX,
        )
        row += 1
        self._pen_pos_up_slider, self._pen_pos_up_value = self._add_slider_row(
            grid,
            row,
            "Pen up position",
            REFERENCE_PEN_UP_POSITION,
            minimum=PEN_POS_MIN,
            maximum=PEN_POS_MAX,
            tooltip=f"Raised pen. {_PEN_POS_TOOLTIP} Driver default is typically 60.",
        )
        row += 1
        self._pen_pos_down_slider, self._pen_pos_down_value = self._add_slider_row(
            grid,
            row,
            "Pen down position",
            REFERENCE_PEN_DOWN_POSITION,
            minimum=PEN_POS_MIN,
            maximum=PEN_POS_MAX,
            tooltip=f"Lowered pen. {_PEN_POS_TOOLTIP} Driver default is typically 30.",
        )
        row += 1

        grid.addWidget(QLabel("Model"), row, 0)
        self._model_combo = QComboBox(self)
        self._model_combo.addItem("Default (CLI)", None)
        for code in sorted(AXIDRAW_MODELS):
            self._model_combo.addItem(f"{AXIDRAW_MODELS[code]} ({code})", code)
        self._model_combo.currentIndexChanged.connect(self._on_model_changed)
        grid.addWidget(self._model_combo, row, 1, 1, 2)
        row += 1

        grid.addWidget(QLabel("Path order"), row, 0)
        self._path_order_combo = QComboBox(self)
        self._path_order_combo.setToolTip(_PATH_ORDER_TOOLTIP)
        for value, label in PATH_ORDER_OPTIONS:
            self._path_order_combo.addItem(label, value)
        self._path_order_combo.currentIndexChanged.connect(self._on_path_order_changed)
        grid.addWidget(self._path_order_combo, row, 1, 1, 2)
        row += 1

        self._const_speed_checkbox = QCheckBox("Constant pen-down speed", self)
        self._const_speed_checkbox.setToolTip(_CONST_SPEED_TOOLTIP)
        self._const_speed_checkbox.toggled.connect(self._on_const_speed_toggled)
        grid.addWidget(self._const_speed_checkbox, row, 0, 1, 3)
        row += 1

        self._orientation_label = QLabel("Orientation: preserved (no auto-rotate)", self)
        self._orientation_label.setToolTip(_ORIENTATION_TOOLTIP)
        self._orientation_label.setWordWrap(True)
        grid.addWidget(self._orientation_label, row, 0, 1, 3)
        row += 1

        self._reset_button = QPushButton("Reset to defaults", self)
        self._reset_button.clicked.connect(self._on_reset)
        grid.addWidget(self._reset_button, row, 0, 1, 3)

        self._pen_down_slider.valueChanged.connect(self._on_pen_down_changed)
        self._pen_up_slider.valueChanged.connect(self._on_pen_up_changed)
        self._accel_slider.valueChanged.connect(self._on_accel_changed)
        self._pen_pos_up_slider.valueChanged.connect(self._on_pen_pos_up_changed)
        self._pen_pos_down_slider.valueChanged.connect(self._on_pen_pos_down_changed)

        self._service.settings_changed.connect(self._apply_settings)
        self._apply_settings(self._service.plot_settings)

    def _add_slider_row(
        self,
        grid: QGridLayout,
        row: int,
        label: str,
        reference: int,
        *,
        minimum: int = SPEED_MIN,
        maximum: int = SPEED_MAX,
        tooltip: str | None = None,
    ) -> tuple[QSlider, QLabel]:
        name = QLabel(label)
        if tooltip:
            name.setToolTip(tooltip)
        grid.addWidget(name, row, 0)
        slider = QSlider(Qt.Orientation.Horizontal, self)
        slider.setMinimum(minimum)
        slider.setMaximum(maximum)
        slider.setValue(reference)
        if tooltip:
            slider.setToolTip(tooltip)
        value_label = QLabel(str(reference), self)
        value_label.setMinimumWidth(28)
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        grid.addWidget(slider, row, 1)
        grid.addWidget(value_label, row, 2)
        return slider, value_label

    def _apply_settings(self, settings: PlotSettings) -> None:
        self._block_sync = True
        try:
            self._set_slider(
                self._pen_down_slider,
                self._pen_down_value,
                settings.pen_down_speed,
                reference=REFERENCE_PEN_DOWN_SPEED,
            )
            self._set_slider(
                self._pen_up_slider,
                self._pen_up_value,
                settings.pen_up_speed,
                reference=REFERENCE_PEN_UP_SPEED,
            )
            self._set_slider(
                self._accel_slider,
                self._accel_value,
                settings.acceleration,
                reference=REFERENCE_ACCELERATION,
            )
            self._set_slider(
                self._pen_pos_up_slider,
                self._pen_pos_up_value,
                settings.pen_pos_up,
                reference=REFERENCE_PEN_UP_POSITION,
            )
            self._set_slider(
                self._pen_pos_down_slider,
                self._pen_pos_down_value,
                settings.pen_pos_down,
                reference=REFERENCE_PEN_DOWN_POSITION,
            )
            self._set_model(settings.model)
            self._set_path_order(settings.path_reordering)
            self._const_speed_checkbox.blockSignals(True)
            self._const_speed_checkbox.setChecked(settings.const_speed)
            self._const_speed_checkbox.blockSignals(False)
        finally:
            self._block_sync = False

    def _set_slider(
        self,
        slider: QSlider,
        value_label: QLabel,
        override: int | None,
        *,
        reference: int,
    ) -> None:
        display = override if override is not None else reference
        slider.blockSignals(True)
        slider.setValue(display)
        slider.blockSignals(False)
        value_label.setText(str(display))

    def _set_model(self, model: int | None) -> None:
        self._model_combo.blockSignals(True)
        if model is None:
            self._model_combo.setCurrentIndex(0)
        else:
            index = self._model_combo.findData(model)
            if index >= 0:
                self._model_combo.setCurrentIndex(index)
        self._model_combo.blockSignals(False)

    def _set_path_order(self, path_reordering: int | None) -> None:
        self._path_order_combo.blockSignals(True)
        index = self._path_order_combo.findData(path_reordering)
        if index < 0:
            index = 0
        self._path_order_combo.setCurrentIndex(index)
        self._path_order_combo.blockSignals(False)

    def _on_pen_down_changed(self, value: int) -> None:
        if self._block_sync:
            return
        self._pen_down_value.setText(str(value))
        self._commit(pen_down_speed=value)

    def _on_pen_up_changed(self, value: int) -> None:
        if self._block_sync:
            return
        self._pen_up_value.setText(str(value))
        self._commit(pen_up_speed=value)

    def _on_accel_changed(self, value: int) -> None:
        if self._block_sync:
            return
        self._accel_value.setText(str(value))
        self._commit(acceleration=value)

    def _on_pen_pos_up_changed(self, value: int) -> None:
        if self._block_sync:
            return
        self._pen_pos_up_value.setText(str(value))
        self._commit(pen_pos_up=value)

    def _on_pen_pos_down_changed(self, value: int) -> None:
        if self._block_sync:
            return
        self._pen_pos_down_value.setText(str(value))
        self._commit(pen_pos_down=value)

    def _on_model_changed(self, _index: int) -> None:
        if self._block_sync:
            return
        self._commit(model=self._model_combo.currentData())

    def _on_path_order_changed(self, _index: int) -> None:
        if self._block_sync:
            return
        self._commit(path_reordering=self._path_order_combo.currentData())

    def _on_const_speed_toggled(self, checked: bool) -> None:
        if self._block_sync:
            return
        self._commit(const_speed=checked)

    def _commit(self, **changes: object) -> None:
        updated = replace(self._service.plot_settings, **changes)
        self._service.replace(updated)
        self.user_changed.emit()

    def _on_reset(self) -> None:
        self._service.reset_plot_settings()
        self.user_changed.emit()

    def set_plotting_active(self, active: bool) -> None:
        enabled = not active
        self._pen_down_slider.setEnabled(enabled)
        self._pen_up_slider.setEnabled(enabled)
        self._accel_slider.setEnabled(enabled)
        self._pen_pos_up_slider.setEnabled(enabled)
        self._pen_pos_down_slider.setEnabled(enabled)
        self._model_combo.setEnabled(enabled)
        self._path_order_combo.setEnabled(enabled)
        self._const_speed_checkbox.setEnabled(enabled)
        self._reset_button.setEnabled(enabled)
