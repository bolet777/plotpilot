"""Primary application window (placeholder)."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget


class MainWindow(QMainWindow):
    """Minimal window to verify PySide6 and project wiring."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PlotPilot")
        self.resize(640, 400)

        central = QWidget(self)
        layout = QVBoxLayout(central)

        label = QLabel(
            "PlotPilot foundation is running.\n"
            "SVG layers and AxiDraw control are not implemented yet.",
            central,
        )
        label.setWordWrap(True)
        layout.addWidget(label)

        self.setCentralWidget(central)
