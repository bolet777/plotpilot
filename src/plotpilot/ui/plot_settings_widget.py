"""Compact plot settings controls (Plot Settings tab of the properties panel)."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
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
from plotpilot.ui.widgets import make_card

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
_MODEL_TOOLTIP = (
    "AxiDraw model passed to axicli (-L). It defines the physical plot area used "
    "for the preview, clipping, and the page preflight."
)


class PlotSettingsWidget(QWidget):
    """Pen speeds, heights, path order, and model; persists via SettingsService."""

    user_changed = Signal()

    def __init__(
        self,
        settings_service: SettingsService,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = settings_service
        self._block_sync = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        # ---- Speed ----------------------------------------------------------
        speed_card, speed_layout = make_card("Speed", self, subtitle="(% of maximum)")
        speed_grid = self._grid()
        self._pen_down_slider, self._pen_down_value = self._add_slider_row(
            speed_grid,
            0,
            "Pen-down speed",
            REFERENCE_PEN_DOWN_SPEED,
        )
        self._pen_up_slider, self._pen_up_value = self._add_slider_row(
            speed_grid,
            1,
            "Pen-up speed",
            REFERENCE_PEN_UP_SPEED,
        )
        self._accel_slider, self._accel_value = self._add_slider_row(
            speed_grid,
            2,
            "Acceleration",
            REFERENCE_ACCELERATION,
            minimum=ACCEL_MIN,
            maximum=ACCEL_MAX,
        )
        speed_layout.addLayout(speed_grid)
        self._const_speed_checkbox = QCheckBox("Constant pen-down speed", self)
        self._const_speed_checkbox.setToolTip(_CONST_SPEED_TOOLTIP)
        self._const_speed_checkbox.toggled.connect(self._on_const_speed_toggled)
        speed_layout.addWidget(self._const_speed_checkbox)
        root.addWidget(speed_card)

        # ---- Pen positions ----------------------------------------------------
        pen_card, pen_layout = make_card("Pen height", self, subtitle="(servo position 0–100)")
        pen_grid = self._grid()
        self._pen_pos_up_slider, self._pen_pos_up_value = self._add_slider_row(
            pen_grid,
            0,
            "Pen-up position",
            REFERENCE_PEN_UP_POSITION,
            minimum=PEN_POS_MIN,
            maximum=PEN_POS_MAX,
            tooltip=f"Raised pen. {_PEN_POS_TOOLTIP} Driver default is typically 60.",
        )
        self._pen_pos_down_slider, self._pen_pos_down_value = self._add_slider_row(
            pen_grid,
            1,
            "Pen-down position",
            REFERENCE_PEN_DOWN_POSITION,
            minimum=PEN_POS_MIN,
            maximum=PEN_POS_MAX,
            tooltip=f"Lowered pen. {_PEN_POS_TOOLTIP} Driver default is typically 30.",
        )
        pen_layout.addLayout(pen_grid)
        root.addWidget(pen_card)

        # ---- Machine ----------------------------------------------------------
        machine_card, machine_layout = make_card("Machine", self)
        machine_grid = QGridLayout()
        machine_grid.setHorizontalSpacing(10)
        machine_grid.setVerticalSpacing(8)
        machine_grid.setColumnStretch(1, 1)
        model_label = QLabel("Model", self)
        model_label.setToolTip(_MODEL_TOOLTIP)
        machine_grid.addWidget(model_label, 0, 0)
        self._model_combo = QComboBox(self)
        self._model_combo.setToolTip(_MODEL_TOOLTIP)
        self._model_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon,
        )
        self._model_combo.setMinimumContentsLength(14)
        self._model_combo.addItem("Default (CLI)", None)
        for code in sorted(AXIDRAW_MODELS):
            self._model_combo.addItem(f"{AXIDRAW_MODELS[code]} ({code})", code)
        self._model_combo.currentIndexChanged.connect(self._on_model_changed)
        machine_grid.addWidget(self._model_combo, 0, 1)

        order_label = QLabel("Path order", self)
        order_label.setToolTip(_PATH_ORDER_TOOLTIP)
        machine_grid.addWidget(order_label, 1, 0)
        self._path_order_combo = QComboBox(self)
        self._path_order_combo.setToolTip(_PATH_ORDER_TOOLTIP)
        self._path_order_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon,
        )
        self._path_order_combo.setMinimumContentsLength(14)
        for value, label in PATH_ORDER_OPTIONS:
            self._path_order_combo.addItem(label, value)
        self._path_order_combo.currentIndexChanged.connect(self._on_path_order_changed)
        machine_grid.addWidget(self._path_order_combo, 1, 1)
        machine_layout.addLayout(machine_grid)
        root.addWidget(machine_card)

        # ---- Reset ------------------------------------------------------------
        self._reset_button = QPushButton("Reset to defaults", self)
        self._reset_button.setToolTip(
            "Clear every override so axicli uses its driver defaults (axidraw_conf.py).",
        )
        self._reset_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._reset_button.clicked.connect(self._on_reset)
        root.addWidget(self._reset_button)

        self._pen_down_slider.valueChanged.connect(self._on_pen_down_changed)
        self._pen_up_slider.valueChanged.connect(self._on_pen_up_changed)
        self._accel_slider.valueChanged.connect(self._on_accel_changed)
        self._pen_pos_up_slider.valueChanged.connect(self._on_pen_pos_up_changed)
        self._pen_pos_down_slider.valueChanged.connect(self._on_pen_pos_down_changed)

        self._service.settings_changed.connect(self._apply_settings)
        self._apply_settings(self._service.plot_settings)

    @staticmethod
    def _grid() -> QGridLayout:
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(1, 1)
        return grid

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
        name = QLabel(label, self)
        name.setProperty("role", "caption")
        if tooltip:
            name.setToolTip(tooltip)
        grid.addWidget(name, row * 2, 0, 1, 2)
        slider = QSlider(Qt.Orientation.Horizontal, self)
        slider.setMinimum(minimum)
        slider.setMaximum(maximum)
        slider.setValue(reference)
        if tooltip:
            slider.setToolTip(tooltip)
        value_label = QLabel(str(reference), self)
        value_label.setProperty("role", "value")
        value_label.setMinimumWidth(30)
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        grid.addWidget(value_label, row * 2, 2)
        grid.addWidget(slider, row * 2 + 1, 0, 1, 3)
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

    def current_model_name(self) -> str:
        """Human label for the selected model (used by the top bar / device tab)."""
        model = self._service.plot_settings.model
        if model is None:
            return "AxiDraw (Default CLI)"
        return AXIDRAW_MODELS.get(model, f"AxiDraw model {model}")
