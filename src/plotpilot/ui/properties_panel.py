"""Right-hand properties panel: Transform · Plot Settings · Device tabs, each scrollable."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QFrame,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

TAB_TRANSFORM = 0
TAB_PLOT_SETTINGS = 1
TAB_DEVICE = 2


class PanelScrollArea(QScrollArea):
    """Vertical scroller whose minimum size does not follow the document size.

    The content keeps its natural minimum width; when the panel is narrower a
    horizontal scrollbar appears instead of clipping controls.
    """

    def __init__(self, content: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        wrapper = QWidget(self)
        wrapper.setObjectName("panelScrollContent")
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(10, 10, 10, 12)
        layout.setSpacing(10)
        layout.addWidget(content)
        layout.addStretch(1)
        self.setWidget(wrapper)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 — Qt API
        return QSize(120, 80)

    def sizeHint(self) -> QSize:  # noqa: N802 — Qt API
        hint = super().sizeHint()
        return QSize(min(hint.width(), 360), hint.height())


class PropertiesPanel(QWidget):
    def __init__(
        self,
        *,
        transform: QWidget,
        plot_settings: QWidget,
        device: QWidget,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("propertiesPanel")
        self.setMinimumWidth(240)
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 0)
        root.setSpacing(6)

        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("propertiesTabs")
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setExpanding(True)
        self.tabs.tabBar().setDrawBase(False)
        self.tabs.setUsesScrollButtons(False)

        self.transform_scroll = PanelScrollArea(transform, self.tabs)
        self.plot_settings_scroll = PanelScrollArea(plot_settings, self.tabs)
        self.device_scroll = PanelScrollArea(device, self.tabs)
        self.tabs.addTab(self.transform_scroll, "Transform")
        self.tabs.addTab(self.plot_settings_scroll, "Plot Settings")
        self.tabs.addTab(self.device_scroll, "Device")
        root.addWidget(self.tabs, stretch=1)

    def set_current_tab(self, index: int) -> None:
        self.tabs.setCurrentIndex(index)

    def scroll_areas(self) -> tuple[PanelScrollArea, ...]:
        return (self.transform_scroll, self.plot_settings_scroll, self.device_scroll)
