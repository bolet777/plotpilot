"""Compact application toolbar: identity, main navigation, and device chip."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from plotpilot.models.plotter_status import PlotterConnectionState
from plotpilot.resources.app_icon import application_icon
from plotpilot.ui.theme import COLORS


class ConnectionDot(QWidget):
    """Small colored circle reflecting the plotter connection state."""

    def __init__(self, parent: QWidget | None = None, *, diameter: int = 8) -> None:
        super().__init__(parent)
        self._diameter = diameter
        self._color = QColor(COLORS.text_muted)
        self.setFixedSize(diameter + 2, diameter + 2)

    def set_state(self, state: PlotterConnectionState) -> None:
        self._color = QColor(connection_color(state))
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._color)
        painter.drawEllipse(1, 1, self._diameter, self._diameter)
        painter.end()


def connection_color(state: PlotterConnectionState) -> str:
    if state is PlotterConnectionState.CONNECTED:
        return COLORS.success
    if state is PlotterConnectionState.ERROR:
        return COLORS.danger
    if state is PlotterConnectionState.DISCONNECTED:
        return COLORS.danger
    return COLORS.text_muted


def connection_label(state: PlotterConnectionState) -> str:
    if state is PlotterConnectionState.CONNECTED:
        return "Connected"
    if state is PlotterConnectionState.ERROR:
        return "Error"
    return "Not connected"


class ClickableFrame(QFrame):
    """Rounded frame that emits ``clicked`` on left-button release."""

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "#deviceChip {"
            f" background-color: {COLORS.raised}; border: 1px solid {COLORS.border};"
            " border-radius: 7px; }"
            "#deviceChip:hover { background-color: #3c3c40; }"
            "#deviceChip QLabel { background: transparent; }"
        )

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 — Qt API
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class TopBar(QWidget):
    """Top application bar.

    Signals map to window-level actions so the bar stays presentation-only.
    """

    open_requested = Signal()
    layers_toggled = Signal(bool)
    device_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("topBar")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 6, 12, 6)
        root.setSpacing(10)

        # Identity
        identity = QHBoxLayout()
        identity.setSpacing(8)
        icon_label = QLabel(self)
        icon_label.setPixmap(_app_pixmap(28))
        icon_label.setFixedSize(28, 28)
        identity.addWidget(icon_label)
        names = QVBoxLayout()
        names.setSpacing(0)
        names.setContentsMargins(0, 0, 0, 0)
        app_name = QLabel("PlotPilot", self)
        app_name.setProperty("role", "title")
        names.addWidget(app_name)
        tagline = QLabel("SVG to AxiDraw", self)
        tagline.setProperty("role", "muted")
        names.addWidget(tagline)
        identity.addLayout(names)
        root.addLayout(identity)

        root.addStretch(1)

        # Navigation
        nav_host = QFrame(self)
        nav_host.setObjectName("navHost")
        nav = QHBoxLayout(nav_host)
        nav.setContentsMargins(0, 0, 0, 0)
        nav.setSpacing(2)
        self.open_button = self._nav_button("Open", "Open an SVG file (⌘O)")
        self.open_button.setCheckable(False)
        self.open_button.clicked.connect(self.open_requested)
        nav.addWidget(self.open_button)

        self.layers_button = self._nav_button("Layers", "Show or hide the Layers sidebar")
        self.layers_button.setCheckable(True)
        self.layers_button.setChecked(True)
        self.layers_button.toggled.connect(self.layers_toggled)
        nav.addWidget(self.layers_button)
        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(False)
        root.addWidget(nav_host)

        root.addStretch(1)

        # Device chip
        self.device_chip = ClickableFrame(self)
        self.device_chip.setObjectName("deviceChip")
        self.device_chip.setToolTip("Device details")
        self.device_chip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.device_chip.clicked.connect(self.device_requested)
        chip_layout = QHBoxLayout(self.device_chip)
        chip_layout.setContentsMargins(10, 4, 12, 4)
        chip_layout.setSpacing(8)
        chip_icon = QLabel(self.device_chip)
        chip_icon.setText("⬚")
        chip_icon.setStyleSheet(f"font-size: 16px; color: {COLORS.text_secondary};")
        chip_layout.addWidget(chip_icon)
        chip_text = QVBoxLayout()
        chip_text.setSpacing(0)
        chip_text.setContentsMargins(0, 0, 0, 0)
        self.device_model_label = QLabel("AxiDraw", self.device_chip)
        self.device_model_label.setProperty("role", "value")
        chip_text.addWidget(self.device_model_label)
        status_row = QHBoxLayout()
        status_row.setSpacing(5)
        status_row.setContentsMargins(0, 0, 0, 0)
        self.connection_dot = ConnectionDot(self.device_chip, diameter=7)
        status_row.addWidget(self.connection_dot)
        self.connection_label = QLabel("Not connected", self.device_chip)
        self.connection_label.setProperty("role", "muted")
        status_row.addWidget(self.connection_label)
        status_row.addStretch(1)
        chip_text.addLayout(status_row)
        chip_layout.addLayout(chip_text)
        root.addWidget(self.device_chip)

    def _nav_button(self, text: str, tooltip: str) -> QPushButton:
        button = QPushButton(text, self)
        button.setProperty("role", "nav")
        button.setToolTip(tooltip)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumWidth(64)
        return button

    def set_device(self, model_name: str, state: PlotterConnectionState) -> None:
        self.device_model_label.setText(model_name)
        self.connection_dot.set_state(state)
        self.connection_label.setText(connection_label(state))
        self.connection_label.setProperty(
            "role",
            "status-ok" if state is PlotterConnectionState.CONNECTED else "muted",
        )
        style = self.connection_label.style()
        if style is not None:
            style.unpolish(self.connection_label)
            style.polish(self.connection_label)


def _app_pixmap(size: int) -> QPixmap:
    icon = application_icon()
    pixmap = icon.pixmap(QSize(size, size))
    if pixmap.isNull():
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor(COLORS.accent))
    return pixmap
