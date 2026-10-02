"""Device tab: detected AxiDraw, connection state, manual pen/motor commands."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from plotpilot.models.plotter_status import PlotterConnectionState, PlotterStatus
from plotpilot.ui.top_bar import ConnectionDot, connection_label
from plotpilot.ui.widgets import make_card, make_wrapping_label


class DevicePanel(QWidget):
    """Presentation-only. The window wires the signals to ``PlotterService``."""

    refresh_requested = Signal()
    pen_up_requested = Signal()
    pen_down_requested = Signal()
    home_requested = Signal()
    motors_off_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        # ---- Connection -------------------------------------------------------
        self.refresh_button = QPushButton("Refresh", self)
        self.refresh_button.setProperty("role", "preset")
        self.refresh_button.setToolTip("Detect the AxiDraw again (axicli)")
        self.refresh_button.clicked.connect(self.refresh_requested)
        connection_card, connection_layout = make_card(
            "Connection",
            self,
            trailing=self.refresh_button,
        )
        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        self.connection_dot = ConnectionDot(self, diameter=9)
        status_row.addWidget(self.connection_dot)
        self.connection_state_label = QLabel("Not connected", self)
        self.connection_state_label.setProperty("role", "value")
        status_row.addWidget(self.connection_state_label)
        status_row.addStretch(1)
        connection_layout.addLayout(status_row)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(1, 1)
        self.device_value = self._info_row(grid, 0, "Device")
        self.model_value = self._info_row(grid, 1, "Model")
        self.firmware_value = self._info_row(grid, 2, "Driver / firmware")
        connection_layout.addLayout(grid)
        self.message_label = make_wrapping_label("", self, role="muted")
        connection_layout.addWidget(self.message_label)
        root.addWidget(connection_card)

        # ---- Manual control ------------------------------------------------
        manual_card, manual_layout = make_card(
            "Manual control",
            self,
            subtitle="(requires a connected AxiDraw)",
        )
        pen_row = QHBoxLayout()
        pen_row.setSpacing(8)
        self.pen_up_button = QPushButton("Pen Up", self)
        self.pen_up_button.clicked.connect(self.pen_up_requested)
        self.pen_down_button = QPushButton("Pen Down", self)
        self.pen_down_button.clicked.connect(self.pen_down_requested)
        for button in (self.pen_up_button, self.pen_down_button):
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            pen_row.addWidget(button)
        manual_layout.addLayout(pen_row)
        motor_row = QHBoxLayout()
        motor_row.setSpacing(8)
        self.home_button = QPushButton("Home", self)
        self.home_button.setToolTip(
            "Return to the position where the motors were enabled (walk_home). "
            "Does not lower the pen.",
        )
        self.home_button.clicked.connect(self.home_requested)
        self.motors_off_button = QPushButton("Motors Off", self)
        self.motors_off_button.setToolTip(
            "Disable the XY motors (disable_xy). Does not move the carriage or lower the pen.",
        )
        self.motors_off_button.clicked.connect(self.motors_off_requested)
        for button in (self.home_button, self.motors_off_button):
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            motor_row.addWidget(button)
        manual_layout.addLayout(motor_row)
        note = make_wrapping_label(
            "Commands run through axicli. Plotting and manual commands never overlap.",
            self,
            role="muted",
        )
        manual_layout.addWidget(note)
        root.addWidget(manual_card)

    def _info_row(self, grid: QGridLayout, row: int, caption: str) -> QLabel:
        label = QLabel(caption, self)
        label.setProperty("role", "caption")
        grid.addWidget(label, row, 0)
        value = make_wrapping_label("—", self)
        grid.addWidget(value, row, 1)
        return value

    def apply_status(self, status: PlotterStatus, *, model_name: str) -> None:
        self.connection_dot.set_state(status.state)
        self.connection_state_label.setText(connection_label(status.state))
        self.device_value.setText(status.device_name or "AxiDraw")
        self.model_value.setText(model_name)
        self.firmware_value.setText(status.backend_version or "—")
        if status.state is PlotterConnectionState.CONNECTED and status.message:
            self.message_label.setText(status.message)
        else:
            self.message_label.setText(status.message or "")

    def set_manual_controls_enabled(self, enabled: bool) -> None:
        for button in (
            self.pen_up_button,
            self.pen_down_button,
            self.home_button,
            self.motors_off_button,
        ):
            button.setEnabled(enabled)

    def set_refresh_enabled(self, enabled: bool) -> None:
        self.refresh_button.setEnabled(enabled)
