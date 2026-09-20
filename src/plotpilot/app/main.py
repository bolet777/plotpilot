"""PlotPilot application bootstrap."""

from __future__ import annotations

import sys

from plotpilot.app.macos import configure_branding

_APP_NAME = "PlotPilot"


def run() -> None:
    """Start the PlotPilot desktop application."""
    configure_branding(_APP_NAME)
    _run_qt_app()


def _run_qt_app() -> None:
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QApplication

    from plotpilot.resources.app_icon import application_icon
    from plotpilot.ui.main_window import MainWindow

    QCoreApplication.setApplicationName(_APP_NAME)
    QCoreApplication.setOrganizationName(_APP_NAME)
    QGuiApplication.setApplicationDisplayName(_APP_NAME)

    app = QApplication(sys.argv)
    app.setWindowIcon(application_icon())

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    run()
