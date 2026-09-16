"""Primary application window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QIcon, QKeySequence, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from plotpilot.models.plotter_status import PlotterConnectionState, PlotterStatus
from plotpilot.models.svg_document import SvgDocument
from plotpilot.models.svg_layer import SvgLayer
from plotpilot.plotter.axidraw import AxiDrawCliBackend
from plotpilot.plotter.base import PlotterBackend
from plotpilot.services.layer_service import layers_for_document
from plotpilot.services.plotter_service import PlotterService
from plotpilot.services.preview_service import preview_svg_for_layer
from plotpilot.services.svg_loader import SvgLoadError, load_svg_from_path
from plotpilot.ui.preview_widget import LayerPreviewWidget


class MainWindow(QMainWindow):
    """PlotPilot main window."""

    def __init__(
        self,
        *,
        plotter_backend: PlotterBackend | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("PlotPilot")
        self.resize(900, 560)

        self._document: SvgDocument | None = None
        self._layers: list[SvgLayer] = []
        self._updating_layers = False

        backend = plotter_backend if plotter_backend is not None else AxiDrawCliBackend()
        self._plotter_service = PlotterService(backend, parent=self)
        self._plotter_service.status_changed.connect(self._apply_plotter_status)

        central = QWidget(self)
        root_layout = QVBoxLayout(central)

        content_row = QHBoxLayout()
        left_column = QVBoxLayout()
        layers_heading = QLabel("Layers", central)
        layers_heading.setStyleSheet("font-weight: bold;")
        left_column.addWidget(layers_heading)

        self._layers_list = QListWidget(central)
        self._layers_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._layers_list.setMinimumWidth(180)
        self._layers_list.currentRowChanged.connect(self._on_layer_row_changed)
        left_column.addWidget(self._layers_list, stretch=1)

        content_row.addLayout(left_column, stretch=0)

        self._preview = LayerPreviewWidget(central)
        content_row.addWidget(self._preview, stretch=1)

        root_layout.addLayout(content_row, stretch=1)

        plotter_heading = QLabel("Plotter", central)
        plotter_heading.setStyleSheet("font-weight: bold;")
        root_layout.addWidget(plotter_heading)

        plotter_row = QHBoxLayout()
        self._plotter_name_label = QLabel("AxiDraw", central)
        plotter_row.addWidget(self._plotter_name_label)

        self._plotter_status_label = QLabel("○ Not connected", central)
        self._plotter_status_label.setWordWrap(True)
        plotter_row.addWidget(self._plotter_status_label, stretch=1)
        root_layout.addLayout(plotter_row)

        plotter_buttons = QHBoxLayout()
        self._pen_up_button = QPushButton("Pen ↑", central)
        self._pen_up_button.clicked.connect(self._plotter_service.pen_up)
        plotter_buttons.addWidget(self._pen_up_button)

        self._pen_down_button = QPushButton("Pen ↓", central)
        self._pen_down_button.clicked.connect(self._plotter_service.pen_down)
        plotter_buttons.addWidget(self._pen_down_button)

        self._plotter_refresh_button = QPushButton("Refresh", central)
        self._plotter_refresh_button.clicked.connect(self._plotter_service.refresh)
        plotter_buttons.addWidget(self._plotter_refresh_button)
        plotter_buttons.addStretch(1)
        root_layout.addLayout(plotter_buttons)

        self._plotter_message_label = QLabel("", central)
        self._plotter_message_label.setWordWrap(True)
        root_layout.addWidget(self._plotter_message_label)

        self._status_label = QLabel(
            "No SVG loaded. Use File → Open SVG… (⌘O) to open a file.",
            central,
        )
        self._status_label.setWordWrap(True)
        root_layout.addWidget(self._status_label)

        self.setCentralWidget(central)
        self._build_menu()
        self._apply_plotter_status(self._plotter_service.status)

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")

        open_action = QAction("Open SVG…", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._open_svg)
        file_menu.addAction(open_action)

    @property
    def document(self) -> SvgDocument | None:
        return self._document

    @property
    def layers(self) -> list[SvgLayer]:
        return list(self._layers)

    @property
    def current_preview_svg(self) -> str | None:
        return self._preview.last_svg

    @property
    def plotter_service(self) -> PlotterService:
        return self._plotter_service

    def _apply_plotter_status(self, status: PlotterStatus) -> None:
        if status.state is PlotterConnectionState.CONNECTED:
            indicator = "● Connected"
        elif status.state is PlotterConnectionState.ERROR:
            indicator = "● Error"
        else:
            indicator = "○ Not connected"
        self._plotter_status_label.setText(indicator)
        self._plotter_message_label.setText(status.message)
        enabled = status.pen_commands_enabled
        self._pen_up_button.setEnabled(enabled)
        self._pen_down_button.setEnabled(enabled)

    def _open_svg(self) -> None:
        file_path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Open SVG…",
            "",
            "SVG files (*.svg)",
        )
        if not file_path:
            return

        try:
            document = load_svg_from_path(Path(file_path))
        except SvgLoadError as exc:
            QMessageBox.warning(
                self,
                "Could not open SVG",
                exc.user_message,
            )
            return

        self.set_document(document)

    def _apply_document(self, document: SvgDocument) -> None:
        self._document = document
        self._layers = layers_for_document(document)
        self._status_label.setText(document.name)
        self._refresh_layers_list()

    def _refresh_layers_list(self) -> None:
        self._updating_layers = True
        self._layers_list.blockSignals(True)
        self._layers_list.clear()
        for layer in self._layers:
            item = QListWidgetItem(layer.name)
            item.setIcon(_layer_swatch_icon(layer.representative_color))
            item.setData(Qt.ItemDataRole.UserRole, layer.layer_id)
            self._layers_list.addItem(item)
        if self._layers_list.count() > 0:
            self._layers_list.setCurrentRow(0)
        self._layers_list.blockSignals(False)
        self._updating_layers = False
        self._update_preview_for_current_layer()

    def _on_layer_row_changed(self, _row: int) -> None:
        if self._updating_layers:
            return
        self._update_preview_for_current_layer()

    def _update_preview_for_current_layer(self) -> None:
        if self._document is None or not self._layers:
            self._preview.clear_preview()
            return

        row = self._layers_list.currentRow()
        if row < 0 or row >= len(self._layers):
            self._preview.clear_preview("Select a layer to preview.")
            return

        layer = self._layers[row]
        svg_text = preview_svg_for_layer(self._document, layer)
        self._preview.set_preview_svg(svg_text)

    def set_document(self, document: SvgDocument) -> None:
        """Replace the active document and layer list (used after successful load)."""
        self._apply_document(document)


def _layer_swatch_icon(color: str | None) -> QIcon:
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    if color:
        qcolor = QColor(color)
        brush_color = qcolor if qcolor.isValid() else QColor("#808080")
    else:
        brush_color = QColor("#c0c0c0")
    painter.setBrush(brush_color)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(2, 2, 12, 12)
    painter.end()
    return QIcon(pixmap)
