"""Slider-based artwork transform controls for the preview column."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from plotpilot.models.artwork_transform import (
    DEFAULT_SCALE_MAX,
    DEFAULT_SCALE_MIN,
    ArtworkTransform,
    scale_percent,
    transform_from_scale_percent,
)
from plotpilot.models.print_margins import PrintMargins, PrintMarginsError, printable_area_for
from plotpilot.ui.transform_slider_mapping import (
    SCALE_PRESET_PERCENTS,
    ArtworkBoundsMm,
    axis_translation_limits,
    mm_to_position_slider,
    percent_to_scale_slider,
    position_slider_maximum,
    position_slider_to_mm,
    preset_matches_scale,
    preset_visible,
    scale_slider_maximum,
    scale_slider_to_percent,
)

_NUMERIC_POSITION_MIN = -2000.0
_NUMERIC_POSITION_MAX = 2000.0


class _AxisSlider(QSlider):
    """Horizontal slider that resets its axis on double-click."""

    double_clicked = Signal()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        super().mouseDoubleClickEvent(event)
        self.double_clicked.emit()


class ArtworkTransformControls(QWidget):
    """X/Y/scale sliders with numeric fields, presets, and reset actions."""

    transform_changed = Signal(ArtworkTransform)
    margins_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._work_width_mm = 300.0
        self._work_height_mm = 217.9
        self._artwork_bounds = ArtworkBoundsMm.origin_point()
        self._x_min_mm = 0.0
        self._x_max_mm = 0.0
        self._y_min_mm = 0.0
        self._y_max_mm = 0.0
        self._x_slider_min_mm = 0.0
        self._x_slider_max_mm = 0.0
        self._y_slider_min_mm = 0.0
        self._y_slider_max_mm = 0.0
        self._scale = 1.0
        self._blocking = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        position_heading = QLabel("POSITION", self)
        position_heading.setStyleSheet("font-weight: bold;")
        root.addWidget(position_heading)

        self._x_slider, self._x_spin, self._reset_x = self._build_axis_row(root, "X")
        self._y_slider, self._y_spin, self._reset_y = self._build_axis_row(root, "Y")

        scale_heading = QLabel("SCALE", self)
        scale_heading.setStyleSheet("font-weight: bold;")
        root.addWidget(scale_heading)

        scale_row = QHBoxLayout()
        self._scale_slider = _AxisSlider(Qt.Orientation.Horizontal, self)
        self._scale_slider.setMinimum(0)
        self._scale_slider.setMaximum(scale_slider_maximum())
        self._scale_slider.valueChanged.connect(self._on_scale_slider_changed)
        self._scale_slider.double_clicked.connect(self._on_reset_scale)
        scale_row.addWidget(self._scale_slider, stretch=1)

        self._scale_spin = QDoubleSpinBox(self)
        self._scale_spin.setRange(DEFAULT_SCALE_MIN * 100.0, DEFAULT_SCALE_MAX * 100.0)
        self._scale_spin.setDecimals(0)
        self._scale_spin.setSuffix(" %")
        self._scale_spin.setFixedWidth(72)
        self._scale_spin.valueChanged.connect(self._on_scale_spin_changed)
        scale_row.addWidget(self._scale_spin)
        root.addLayout(scale_row)

        preset_row = QHBoxLayout()
        preset_row.addStretch(1)
        self._preset_buttons: dict[float, QPushButton] = {}
        for pct in SCALE_PRESET_PERCENTS:
            button = QPushButton(f"{int(pct)} %", self)
            button.setCheckable(True)
            button.setAutoExclusive(False)
            button.clicked.connect(lambda _checked=False, p=pct: self._apply_scale_preset(p))
            preset_row.addWidget(button)
            self._preset_buttons[pct] = button
        preset_row.addStretch(1)
        root.addLayout(preset_row)

        separator = QFrame(self)
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        root.addWidget(separator)

        footer = QHBoxLayout()
        self._plot_area_label = QLabel("", self)
        self._plot_area_label.setWordWrap(True)
        footer.addWidget(self._plot_area_label, stretch=1)
        self._reset_all = QPushButton("Reset All", self)
        self._reset_all.clicked.connect(self._on_reset_all)
        footer.addWidget(self._reset_all)
        root.addLayout(footer)

        margin_row = QHBoxLayout()
        margin_row.setSpacing(6)
        margin_row.addWidget(QLabel("Margins:", self))
        margin_row.addWidget(QLabel("H", self))
        self._margin_horizontal = self._build_margin_spin()
        self._margin_horizontal.setToolTip(
            "Inset from the left and right edges of the machine work area.",
        )
        margin_row.addWidget(self._margin_horizontal)
        margin_row.addWidget(QLabel("V", self))
        self._margin_vertical = self._build_margin_spin()
        self._margin_vertical.setToolTip(
            "Inset from the top and bottom edges of the machine work area.",
        )
        margin_row.addWidget(self._margin_vertical)
        margin_row.addStretch(1)
        root.addLayout(margin_row)

        self._printable_label = QLabel("Printable: —", self)
        self._printable_label.setWordWrap(True)
        root.addWidget(self._printable_label)

        self._status_label = QLabel("", self)
        self._status_label.setWordWrap(True)
        root.addWidget(self._status_label)

        self._reset_x.clicked.connect(self._on_reset_x)
        self._reset_y.clicked.connect(self._on_reset_y)
        self._refresh_scale_presets()
        self.set_print_margins(PrintMargins())

    def _build_axis_row(
        self,
        parent_layout: QVBoxLayout,
        axis_label: str,
    ) -> tuple[_AxisSlider, QDoubleSpinBox, QPushButton]:
        row = QHBoxLayout()
        label = QLabel(axis_label, self)
        label.setFixedWidth(16)
        row.addWidget(label)

        slider = _AxisSlider(Qt.Orientation.Horizontal, self)
        slider.valueChanged.connect(
            lambda value, axis=axis_label: self._on_position_slider_changed(axis, value),
        )
        if axis_label == "X":
            slider.double_clicked.connect(self._on_reset_x)
        else:
            slider.double_clicked.connect(self._on_reset_y)
        row.addWidget(slider, stretch=1)

        spin = QDoubleSpinBox(self)
        spin.setRange(_NUMERIC_POSITION_MIN, _NUMERIC_POSITION_MAX)
        spin.setDecimals(1)
        spin.setSuffix(" mm")
        spin.setFixedWidth(88)
        spin.valueChanged.connect(
            lambda _value, axis=axis_label: self._on_position_spin_changed(axis),
        )
        row.addWidget(spin)

        reset = QPushButton(f"Reset {axis_label}", self)
        row.addWidget(reset)
        parent_layout.addLayout(row)
        return slider, spin, reset

    def set_artwork_bounds(self, bounds: ArtworkBoundsMm) -> None:
        """Store unscaled document-mm artwork extent and recompute X/Y slider limits."""
        self._artwork_bounds = bounds
        self._refresh_position_slider_ranges()

    def set_work_area_dimensions(self, width_mm: float, height_mm: float) -> None:
        self._work_width_mm = width_mm
        self._work_height_mm = height_mm
        self._refresh_position_slider_ranges()

    def x_translation_limits(self) -> tuple[float, float]:
        """Calculated X travel ``(min_mm, max_mm)``, before expanding for the current value."""
        return self._x_min_mm, self._x_max_mm

    def y_translation_limits(self) -> tuple[float, float]:
        """Calculated Y travel ``(min_mm, max_mm)``, before expanding for the current value."""
        return self._y_min_mm, self._y_max_mm

    def x_slider_limits(self) -> tuple[float, float]:
        """X slider span, widened when the current translation sits outside the travel range."""
        return self._x_slider_min_mm, self._x_slider_max_mm

    def y_slider_limits(self) -> tuple[float, float]:
        """Y slider span, widened when the current translation sits outside the travel range."""
        return self._y_slider_min_mm, self._y_slider_max_mm

    def set_plot_area_text(self, text: str) -> None:
        self._plot_area_label.setText(text)

    def set_printable_text(self, text: str) -> None:
        self._printable_label.setText(text)

    def print_margins(self) -> PrintMargins:
        return PrintMargins(
            horizontal_mm=self._margin_horizontal.value(),
            vertical_mm=self._margin_vertical.value(),
        )

    def set_print_margins(self, margins: PrintMargins) -> None:
        self._blocking = True
        try:
            self._margin_horizontal.setValue(margins.horizontal_mm)
            self._margin_vertical.setValue(margins.vertical_mm)
            self._refresh_position_slider_ranges()
        finally:
            self._blocking = False

    def set_margin_ranges(
        self,
        max_horizontal_mm: float,
        max_vertical_mm: float,
    ) -> PrintMargins | None:
        """Limit each spin. Return the margins when a value was reduced to fit."""
        self._blocking = True
        try:
            before = self.print_margins()
            self._margin_horizontal.setMaximum(max(0.0, max_horizontal_mm))
            self._margin_vertical.setMaximum(max(0.0, max_vertical_mm))
            after = self.print_margins()
            self._refresh_position_slider_ranges()
        finally:
            self._blocking = False
        if after != before:
            return after
        return None

    def _build_margin_spin(self) -> QDoubleSpinBox:
        spin = QDoubleSpinBox(self)
        spin.setRange(0.0, 1000.0)
        spin.setDecimals(1)
        spin.setSingleStep(1.0)
        spin.setSuffix(" mm")
        spin.setFixedWidth(88)
        spin.setKeyboardTracking(True)
        spin.valueChanged.connect(self._on_margin_spin_changed)
        return spin

    def _on_margin_spin_changed(self, _value: float) -> None:
        if self._blocking:
            return
        self._refresh_position_slider_ranges()
        self.margins_changed.emit(self.print_margins())

    def set_status_lines(self, lines: list[str]) -> None:
        self._status_label.setText("\n".join(line for line in lines if line))

    def set_transform(self, transform: ArtworkTransform) -> None:
        self._blocking = True
        try:
            self._scale = transform.scale
            self._x_spin.setValue(transform.x_mm)
            self._y_spin.setValue(transform.y_mm)
            self._scale_spin.setValue(scale_percent(transform))
            self._refresh_position_slider_ranges()
            self._scale_slider.setValue(percent_to_scale_slider(self._scale_spin.value()))
            self._refresh_scale_presets()
        finally:
            self._blocking = False

    def _refresh_position_slider_ranges(self) -> None:
        """Recompute X/Y travel from bounds, scale, and the printable area.

        Does not change the spinbox values or emit ``transform_changed``.
        """
        if not self._recompute_translation_limits():
            return
        was_blocking = self._blocking
        self._blocking = True
        try:
            self._apply_axis_slider("X")
            self._apply_axis_slider("Y")
        finally:
            self._blocking = was_blocking

    def _recompute_translation_limits(self) -> bool:
        try:
            area = printable_area_for(
                self._work_width_mm,
                self._work_height_mm,
                self.print_margins(),
            )
            x_limits = axis_translation_limits(
                artwork_min_mm=self._artwork_bounds.min_x_mm,
                artwork_max_mm=self._artwork_bounds.max_x_mm,
                scale=self._scale,
                printable_min_mm=area.x_mm,
                printable_max_mm=area.x_max_mm,
            )
            y_limits = axis_translation_limits(
                artwork_min_mm=self._artwork_bounds.min_y_mm,
                artwork_max_mm=self._artwork_bounds.max_y_mm,
                scale=self._scale,
                printable_min_mm=area.y_mm,
                printable_max_mm=area.y_max_mm,
            )
        except (PrintMarginsError, ValueError):
            return False
        self._x_min_mm, self._x_max_mm = x_limits
        self._y_min_mm, self._y_max_mm = y_limits
        return True

    def _apply_axis_slider(self, axis: str) -> None:
        if axis == "X":
            slider = self._x_slider
            current = self._x_spin.value()
            calc_min, calc_max = self._x_min_mm, self._x_max_mm
        else:
            slider = self._y_slider
            current = self._y_spin.value()
            calc_min, calc_max = self._y_min_mm, self._y_max_mm
        shown_min = min(calc_min, current)
        shown_max = max(calc_max, current)
        if axis == "X":
            self._x_slider_min_mm = shown_min
            self._x_slider_max_mm = shown_max
        else:
            self._y_slider_min_mm = shown_min
            self._y_slider_max_mm = shown_max
        slider.blockSignals(True)
        try:
            slider.setMinimum(0)
            slider.setMaximum(position_slider_maximum(shown_min, shown_max))
            slider.setValue(mm_to_position_slider(current, shown_min, shown_max))
        finally:
            slider.blockSignals(False)

    def _sync_sliders_from_values(self) -> None:
        self._blocking = True
        try:
            self._apply_axis_slider("X")
            self._apply_axis_slider("Y")
            self._scale_slider.setValue(percent_to_scale_slider(self._scale_spin.value()))
        finally:
            self._blocking = False

    def _refresh_scale_presets(self) -> None:
        for pct, button in self._preset_buttons.items():
            visible = preset_visible(pct)
            button.setVisible(visible)
            button.setEnabled(visible)
            button.setChecked(preset_matches_scale(pct, self._scale))

    def _emit_current_transform(self) -> None:
        if self._blocking:
            return
        transform = ArtworkTransform(
            x_mm=self._x_spin.value(),
            y_mm=self._y_spin.value(),
            scale=self._scale,
        )
        self.transform_changed.emit(transform)

    def _on_position_slider_changed(self, axis: str, value: int) -> None:
        if self._blocking:
            return
        if axis == "X":
            min_mm, max_mm = self._x_slider_min_mm, self._x_slider_max_mm
        else:
            min_mm, max_mm = self._y_slider_min_mm, self._y_slider_max_mm
        mm = position_slider_to_mm(value, min_mm, max_mm)
        self._blocking = True
        try:
            if axis == "X":
                self._x_spin.setValue(mm)
            else:
                self._y_spin.setValue(mm)
        finally:
            self._blocking = False
        self._emit_current_transform()

    def _on_position_spin_changed(self, axis: str) -> None:
        if self._blocking:
            return
        self._sync_sliders_from_values()
        self._emit_current_transform()

    def _on_scale_slider_changed(self, value: int) -> None:
        if self._blocking:
            return
        percent = scale_slider_to_percent(value)
        self._blocking = True
        try:
            self._scale_spin.setValue(percent)
        finally:
            self._blocking = False
        self._apply_scale_percent(percent)

    def _on_scale_spin_changed(self, value: float) -> None:
        if self._blocking:
            return
        self._blocking = True
        try:
            self._scale_slider.setValue(percent_to_scale_slider(value))
        finally:
            self._blocking = False
        self._apply_scale_percent(value)

    def _apply_scale_preset(self, percent: float) -> None:
        self._blocking = True
        try:
            self._scale_spin.setValue(percent)
            self._scale_slider.setValue(percent_to_scale_slider(percent))
        finally:
            self._blocking = False
        self._apply_scale_percent(percent)

    def _apply_scale_percent(self, percent: float) -> None:
        if self._blocking:
            return
        current = ArtworkTransform(
            x_mm=self._x_spin.value(),
            y_mm=self._y_spin.value(),
            scale=self._scale,
        )
        try:
            scaled = transform_from_scale_percent(current, percent)
        except ValueError:
            return
        self._scale = scaled.scale
        self._refresh_position_slider_ranges()
        self._refresh_scale_presets()
        self._emit_current_transform()

    def _on_reset_x(self) -> None:
        self._blocking = True
        try:
            self._x_spin.setValue(0.0)
            self._apply_axis_slider("X")
        finally:
            self._blocking = False
        self._emit_current_transform()

    def _on_reset_y(self) -> None:
        self._blocking = True
        try:
            self._y_spin.setValue(0.0)
            self._apply_axis_slider("Y")
        finally:
            self._blocking = False
        self._emit_current_transform()

    def _on_reset_scale(self) -> None:
        self._apply_scale_preset(100.0)

    def _on_reset_all(self) -> None:
        self.set_transform(ArtworkTransform.identity())
        self.transform_changed.emit(ArtworkTransform.identity())
