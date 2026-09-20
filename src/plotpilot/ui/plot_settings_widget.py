"""Compact plot settings controls."""

from __future__ import annotations

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
    REFERENCE_ACCELERATION,
    REFERENCE_PEN_DOWN_SPEED,
    REFERENCE_PEN_UP_SPEED,
    REORDERING_BASIC,
    SPEED_MAX,
    SPEED_MIN,
    PlotSettings,
)
from plotpilot.services.settings_service import SettingsService


class PlotSettingsWidget(QGroupBox):
    """Pen speeds, acceleration, and model; persists via SettingsService."""

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

        self._pen_down_slider, self._pen_down_value = self._add_speed_row(
            grid,
            row,
            "Pen-down speed",
            REFERENCE_PEN_DOWN_SPEED,
        )
        row += 1
        self._pen_up_slider, self._pen_up_value = self._add_speed_row(
            grid,
            row,
            "Pen-up speed",
            REFERENCE_PEN_UP_SPEED,
        )
        row += 1
        self._accel_slider, self._accel_value = self._add_speed_row(
            grid,
            row,
            "Acceleration",
            REFERENCE_ACCELERATION,
            minimum=ACCEL_MIN,
            maximum=ACCEL_MAX,
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

        self._optimize_checkbox = QCheckBox("Optimize path order", self)
        self._optimize_checkbox.setToolTip("Reorder SVG paths to reduce pen-up travel.")
        self._optimize_checkbox.toggled.connect(self._on_optimize_toggled)
        grid.addWidget(self._optimize_checkbox, row, 0, 1, 3)
        row += 1

        self._reset_button = QPushButton("Reset to defaults", self)
        self._reset_button.clicked.connect(self._on_reset)
        grid.addWidget(self._reset_button, row, 0, 1, 3)

        self._pen_down_slider.valueChanged.connect(self._on_pen_down_changed)
        self._pen_up_slider.valueChanged.connect(self._on_pen_up_changed)
        self._accel_slider.valueChanged.connect(self._on_accel_changed)

        self._service.settings_changed.connect(self._apply_settings)
        self._apply_settings(self._service.plot_settings)

    def _add_speed_row(
        self,
        grid: QGridLayout,
        row: int,
        label: str,
        reference: int,
        *,
        minimum: int = SPEED_MIN,
        maximum: int = SPEED_MAX,
    ) -> tuple[QSlider, QLabel]:
        grid.addWidget(QLabel(label), row, 0)
        slider = QSlider(Qt.Orientation.Horizontal, self)
        slider.setMinimum(minimum)
        slider.setMaximum(maximum)
        slider.setValue(reference)
        value_label = QLabel(str(reference), self)
        value_label.setMinimumWidth(28)
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        grid.addWidget(slider, row, 1)
        grid.addWidget(value_label, row, 2)
        return slider, value_label

    def _apply_settings(self, settings: PlotSettings) -> None:
        self._block_sync = True
        try:
            self._set_slider(self._pen_down_slider, self._pen_down_value, settings.pen_down_speed)
            self._set_slider(self._pen_up_slider, self._pen_up_value, settings.pen_up_speed)
            self._set_slider(self._accel_slider, self._accel_value, settings.acceleration)
            self._set_model(settings.model)
            self._optimize_checkbox.blockSignals(True)
            self._optimize_checkbox.setChecked(settings.optimize_path_order)
            self._optimize_checkbox.blockSignals(False)
        finally:
            self._block_sync = False

    def _set_slider(
        self,
        slider: QSlider,
        value_label: QLabel,
        override: int | None,
        *,
        reference: int | None = None,
    ) -> None:
        if reference is None:
            if slider is self._pen_down_slider:
                reference = REFERENCE_PEN_DOWN_SPEED
            elif slider is self._pen_up_slider:
                reference = REFERENCE_PEN_UP_SPEED
            else:
                reference = REFERENCE_ACCELERATION
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

    def _on_pen_down_changed(self, value: int) -> None:
        if self._block_sync:
            return
        self._pen_down_value.setText(str(value))
        self._commit_field(pen_down_speed=value)

    def _on_pen_up_changed(self, value: int) -> None:
        if self._block_sync:
            return
        self._pen_up_value.setText(str(value))
        self._commit_field(pen_up_speed=value)

    def _on_accel_changed(self, value: int) -> None:
        if self._block_sync:
            return
        self._accel_value.setText(str(value))
        self._commit_field(acceleration=value)

    def _on_model_changed(self, _index: int) -> None:
        if self._block_sync:
            return
        model = self._model_combo.currentData()
        current = self._service.plot_settings
        self._service.replace(
            PlotSettings(
                pen_down_speed=current.pen_down_speed,
                pen_up_speed=current.pen_up_speed,
                acceleration=current.acceleration,
                model=model,
                path_reordering=current.path_reordering,
            )
        )
        self.user_changed.emit()

    def _on_optimize_toggled(self, checked: bool) -> None:
        if self._block_sync:
            return
        current = self._service.plot_settings
        self._service.replace(
            PlotSettings(
                pen_down_speed=current.pen_down_speed,
                pen_up_speed=current.pen_up_speed,
                acceleration=current.acceleration,
                model=current.model,
                path_reordering=REORDERING_BASIC if checked else None,
            )
        )
        self.user_changed.emit()

    def _commit_field(self, **field: int) -> None:
        current = self._service.plot_settings
        updated = PlotSettings(
            pen_down_speed=field.get("pen_down_speed", current.pen_down_speed),
            pen_up_speed=field.get("pen_up_speed", current.pen_up_speed),
            acceleration=field.get("acceleration", current.acceleration),
            model=current.model,
            path_reordering=current.path_reordering,
        )
        self._service.replace(updated)
        self.user_changed.emit()

    def _on_reset(self) -> None:
        self._service.reset_plot_settings()
        self.user_changed.emit()

    def set_plotting_active(self, active: bool) -> None:
        self._pen_down_slider.setEnabled(not active)
        self._pen_up_slider.setEnabled(not active)
        self._accel_slider.setEnabled(not active)
        self._model_combo.setEnabled(not active)
        self._optimize_checkbox.setEnabled(not active)
        self._reset_button.setEnabled(not active)
