"""PlotPilot application bootstrap."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from plotpilot.ui.main_window import MainWindow


def run() -> None:
    """Start the PlotPilot desktop application."""
    app = QApplication(sys.argv)
    app.setApplicationName("PlotPilot")
    app.setOrganizationName("PlotPilot")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    run()
