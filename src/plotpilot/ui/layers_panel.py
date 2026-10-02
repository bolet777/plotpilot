"""Layers sidebar: compact list with visibility check, color swatch, name, and path count."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QModelIndex, QPointF, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from plotpilot.models.svg_layer import SvgLayer
from plotpilot.ui.theme import COLORS, scaled_font
from plotpilot.ui.widgets import make_wrapping_label

LAYER_ID_ROLE = Qt.ItemDataRole.UserRole
LAYER_COLOR_ROLE = Qt.ItemDataRole.UserRole + 1
LAYER_COUNT_ROLE = Qt.ItemDataRole.UserRole + 2
LAYER_HIDDEN_ROLE = Qt.ItemDataRole.UserRole + 3
LAYER_NAME_ROLE = Qt.ItemDataRole.UserRole + 4

_ROW_HEIGHT = 46
_CHECK_SIZE = 16
_SWATCH_SIZE = 18
_PAD = 10


def layer_secondary_text(layer: SvgLayer) -> str:
    """Secondary line shown under the layer name (path count, hidden flag)."""
    noun = "path" if layer.drawable_count == 1 else "paths"
    text = f"{layer.drawable_count:,} {noun}".replace(",", "\u202f")
    if layer.hidden:
        text += " · hidden"
    return text


def populate_layer_item(item: QListWidgetItem, layer: SvgLayer, index: int) -> None:
    """Fill a list item with the data the delegate paints. Keeps the check state untouched."""
    item.setText(f"{index}  {layer.list_label}")
    item.setData(LAYER_ID_ROLE, layer.layer_id)
    item.setData(LAYER_COLOR_ROLE, layer.representative_color or "")
    item.setData(LAYER_COUNT_ROLE, layer_secondary_text(layer))
    item.setData(LAYER_HIDDEN_ROLE, layer.hidden)
    item.setData(LAYER_NAME_ROLE, layer.name)
    item.setToolTip(f"{layer.name}\n{layer_secondary_text(layer)}")


class LayerItemDelegate(QStyledItemDelegate):
    """Paint a two-line layer row with a checkbox (plot/visibility) and color swatch."""

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        return QSize(max(140, option.rect.width()), _ROW_HEIGHT)

    @staticmethod
    def check_rect(rect: QRect) -> QRect:
        y = rect.y() + (rect.height() - _CHECK_SIZE) // 2
        return QRect(rect.x() + _PAD, y, _CHECK_SIZE, _CHECK_SIZE)

    def paint(  # noqa: N802
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        enabled = bool(option.state & QStyle.StateFlag.State_Enabled)

        row_rect = rect.adjusted(4, 2, -4, -2)
        painter.setPen(Qt.PenStyle.NoPen)
        if selected:
            painter.setBrush(QColor(COLORS.accent_soft))
            painter.drawRoundedRect(row_rect, 6, 6)
            painter.setBrush(QColor(COLORS.accent))
            painter.drawRoundedRect(
                QRect(row_rect.x(), row_rect.y() + 6, 3, row_rect.height() - 12), 1.5, 1.5
            )
        elif hovered:
            painter.setBrush(QColor(COLORS.raised))
            painter.drawRoundedRect(row_rect, 6, 6)

        # Checkbox (plot this layer in multi-layer jobs)
        check = self.check_rect(rect)
        checked = index.data(Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked
        flags = index.flags()
        checkable = bool(flags & Qt.ItemFlag.ItemIsUserCheckable) and enabled
        if checked:
            painter.setBrush(QColor(COLORS.accent if checkable else "#4a5a75"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(check, 3, 3)
            pen = QPen(QColor("#ffffff"))
            pen.setWidthF(1.8)
            painter.setPen(pen)
            origin = QPointF(check.topLeft())
            painter.drawPolyline(
                QPolygonF(
                    [
                        origin + QPointF(3.5, 8.5),
                        origin + QPointF(6.8, 11.5),
                        origin + QPointF(12.5, 4.5),
                    ]
                )
            )
        else:
            painter.setBrush(QColor(COLORS.input))
            painter.setPen(QPen(QColor("#55555b" if checkable else COLORS.border_subtle)))
            painter.drawRoundedRect(check, 3, 3)

        # Color swatch
        swatch_x = check.right() + _PAD
        swatch_y = rect.y() + (rect.height() - _SWATCH_SIZE) // 2
        swatch = QRect(swatch_x, swatch_y, _SWATCH_SIZE, _SWATCH_SIZE)
        color_text = index.data(LAYER_COLOR_ROLE) or ""
        color = QColor(color_text) if color_text else QColor()
        painter.setPen(QPen(QColor(COLORS.border)))
        painter.setBrush(color if color.isValid() else QColor("#8a8a90"))
        painter.drawRoundedRect(swatch, 4, 4)

        # Name + secondary
        text_x = swatch.right() + _PAD
        text_rect = QRect(text_x, rect.y(), rect.right() - text_x - _PAD, rect.height())
        name = index.data(LAYER_NAME_ROLE) or index.data(Qt.ItemDataRole.DisplayRole) or ""
        hidden = bool(index.data(LAYER_HIDDEN_ROLE))
        name_font = scaled_font(option.font, 0.5)
        name_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(name_font)
        text_color = COLORS.text if enabled else COLORS.text_muted
        if hidden:
            text_color = COLORS.text_secondary
        painter.setPen(QColor(text_color))
        metrics = painter.fontMetrics()
        name_line = QRect(text_rect.x(), rect.y() + 7, text_rect.width(), metrics.height())
        painter.drawText(
            name_line,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            metrics.elidedText(str(name), Qt.TextElideMode.ElideRight, text_rect.width()),
        )
        sub_font = scaled_font(option.font, -1.0, minimum=8.0)
        painter.setFont(sub_font)
        painter.setPen(QColor(COLORS.text_secondary if enabled else COLORS.text_muted))
        sub_metrics = painter.fontMetrics()
        sub_line = QRect(
            text_rect.x(),
            name_line.bottom() + 1,
            text_rect.width(),
            sub_metrics.height(),
        )
        painter.drawText(
            sub_line,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            sub_metrics.elidedText(
                str(index.data(LAYER_COUNT_ROLE) or ""),
                Qt.TextElideMode.ElideRight,
                text_rect.width(),
            ),
        )
        painter.restore()

    def editorEvent(  # noqa: N802
        self,
        event: QEvent,
        model,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> bool:
        """Toggle the check state when the custom checkbox area is clicked."""
        if not (index.flags() & Qt.ItemFlag.ItemIsUserCheckable) or not (
            index.flags() & Qt.ItemFlag.ItemIsEnabled
        ):
            return False
        if event.type() in (QEvent.Type.MouseButtonRelease, QEvent.Type.MouseButtonDblClick):
            assert isinstance(event, QMouseEvent)
            if event.button() != Qt.MouseButton.LeftButton:
                return False
            hit = self.check_rect(option.rect).adjusted(-4, -6, 4, 6)
            if not hit.contains(event.position().toPoint()):
                return False
            if event.type() == QEvent.Type.MouseButtonDblClick:
                return True
            current = index.data(Qt.ItemDataRole.CheckStateRole)
            new_state = (
                Qt.CheckState.Unchecked
                if current == Qt.CheckState.Checked
                else Qt.CheckState.Checked
            )
            return model.setData(index, new_state, Qt.ItemDataRole.CheckStateRole)
        if event.type() == QEvent.Type.MouseButtonPress:
            assert isinstance(event, QMouseEvent)
            hit = self.check_rect(option.rect).adjusted(-4, -6, 4, 6)
            if hit.contains(event.position().toPoint()):
                return True
        return False


class LayersPanel(QWidget):
    """Sidebar hosting the layer list. ``list_widget`` is the authoritative selection model."""

    add_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("layersPanel")
        self.setMinimumWidth(168)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 8)
        root.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(6)
        title = QLabel("Layers", self)
        title.setProperty("role", "heading")
        header.addWidget(title)
        header.addStretch(1)
        self.count_label = QLabel("", self)
        self.count_label.setProperty("role", "muted")
        header.addWidget(self.count_label)
        self.open_button = QPushButton("Open…", self)
        self.open_button.setProperty("role", "quiet")
        self.open_button.setToolTip("Open another SVG file (⌘O)")
        header.addWidget(self.open_button)
        root.addLayout(header)

        self.list_widget = QListWidget(self)
        self.list_widget.setObjectName("layersList")
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.list_widget.setItemDelegate(LayerItemDelegate(self.list_widget))
        self.list_widget.setMouseTracking(True)
        self.list_widget.setUniformItemSizes(True)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.list_widget.setSpacing(0)
        root.addWidget(self.list_widget, stretch=1)

        self.hint_label = make_wrapping_label(
            "Check layers to include them in a multi-layer plot.", self, role="muted"
        )
        root.addWidget(self.hint_label)

    def set_layer_count(self, count: int) -> None:
        self.count_label.setText("" if count == 0 else f"{count}")
        self.hint_label.setVisible(count > 1)
