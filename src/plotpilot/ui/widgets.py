"""Small reusable building blocks shared by the V2 panels."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLayoutItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class FlowLayout(QLayout):
    """Left-to-right layout that wraps items onto new rows when the width is too small.

    Used by the bottom action bar so control groups never get clipped on narrow
    windows; they simply wrap.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        h_spacing: int = 12,
        v_spacing: int = 6,
    ) -> None:
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item: QLayoutItem) -> None:  # noqa: N802 — Qt API
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:  # noqa: N802 — Qt API
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> QLayoutItem | None:  # noqa: N802 — Qt API
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientation:  # noqa: N802 — Qt API
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802 — Qt API
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802 — Qt API
        return self._do_layout(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802 — Qt API
        super().setGeometry(rect)
        self._do_layout(rect, apply=True)

    def sizeHint(self) -> QSize:  # noqa: N802 — Qt API
        width = sum(item.sizeHint().width() for item in self._items)
        width += self._h_spacing * max(0, len(self._items) - 1)
        height = max((item.sizeHint().height() for item in self._items), default=0)
        margins = self.contentsMargins()
        return QSize(
            width + margins.left() + margins.right(),
            height + margins.top() + margins.bottom(),
        )

    def minimumSize(self) -> QSize:  # noqa: N802 — Qt API
        width = max((item.minimumSize().width() for item in self._items), default=0)
        height = max((item.minimumSize().height() for item in self._items), default=0)
        margins = self.contentsMargins()
        return QSize(
            width + margins.left() + margins.right(),
            height + margins.top() + margins.bottom(),
        )

    def _do_layout(self, rect: QRect, *, apply: bool) -> int:
        margins = self.contentsMargins()
        effective = rect.adjusted(
            margins.left(), margins.top(), -margins.right(), -margins.bottom()
        )
        x = effective.x()
        y = effective.y()
        row_height = 0
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + self._h_spacing
            if next_x - self._h_spacing > effective.right() + 1 and row_height > 0:
                x = effective.x()
                y += row_height + self._v_spacing
                next_x = x + hint.width() + self._h_spacing
                row_height = 0
            if apply:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            row_height = max(row_height, hint.height())
        return y + row_height - rect.y() + margins.bottom()


def make_card(
    title: str | None,
    parent: QWidget | None = None,
    *,
    subtitle: str | None = None,
    trailing: QWidget | None = None,
) -> tuple[QFrame, QVBoxLayout]:
    """Return a rounded card frame and its content layout.

    The optional *trailing* widget sits at the right end of the title row.
    """
    card = QFrame(parent)
    card.setProperty("role", "card")
    card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(12, 10, 12, 12)
    layout.setSpacing(8)
    if title is not None:
        header = QHBoxLayout()
        header.setSpacing(6)
        heading = QLabel(title, card)
        heading.setProperty("role", "heading")
        header.addWidget(heading)
        if subtitle:
            caption = QLabel(subtitle, card)
            caption.setProperty("role", "caption")
            header.addWidget(caption)
        header.addStretch(1)
        if trailing is not None:
            header.addWidget(trailing)
        layout.addLayout(header)
    return card, layout


def make_wrapping_label(
    text: str, parent: QWidget | None = None, *, role: str | None = None
) -> QLabel:
    """Word-wrapping label that can shrink below its text width instead of forcing scrollbars."""
    label = QLabel(text, parent)
    label.setWordWrap(True)
    label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    label.setMinimumWidth(40)
    if role:
        label.setProperty("role", role)
    return label


def make_separator(parent: QWidget | None = None) -> QFrame:
    line = QFrame(parent)
    line.setProperty("role", "separator")
    line.setFrameShape(QFrame.Shape.NoFrame)
    line.setFixedHeight(1)
    return line


def make_group_label(text: str, parent: QWidget | None = None) -> QLabel:
    label = QLabel(text, parent)
    label.setProperty("role", "group")
    return label


class ElidedLabel(QLabel):
    """Single-line label that elides long text instead of growing the layout.

    ``text()`` returns the full, un-elided text so callers (and tests) can read it.
    """

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full_text = ""
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(24)
        self.setText(text)

    def setText(self, text: str) -> None:  # noqa: N802 — Qt API
        self._full_text = text
        self.setToolTip(text if "\n" in text or len(text) > 60 else "")
        self._apply_elide()

    def text(self) -> str:  # noqa: D102
        return self._full_text

    def resizeEvent(self, event) -> None:  # noqa: N802 — Qt API
        super().resizeEvent(event)
        self._apply_elide()

    def _apply_elide(self) -> None:
        single = " · ".join(part.strip() for part in self._full_text.splitlines() if part.strip())
        width = max(self.width() - 4, 24)
        elided = self.fontMetrics().elidedText(single, Qt.TextElideMode.ElideRight, width)
        super().setText(elided)


def make_tool_button(text: str, tooltip: str, parent: QWidget | None = None) -> QPushButton:
    button = QPushButton(text, parent)
    button.setProperty("role", "tool")
    button.setToolTip(tooltip)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    return button
