"""Layer preview widget behavior."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from plotpilot.ui.preview_widget import LayerPreviewWidget

MINIMAL_SVG = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">
  <rect width="10" height="10" fill="#000000"/>
</svg>"""


@pytest.fixture(scope="session")
def qapp():
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    yield application


def test_valid_preview_loads(qapp) -> None:
    widget = LayerPreviewWidget()
    assert widget.set_preview_svg(MINIMAL_SVG) is True
    assert widget.message is None
    assert widget.last_svg == MINIMAL_SVG


def test_invalid_preview_does_not_crash(qapp) -> None:
    widget = LayerPreviewWidget()
    assert widget.set_preview_svg("<not-valid-svg") is False
    assert widget.message is not None
    widget.repaint()
