"""Central SVG workspace: preview canvas, empty state, view tools, readouts."""

from __future__ import annotations

from PySide6.QtCore import QKeyCombination, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from plotpilot.ui.preview_widget import LayerPreviewWidget
from plotpilot.ui.theme import COLORS
from plotpilot.ui.widgets import make_tool_button


class _Overlay(QFrame):
    """Translucent rounded container floating above the preview canvas."""

    def __init__(self, parent: QWidget, *, vertical: bool = False) -> None:
        super().__init__(parent)
        self.setObjectName("previewOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "#previewOverlay {"
            f" background-color: rgba(34, 34, 38, 225); border: 1px solid {COLORS.border};"
            " border-radius: 7px; }"
            "#previewOverlay QLabel { background: transparent; }"
            "#previewOverlay QPushButton { background: transparent; border-color: transparent; }"
            "#previewOverlay QPushButton:hover { background-color: #3c3c40; }"
            f"#previewOverlay QPushButton:checked {{ background-color: {COLORS.accent}; }}"
        )
        layout = QVBoxLayout(self) if vertical else QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        self.body = layout


class PreviewWorkspace(QWidget):
    """Hosts the empty page and the ``LayerPreviewWidget`` plus floating view tools."""

    open_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("previewWorkspace")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(220, 200)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.stack = QStackedWidget(self)
        root.addWidget(self.stack, stretch=1)

        # ---- Empty page ------------------------------------------------------
        self.empty_page = QWidget(self)
        self.empty_page.setObjectName("previewEmptyPage")
        empty_layout = QVBoxLayout(self.empty_page)
        empty_layout.addStretch(1)
        glyph = QLabel("⬚", self.empty_page)
        glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        glyph.setStyleSheet(f"font-size: 40px; color: {COLORS.text_muted};")
        empty_layout.addWidget(glyph)
        heading = QLabel("No SVG loaded", self.empty_page)
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.setProperty("role", "title")
        empty_layout.addWidget(heading)
        caption = QLabel(
            "Open an SVG to preview layers, position the artwork, and plot.",
            self.empty_page,
        )
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        caption.setProperty("role", "caption")
        caption.setWordWrap(True)
        empty_layout.addWidget(caption)
        empty_layout.addSpacing(12)
        self.open_button = QPushButton("Open SVG…", self.empty_page)
        self.open_button.setProperty("role", "accent")
        self.open_button.clicked.connect(self.open_requested)
        empty_layout.addWidget(self.open_button, alignment=Qt.AlignmentFlag.AlignCenter)
        open_shortcut = QKeySequence(QKeySequence.StandardKey.Open).toString(
            QKeySequence.SequenceFormat.NativeText,
        )
        hint = QLabel(f"or press {open_shortcut}", self.empty_page)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setProperty("role", "muted")
        empty_layout.addWidget(hint)
        empty_layout.addStretch(1)
        self.stack.addWidget(self.empty_page)

        # ---- Canvas page -----------------------------------------------------
        # The preview widget itself is the stack page; overlays are its children so
        # they float above the canvas without wrapping it in another container.
        self.preview = LayerPreviewWidget(self)
        self.stack.addWidget(self.preview)
        self.canvas_page = self.preview

        # Floating tools (children of the canvas, positioned on resize)
        self.tools = _Overlay(self.canvas_page, vertical=True)
        self.pan_button = make_tool_button("✋", "Hand tool: drag to pan the view", self.tools)
        self.pan_button.setCheckable(True)
        self.pan_button.toggled.connect(self.preview.set_pan_tool_active)
        self.tools.body.addWidget(self.pan_button)
        self.zoom_in_button = make_tool_button("＋", "Zoom in (⌘+)", self.tools)
        self.zoom_in_button.clicked.connect(self.preview.zoom_in)
        self.tools.body.addWidget(self.zoom_in_button)
        self.zoom_out_button = make_tool_button("－", "Zoom out (⌘−)", self.tools)
        self.zoom_out_button.clicked.connect(self.preview.zoom_out)
        self.tools.body.addWidget(self.zoom_out_button)
        self.fit_button = make_tool_button("⤢", "Fit to window (⌘0)", self.tools)
        self.fit_button.clicked.connect(self.preview.fit_view)
        self.tools.body.addWidget(self.fit_button)

        self.zoom_readout = _Overlay(self.canvas_page)
        self.zoom_minus = make_tool_button("－", "Zoom out", self.zoom_readout)
        self.zoom_minus.clicked.connect(self.preview.zoom_out)
        self.zoom_readout.body.addWidget(self.zoom_minus)
        self.zoom_label = QLabel("100%", self.zoom_readout)
        self.zoom_label.setMinimumWidth(44)
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_label.setProperty("role", "value")
        self.zoom_readout.body.addWidget(self.zoom_label)
        self.zoom_plus = make_tool_button("＋", "Zoom in", self.zoom_readout)
        self.zoom_plus.clicked.connect(self.preview.zoom_in)
        self.zoom_readout.body.addWidget(self.zoom_plus)
        self.fit_text_button = QPushButton("Fit", self.zoom_readout)
        self.fit_text_button.setProperty("role", "preset")
        self.fit_text_button.setToolTip("Fit to window (⌘0)")
        self.fit_text_button.clicked.connect(self.preview.fit_view)
        self.zoom_readout.body.addWidget(self.fit_text_button)

        self.cursor_readout = _Overlay(self.canvas_page)
        self.cursor_label = QLabel("X: —  Y: —", self.cursor_readout)
        self.cursor_label.setProperty("role", "caption")
        self.cursor_label.setMinimumWidth(150)
        self.cursor_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cursor_readout.body.setContentsMargins(10, 5, 10, 5)
        self.cursor_readout.body.addWidget(self.cursor_label)

        self.preview.view_changed.connect(self._sync_zoom_label)
        self.preview.cursor_mm_changed.connect(self._sync_cursor_label)
        self.canvas_page.installEventFilter(self)

        for sequence, slot in (
            (QKeySequence.StandardKey.ZoomIn, self.preview.zoom_in),
            (QKeySequence.StandardKey.ZoomOut, self.preview.zoom_out),
        ):
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.activated.connect(slot)
        fit_shortcut = QShortcut(
            QKeySequence(QKeyCombination(Qt.KeyboardModifier.ControlModifier, Qt.Key.Key_0)),
            self,
        )
        fit_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        fit_shortcut.activated.connect(self.preview.fit_view)

        self._sync_zoom_label()

    # ------------------------------------------------------------------ slots
    def _sync_zoom_label(self) -> None:
        self.zoom_label.setText(f"{int(round(self.preview.view_zoom * 100))}%")

    def _sync_cursor_label(self, point: object) -> None:
        if isinstance(point, tuple) and len(point) == 2:
            x_mm, y_mm = point
            self.cursor_label.setText(f"X: {x_mm:7.1f}   Y: {y_mm:7.1f} mm")
        else:
            self.cursor_label.setText("X: —   Y: — mm")

    def show_document(self, has_document: bool) -> None:
        self.stack.setCurrentWidget(self.canvas_page if has_document else self.empty_page)

    # ---------------------------------------------------------------- layout
    def eventFilter(self, watched, event) -> bool:  # noqa: N802 — Qt API
        if watched is self.canvas_page and event.type() == event.Type.Resize:
            self._place_overlays()
        return super().eventFilter(watched, event)

    def _place_overlays(self) -> None:
        area = self.canvas_page.rect()
        pad = 10
        ruler = int(self.preview.RULER_PX)
        self.tools.adjustSize()
        self.tools.move(area.right() - self.tools.width() - pad, area.top() + ruler + pad)
        self.zoom_readout.adjustSize()
        self.zoom_readout.move(
            area.left() + ruler + pad,
            area.bottom() - self.zoom_readout.height() - pad,
        )
        self.cursor_readout.adjustSize()
        self.cursor_readout.move(
            area.right() - self.cursor_readout.width() - pad,
            area.bottom() - self.cursor_readout.height() - pad,
        )
        needed = self.zoom_readout.width() + self.cursor_readout.width() + ruler + 3 * pad
        self.cursor_readout.setVisible(area.width() >= needed)
        self.tools.setVisible(area.height() >= self.tools.height() + ruler + 2 * pad + 60)
        for overlay in (self.tools, self.zoom_readout, self.cursor_readout):
            overlay.raise_()
