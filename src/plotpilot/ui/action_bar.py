"""Persistent bottom action/status bar.

Row 1: status strip (document, activity, plotter message, estimate).
Row 2: plot progress (only while plotting).
Row 3: pen-change banner (only while a multi-layer job waits for a pen change).
Row 4: grouped controls — Plotter · Pen Control · Motors · Actions.

The bar owns the widgets; ``MainWindow`` binds them to services and keeps the
same attribute names as V1 (``_pen_up_button``, ``_plot_stop_button``, …).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from plotpilot.models.plotter_status import PlotterConnectionState
from plotpilot.ui.top_bar import ConnectionDot, connection_label
from plotpilot.ui.widgets import ElidedLabel, FlowLayout, make_group_label


class ActionBar(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("actionBar")
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 6, 12, 8)
        root.setSpacing(6)

        # ---- Status strip -----------------------------------------------------
        status_strip = QHBoxLayout()
        status_strip.setSpacing(14)
        self.status_label = ElidedLabel("", self)
        self.status_label.setProperty("role", "caption")
        self.status_label.setToolTip("Current document")
        status_strip.addWidget(self.status_label, stretch=3)
        self.activity_label = ElidedLabel("", self)
        self.activity_label.setProperty("role", "caption")
        status_strip.addWidget(self.activity_label, stretch=3)
        self.plotter_message_label = ElidedLabel("", self)
        self.plotter_message_label.setProperty("role", "muted")
        status_strip.addWidget(self.plotter_message_label, stretch=3)
        self.estimate_label = ElidedLabel("", self)
        self.estimate_label.setProperty("role", "caption")
        self.estimate_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        status_strip.addWidget(self.estimate_label, stretch=4)
        root.addLayout(status_strip)

        # ---- Progress ---------------------------------------------------------
        self.progress_row = QWidget(self)
        progress_layout = QHBoxLayout(self.progress_row)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(10)
        self.progress_headline = ElidedLabel("", self.progress_row)
        self.progress_headline.setProperty("role", "value")
        progress_layout.addWidget(self.progress_headline, stretch=2)
        self.progress_bar = QProgressBar(self.progress_row)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setMinimumWidth(160)
        progress_layout.addWidget(self.progress_bar, stretch=4)
        self.progress_timing = ElidedLabel("", self.progress_row)
        self.progress_timing.setProperty("role", "caption")
        progress_layout.addWidget(self.progress_timing, stretch=2)
        self.progress_next = ElidedLabel("", self.progress_row)
        self.progress_next.setProperty("role", "caption")
        progress_layout.addWidget(self.progress_next, stretch=2)
        root.addWidget(self.progress_row)

        # ---- Pen change banner ------------------------------------------------
        self.pen_change_banner = QFrame(self)
        self.pen_change_banner.setProperty("role", "banner")
        banner_layout = QHBoxLayout(self.pen_change_banner)
        banner_layout.setContentsMargins(12, 8, 12, 8)
        banner_layout.setSpacing(12)
        self.pen_change_label = QLabel("", self.pen_change_banner)
        self.pen_change_label.setWordWrap(True)
        banner_layout.addWidget(self.pen_change_label, stretch=1)
        self.continue_button = QPushButton("Continue", self.pen_change_banner)
        self.continue_button.setProperty("role", "accent")
        self.continue_button.setToolTip("Pen changed — plot the next layer")
        banner_layout.addWidget(self.continue_button, alignment=Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(self.pen_change_banner)

        # ---- Groups -------------------------------------------------------------
        self.groups_host = QWidget(self)
        host_policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        host_policy.setHeightForWidth(True)
        self.groups_host.setSizePolicy(host_policy)
        groups = FlowLayout(self.groups_host, h_spacing=0, v_spacing=8)

        plotter_group, plotter_row = self._group("Plotter")
        plotter_row.setSpacing(8)
        self.connection_dot = ConnectionDot(plotter_group, diameter=8)
        plotter_row.addWidget(self.connection_dot)
        self.plotter_status_label = QLabel("○ Not connected", plotter_group)
        self.plotter_status_label.setProperty("role", "status-error")
        plotter_row.addWidget(self.plotter_status_label)
        self.connect_button = QPushButton("Connect", plotter_group)
        self.connect_button.setProperty("role", "accent")
        self.connect_button.setToolTip("Detect the AxiDraw (axicli)")
        plotter_row.addWidget(self.connect_button)
        groups.addWidget(plotter_group)

        pen_group, pen_row = self._group("Pen Control")
        self.pen_up_button = QPushButton("Pen Up", pen_group)
        self.pen_down_button = QPushButton("Pen Down", pen_group)
        pen_row.addWidget(self.pen_up_button)
        pen_row.addWidget(self.pen_down_button)
        groups.addWidget(pen_group)

        motors_group, motors_row = self._group("Motors")
        self.home_button = QPushButton("Home", motors_group)
        self.home_button.setToolTip(
            "Return to the position where the motors were enabled (walk_home). "
            "Does not lower the pen.",
        )
        self.motors_off_button = QPushButton("Motors Off", motors_group)
        self.motors_off_button.setToolTip(
            "Disable the XY motors (disable_xy). Does not move the carriage or lower the pen.",
        )
        motors_row.addWidget(self.home_button)
        motors_row.addWidget(self.motors_off_button)
        groups.addWidget(motors_group)

        actions_group, actions_row = self._group("Actions")
        self.refresh_button = QPushButton("Refresh", actions_group)
        self.refresh_button.setToolTip("Detect the AxiDraw again (axicli)")
        actions_row.addWidget(self.refresh_button)
        self.plot_layer_button = QPushButton("Plot Selected Layer", actions_group)
        self.plot_layer_button.setProperty("role", "accent")
        actions_row.addWidget(self.plot_layer_button)
        self.plot_checked_button = QPushButton("Plot Checked Layers", actions_group)
        actions_row.addWidget(self.plot_checked_button)
        self.stop_button = QPushButton("Stop", actions_group)
        self.stop_button.setProperty("role", "danger")
        actions_row.addWidget(self.stop_button)
        self.estimate_button = QPushButton("Estimate", actions_group)
        self.estimate_button.setToolTip(
            "Estimate drawing time from the final clipped SVG (axicli -v -T). "
            "Pen-change pauses are not included.",
        )
        actions_row.addWidget(self.estimate_button)
        groups.addWidget(actions_group)
        root.addWidget(self.groups_host)

        self.progress_row.setVisible(False)
        self.pen_change_banner.setVisible(False)

    def _group(self, caption: str) -> tuple[QWidget, QHBoxLayout]:
        """Caption above a row of controls, with a separator line on the right."""
        host = QWidget(self.groups_host)
        outer = QHBoxLayout(host)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)
        column = QVBoxLayout()
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(4)
        column.addWidget(make_group_label(caption, host))
        row = QHBoxLayout()
        row.setSpacing(6)
        column.addLayout(row)
        outer.addLayout(column)
        line = QFrame(host)
        line.setFrameShape(QFrame.Shape.NoFrame)
        line.setFixedWidth(1)
        line.setStyleSheet("background-color: #2f2f33; border: none;")
        outer.addWidget(line)
        outer.addSpacing(0)
        return host, row

    def set_connection_state(self, state: PlotterConnectionState) -> None:
        self.connection_dot.set_state(state)
        label = connection_label(state)
        if state is PlotterConnectionState.CONNECTED:
            self.plotter_status_label.setText(f"● {label}")
            role = "status-ok"
        elif state is PlotterConnectionState.ERROR:
            self.plotter_status_label.setText(f"● {label}")
            role = "status-error"
        else:
            self.plotter_status_label.setText(f"○ {label}")
            role = "status-error"
        self.plotter_status_label.setProperty("role", role)
        style = self.plotter_status_label.style()
        if style is not None:
            style.unpolish(self.plotter_status_label)
            style.polish(self.plotter_status_label)
        self.connect_button.setText(
            "Reconnect" if state is PlotterConnectionState.CONNECTED else "Connect",
        )
