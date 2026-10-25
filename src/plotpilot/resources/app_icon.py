"""Load the PlotPilot application icon from bundled resources."""

from __future__ import annotations

from importlib import resources

from PySide6.QtGui import QIcon

_ICON_SIZES = (16, 32, 64, 128, 256, 512, 1024)


def application_icon() -> QIcon:
    """Pre-rounded PNG icon for in-app surfaces such as the top bar.

    The packaged macOS Dock icon is the opaque ``plotpilot.icns`` on the app
    bundle. These PNGs stay transparent so the interface keeps the original art.
    """
    base = resources.files("plotpilot.resources.icons")
    icon = QIcon()
    for size in _ICON_SIZES:
        path = base.joinpath(f"icon_{size}.png")
        if path.is_file():
            icon.addFile(str(path))
    return icon
