"""Load the PlotPilot application icon from bundled resources."""

from __future__ import annotations

import sys
from importlib import resources

from PySide6.QtGui import QIcon

_ICON_SIZES = (16, 32, 64, 128, 256, 512, 1024)


def application_icon() -> QIcon:
    """Multi-resolution icon for the main window and macOS dock when running the app."""
    base = resources.files("plotpilot.resources.icons")

    if sys.platform == "darwin":
        icns = base.joinpath("plotpilot.icns")
        if icns.is_file():
            return QIcon(str(icns))

    icon = QIcon()
    for size in _ICON_SIZES:
        path = base.joinpath(f"icon_{size}.png")
        if path.is_file():
            icon.addFile(str(path))
    return icon
