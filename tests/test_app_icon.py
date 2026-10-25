"""Application icon source and macOS Dock icon ownership."""

from __future__ import annotations

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from plotpilot.app.macos import uses_system_dock_icon
from plotpilot.resources.app_icon import application_icon


def test_application_icon_keeps_transparent_png_corners(qapp: QApplication) -> None:
    assert qapp is not None
    image = application_icon().pixmap(1024, 1024).toImage()
    image = image.convertToFormat(QImage.Format.Format_RGBA8888)
    assert image.pixelColor(0, 0).alpha() == 0
    assert image.pixelColor(image.width() // 2, image.height() // 2).alpha() > 200


def test_packaged_app_uses_system_dock_icon() -> None:
    assert uses_system_dock_icon("darwin", "com.plotpilot.app")
    assert not uses_system_dock_icon("darwin", "org.python.python")
    assert not uses_system_dock_icon("darwin", None)
    assert not uses_system_dock_icon("linux", "com.plotpilot.app")
