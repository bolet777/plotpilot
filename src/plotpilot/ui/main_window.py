"""Primary application window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from plotpilot.models.svg_document import SvgDocument
from plotpilot.services.svg_loader import SvgLoadError, load_svg_from_path


class MainWindow(QMainWindow):
    """PlotPilot main window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PlotPilot")
        self.resize(640, 400)

        self._document: SvgDocument | None = None

        central = QWidget(self)
        layout = QVBoxLayout(central)

        self._status_label = QLabel(
            "No SVG loaded. Use File → Open SVG… (⌘O) to open a file.",
            central,
        )
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        self.setCentralWidget(central)
        self._build_menu()

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")

        open_action = QAction("Open SVG…", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._open_svg)
        file_menu.addAction(open_action)

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

        self._document = document
        self._status_label.setText(f"Loaded: {document.name}")
