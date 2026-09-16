"""Primary application window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QIcon, QKeySequence, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from plotpilot.models.svg_document import SvgDocument
from plotpilot.models.svg_layer import SvgLayer
from plotpilot.services.layer_service import layers_for_document
from plotpilot.services.svg_loader import SvgLoadError, load_svg_from_path


class MainWindow(QMainWindow):
    """PlotPilot main window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PlotPilot")
        self.resize(640, 480)

        self._document: SvgDocument | None = None
        self._layers: list[SvgLayer] = []

        central = QWidget(self)
        layout = QVBoxLayout(central)

        self._status_label = QLabel(
            "No SVG loaded. Use File → Open SVG… (⌘O) to open a file.",
            central,
        )
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        layers_heading = QLabel("Layers", central)
        layers_heading.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(layers_heading)

        self._layers_list = QListWidget(central)
        self._layers_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        layout.addWidget(self._layers_list)

        self.setCentralWidget(central)
        self._build_menu()

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

    def _open_svg(self) -> None:
        file_path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Open SVG",
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
        self._status_label.setText(f"Loaded: {document.name}")
        self._refresh_layers_list()

    def _refresh_layers_list(self) -> None:
        self._layers_list.clear()
        for layer in self._layers:
            item = QListWidgetItem(layer.name)
            item.setIcon(_layer_swatch_icon(layer.representative_color))
            item.setData(Qt.ItemDataRole.UserRole, layer.layer_id)
            self._layers_list.addItem(item)

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
