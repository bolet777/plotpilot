"""Slider-based artwork transform controls (Transform tab of the properties panel).

Cards: Position (X/Y), Scale, Margins (+ plot/printable area), Orientation,
Reset All. The slider/limit math is unchanged from V1; only the layout moved.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSizePolicy,
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
from plotpilot.ui.theme import COLORS, scaled_font
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
from plotpilot.ui.widgets import make_card, make_wrapping_label

_NUMERIC_POSITION_MIN = -2000.0
_NUMERIC_POSITION_MAX = 2000.0

ORIENTATION_TOOLTIP = (
    "PlotPilot always passes axicli -N so the page keeps the orientation shown in the "
    "preview. axicli cannot force auto-rotate on from the command line, and the "
    "rotation direction is only a config-file setting, so the other options are "
    "not available."
)


class _AxisSlider(QSlider):
    """Horizontal slider that resets its axis on double-click."""

    double_clicked = Signal()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        super().mouseDoubleClickEvent(event)
        self.double_clicked.emit()


class MarginsDiagram(QWidget):
    """Tiny schematic of the plot area with the dashed printable inset and margin labels."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._work_w = 300.0
        self._work_h = 217.9
        self._margins = PrintMargins()
        self.setMinimumSize(96, 64)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedSize(92, 64)

    def set_geometry_mm(self, work_w: float, work_h: float, margins: PrintMargins) -> None:
        self._work_w = max(work_w, 1.0)
        self._work_h = max(work_h, 1.0)
        self._margins = margins
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        inset = 14.0
        avail = QRectF(self.rect()).adjusted(inset, inset, -inset, -inset)
        scale = min(avail.width() / self._work_w, avail.height() / self._work_h)
        w = self._work_w * scale
        h = self._work_h * scale
        x = avail.x() + (avail.width() - w) / 2
        y = avail.y() + (avail.height() - h) / 2
        outer = QRectF(x, y, w, h)
        painter.setPen(QPen(QColor(COLORS.text_secondary), 1.0))
        painter.setBrush(QColor(COLORS.paper))
        painter.drawRect(outer)
        mh = min(self._margins.horizontal_mm * scale, w / 2)
        mv = min(self._margins.vertical_mm * scale, h / 2)
        inner = outer.adjusted(mh, mv, -mh, -mv)
        pen = QPen(QColor(COLORS.printable_outline), 1.0, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if inner.width() > 0 and inner.height() > 0:
            painter.drawRect(inner)
        painter.setFont(scaled_font(painter.font(), -3.0, minimum=6.5))
        painter.setPen(QColor(COLORS.text_secondary))
        painter.drawText(
            QRectF(0, 0, self.width(), inset),
            int(Qt.AlignmentFlag.AlignCenter),
            f"{_fmt(self._margins.vertical_mm)} mm",
        )
        painter.save()
        painter.translate(inset / 2, self.height() / 2)
        painter.rotate(-90)
        painter.drawText(
            QRectF(-self.height() / 2, -inset / 2, self.height(), inset),
            int(Qt.AlignmentFlag.AlignCenter),
            f"{_fmt(self._margins.horizontal_mm)} mm",
        )
        painter.restore()
        painter.end()


class ArtworkTransformControls(QWidget):
    """X/Y/scale sliders with numeric fields, presets, margins, and reset actions."""

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
        self._margins_linked = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        # ---- Position -------------------------------------------------------
        position_card, position_layout = make_card(
            "Position",
            self,
            subtitle="(relative to printable area)",
        )
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(1, 1)
        self._x_slider, self._x_spin, self._reset_x = self._build_axis_row(grid, 0, "X")
        self._y_slider, self._y_spin, self._reset_y = self._build_axis_row(grid, 1, "Y")
        position_layout.addLayout(grid)
        root.addWidget(position_card)

        # ---- Scale ----------------------------------------------------------
        scale_card, scale_layout = make_card("Scale", self)
        scale_row = QHBoxLayout()
        scale_row.setSpacing(8)
        self._scale_slider = _AxisSlider(Qt.Orientation.Horizontal, self)
        self._scale_slider.setMinimum(0)
        self._scale_slider.setMaximum(scale_slider_maximum())
        self._scale_slider.setToolTip("Double-click to reset to 100 %")
        self._scale_slider.valueChanged.connect(self._on_scale_slider_changed)
        self._scale_slider.double_clicked.connect(self._on_reset_scale)
        scale_row.addWidget(self._scale_slider, stretch=1)

        self._scale_spin = QDoubleSpinBox(self)
        self._scale_spin.setRange(DEFAULT_SCALE_MIN * 100.0, DEFAULT_SCALE_MAX * 100.0)
        self._scale_spin.setDecimals(0)
        self._scale_spin.setSuffix(" %")
        self._scale_spin.setFixedWidth(72)
        self._scale_spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        # Show the identity scale before any document is loaded (instead of the range minimum).
        self._blocking = True
        try:
            self._scale_spin.setValue(100.0)
            self._scale_slider.setValue(percent_to_scale_slider(100.0))
        finally:
            self._blocking = False
        self._scale_spin.valueChanged.connect(self._on_scale_spin_changed)
        scale_row.addWidget(self._scale_spin)
        scale_layout.addLayout(scale_row)

        preset_row = QHBoxLayout()
        preset_row.setSpacing(6)
        self._preset_buttons: dict[float, QPushButton] = {}
        for pct in SCALE_PRESET_PERCENTS:
            button = QPushButton(f"{int(pct)} %", self)
            button.setProperty("role", "preset")
            button.setCheckable(True)
            button.setAutoExclusive(False)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.clicked.connect(lambda _checked=False, p=pct: self._apply_scale_preset(p))
            preset_row.addWidget(button)
            self._preset_buttons[pct] = button
        scale_layout.addLayout(preset_row)
        root.addWidget(scale_card)

        # ---- Margins --------------------------------------------------------
        self._link_button = QPushButton("⛓", self)
        self._link_button.setProperty("role", "tool")
        self._link_button.setCheckable(True)
        self._link_button.setToolTip("Link horizontal and vertical margins")
        self._link_button.toggled.connect(self._on_margins_link_toggled)
        margins_card, margins_layout = make_card(
            "Margins",
            self,
            subtitle="(not plotted)",
            trailing=self._link_button,
        )
        margins_grid = QGridLayout()
        margins_grid.setHorizontalSpacing(8)
        margins_grid.setVerticalSpacing(8)
        margins_grid.setColumnStretch(1, 1)
        margins_grid.addWidget(QLabel("Horizontal", self), 0, 0)
        self._margin_horizontal_slider = QSlider(Qt.Orientation.Horizontal, self)
        margins_grid.addWidget(self._margin_horizontal_slider, 0, 1)
        self._margin_horizontal = self._build_margin_spin()
        self._margin_horizontal.setToolTip(
            "Inset from the left and right edges of the machine work area.",
        )
        margins_grid.addWidget(self._margin_horizontal, 0, 2)
        margins_grid.addWidget(QLabel("Vertical", self), 1, 0)
        self._margin_vertical_slider = QSlider(Qt.Orientation.Horizontal, self)
        margins_grid.addWidget(self._margin_vertical_slider, 1, 1)
        self._margin_vertical = self._build_margin_spin()
        self._margin_vertical.setToolTip(
            "Inset from the top and bottom edges of the machine work area.",
        )
        margins_grid.addWidget(self._margin_vertical, 1, 2)
        margins_layout.addLayout(margins_grid)
        self._margin_horizontal_slider.valueChanged.connect(
            lambda value: self._on_margin_slider_changed(self._margin_horizontal, value),
        )
        self._margin_vertical_slider.valueChanged.connect(
            lambda value: self._on_margin_slider_changed(self._margin_vertical, value),
        )

        info = QFrame(self)
        info.setProperty("role", "info")
        info_frame_layout = QHBoxLayout(info)
        info_frame_layout.setContentsMargins(10, 8, 10, 8)
        info_frame_layout.setSpacing(10)
        info_text = QVBoxLayout()
        info_text.setSpacing(1)
        self._plot_area_label = make_wrapping_label("", self, role="caption")
        info_text.addWidget(self._plot_area_label)
        self._plot_area_size_label = make_wrapping_label("", self, role="value")
        info_text.addWidget(self._plot_area_size_label)
        info_text.addSpacing(4)
        self._printable_label = make_wrapping_label("Printable: —", self, role="value")
        self._printable_label.setToolTip(
            "Printable area after margins. Strokes are clipped to this rectangle before plotting.",
        )
        info_text.addWidget(self._printable_label)
        info_text.addStretch(1)
        info_frame_layout.addLayout(info_text, stretch=1)
        self._margins_diagram = MarginsDiagram(info)
        info_frame_layout.addWidget(
            self._margins_diagram,
            alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
        )
        margins_layout.addWidget(info)

        # Host for window-owned plot-area widgets (fallback work area, bounds status).
        self.work_area_slot = QVBoxLayout()
        self.work_area_slot.setContentsMargins(0, 0, 0, 0)
        self.work_area_slot.setSpacing(6)
        margins_layout.addLayout(self.work_area_slot)

        self._status_label = make_wrapping_label("", self, role="status-warn")
        self._status_label.setVisible(False)
        margins_layout.addWidget(self._status_label)
        root.addWidget(margins_card)

        # ---- Orientation ----------------------------------------------------
        orientation_card, orientation_layout = make_card("Orientation", self)
        orientation_card.setToolTip(ORIENTATION_TOOLTIP)
        self._orientation_preserved = QRadioButton("Preserved (no auto-rotate)", self)
        self._orientation_preserved.setChecked(True)
        self._orientation_preserved.setToolTip(ORIENTATION_TOOLTIP)
        orientation_layout.addWidget(self._orientation_preserved)
        self._orientation_unavailable: list[QRadioButton] = []
        for text in ("Auto-rotate to fit", "Rotate 90° CCW", "Rotate 90° CW"):
            option = QRadioButton(text, self)
            option.setEnabled(False)
            option.setToolTip("Not available: " + ORIENTATION_TOOLTIP)
            orientation_layout.addWidget(option)
            self._orientation_unavailable.append(option)
        orientation_note = make_wrapping_label(
            "The page keeps the orientation shown in the preview (axicli -N).",
            self,
            role="muted",
        )
        orientation_layout.addWidget(orientation_note)
        root.addWidget(orientation_card)

        # ---- Reset ----------------------------------------------------------
        self._reset_all = QPushButton("Reset All", self)
        self._reset_all.setToolTip(
            "Reset position and scale. Margins and plot settings are not changed.",
        )
        self._reset_all.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._reset_all.clicked.connect(self._on_reset_all)
        root.addWidget(self._reset_all)

        self._reset_x.clicked.connect(self._on_reset_x)
        self._reset_y.clicked.connect(self._on_reset_y)
        self._refresh_scale_presets()
        self.set_print_margins(PrintMargins())

    # ------------------------------------------------------------------ build
    def _build_axis_row(
        self,
        grid: QGridLayout,
        row: int,
        axis_label: str,
    ) -> tuple[_AxisSlider, QDoubleSpinBox, QPushButton]:
        label = QLabel(axis_label, self)
        label.setFixedWidth(14)
        grid.addWidget(label, row, 0)

        slider = _AxisSlider(Qt.Orientation.Horizontal, self)
        slider.setToolTip(f"Double-click to reset {axis_label} to 0 mm")
        slider.valueChanged.connect(
            lambda value, axis=axis_label: self._on_position_slider_changed(axis, value),
        )
        if axis_label == "X":
            slider.double_clicked.connect(self._on_reset_x)
        else:
            slider.double_clicked.connect(self._on_reset_y)
        grid.addWidget(slider, row, 1)

        spin = QDoubleSpinBox(self)
        spin.setRange(_NUMERIC_POSITION_MIN, _NUMERIC_POSITION_MAX)
        spin.setDecimals(1)
        spin.setSuffix(" mm")
        spin.setFixedWidth(82)
        spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        spin.valueChanged.connect(
            lambda _value, axis=axis_label: self._on_position_spin_changed(axis),
        )
        grid.addWidget(spin, row, 2)

        reset = QPushButton(f"Reset {axis_label}", self)
        reset.setProperty("role", "preset")
        grid.addWidget(reset, row, 3)
        return slider, spin, reset

    def _build_margin_spin(self) -> QDoubleSpinBox:
        spin = QDoubleSpinBox(self)
        spin.setRange(0.0, 1000.0)
        spin.setDecimals(1)
        spin.setSingleStep(1.0)
        spin.setSuffix(" mm")
        spin.setFixedWidth(82)
        spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        spin.setKeyboardTracking(True)
        spin.valueChanged.connect(self._on_margin_spin_changed)
        return spin

    # --------------------------------------------------------------- public
    def set_artwork_bounds(self, bounds: ArtworkBoundsMm) -> None:
        """Store unscaled document-mm artwork extent and recompute X/Y slider limits."""
        self._artwork_bounds = bounds
        self._refresh_position_slider_ranges()

    def set_work_area_dimensions(self, width_mm: float, height_mm: float) -> None:
        self._work_width_mm = width_mm
        self._work_height_mm = height_mm
        self._refresh_position_slider_ranges()
        self._refresh_margin_sliders()
        self._refresh_diagram()

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
        """Accepts the V1 ``"Plot area: <label> — W × H mm"`` string and splits it."""
        caption, size = _split_plot_area_text(text)
        self._plot_area_label.setText(caption)
        self._plot_area_size_label.setText(size)
        self._plot_area_size_label.setVisible(bool(size))

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
            self._refresh_margin_sliders()
            self._refresh_diagram()
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
            self._refresh_margin_sliders()
            self._refresh_diagram()
        finally:
            self._blocking = False
        if after != before:
            return after
        return None

    def set_status_lines(self, lines: list[str]) -> None:
        text = "\n".join(line for line in lines if line)
        self._status_label.setText(text)
        self._status_label.setVisible(bool(text))

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

    # ------------------------------------------------------------- internals
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

    def _refresh_margin_sliders(self) -> None:
        """Mirror margin spin values on 0.1 mm sliders (no signals)."""
        for spin, slider in (
            (self._margin_horizontal, self._margin_horizontal_slider),
            (self._margin_vertical, self._margin_vertical_slider),
        ):
            slider.blockSignals(True)
            try:
                slider.setMinimum(0)
                slider.setMaximum(max(1, int(round(spin.maximum() * 10))))
                slider.setValue(int(round(spin.value() * 10)))
            finally:
                slider.blockSignals(False)

    def _refresh_diagram(self) -> None:
        self._margins_diagram.set_geometry_mm(
            self._work_width_mm,
            self._work_height_mm,
            self.print_margins(),
        )

    def _emit_current_transform(self) -> None:
        if self._blocking:
            return
        transform = ArtworkTransform(
            x_mm=self._x_spin.value(),
            y_mm=self._y_spin.value(),
            scale=self._scale,
        )
        self.transform_changed.emit(transform)

    # ---------------------------------------------------------------- slots
    def _on_margin_slider_changed(self, spin: QDoubleSpinBox, value: int) -> None:
        if self._blocking:
            return
        spin.setValue(value / 10.0)

    def _on_margin_spin_changed(self, _value: float) -> None:
        if self._blocking:
            return
        if self._margins_linked:
            sender = self.sender()
            other = (
                self._margin_vertical
                if sender is self._margin_horizontal
                else self._margin_horizontal
            )
            if isinstance(sender, QDoubleSpinBox) and other.value() != sender.value():
                self._blocking = True
                try:
                    other.setValue(min(sender.value(), other.maximum()))
                finally:
                    self._blocking = False
        self._refresh_position_slider_ranges()
        self._refresh_margin_sliders()
        self._refresh_diagram()
        self.margins_changed.emit(self.print_margins())

    def _on_margins_link_toggled(self, checked: bool) -> None:
        self._margins_linked = checked
        self._link_button.setToolTip(
            "Margins are linked: editing one updates the other"
            if checked
            else "Link horizontal and vertical margins"
        )
        if checked and self._margin_horizontal.value() != self._margin_vertical.value():
            self._margin_vertical.setValue(
                min(self._margin_horizontal.value(), self._margin_vertical.maximum()),
            )

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


def _split_plot_area_text(text: str) -> tuple[str, str]:
    """Split ``"Plot area: AxiDraw … — 300 × 217.9 mm"`` into caption and size."""
    if not text:
        return "", ""
    body = text.removeprefix("Plot area: ")
    if " — " in body:
        name, size = body.rsplit(" — ", 1)
        return f"Plot area · {name}", size
    return "Plot area", body


def _fmt(value: float) -> str:
    if abs(value - round(value)) < 0.05:
        return str(int(round(value)))
    return f"{value:.1f}"
