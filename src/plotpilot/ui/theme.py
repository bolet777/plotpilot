"""Centralized dark desktop theme (palette + Qt stylesheet) for PlotPilot V2.

Every widget relies on this module for colors and spacing instead of carrying
its own hardcoded stylesheet. Object names and dynamic ``role`` properties are
the hooks used by the stylesheet:

- ``#topBar``, ``#layersPanel``, ``#propertiesPanel``, ``#actionBar``,
  ``#previewWorkspace`` for the main regions
- ``QFrame[role="card"]`` for grouped controls inside the properties panel
- ``QPushButton[role="accent"]`` / ``[role="nav"]`` / ``[role="quiet"]`` for
  button variants
- ``QLabel[role="heading"]`` / ``[role="caption"]`` / ``[role="muted"]``
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication


@dataclass(frozen=True, slots=True)
class ThemeColors:
    window: str = "#1b1b1d"
    panel: str = "#222224"
    card: str = "#2a2a2d"
    input: str = "#19191b"
    raised: str = "#333336"
    border: str = "#39393d"
    border_subtle: str = "#2f2f33"
    text: str = "#ececf0"
    text_secondary: str = "#a6a6ae"
    text_muted: str = "#6d6d76"
    accent: str = "#2f7df6"
    accent_hover: str = "#4a8ff8"
    accent_pressed: str = "#2468d6"
    accent_soft: str = "#1f3a66"
    danger: str = "#e5484d"
    success: str = "#34c38f"
    warning: str = "#f0a63a"
    selection: str = "#2f7df6"
    # Preview canvas
    canvas: str = "#161618"
    canvas_grid: str = "#232326"
    paper: str = "#f6f6f4"
    paper_shadow: str = "#0a0a0b"
    margin_zone: str = "#d9d9d6"
    printable_outline: str = "#2f7df6"
    work_area_outline: str = "#7a7a80"
    artwork_ink: str = "#111111"
    ruler_bg: str = "#1f1f22"
    ruler_tick: str = "#6d6d76"
    ruler_text: str = "#a6a6ae"


COLORS = ThemeColors()

RADIUS = 6
CONTROL_HEIGHT = 24


def build_stylesheet(c: ThemeColors = COLORS) -> str:
    """Return the application-wide Qt stylesheet."""
    return f"""
    /* Plain containers inherit the palette window colour; only regions and
       controls paint explicit backgrounds. Avoid `X QWidget {{ transparent }}`
       descendant rules: their ID specificity would override role-based button
       styles such as QPushButton[role="accent"]. */
    QWidget {{
        color: {c.text};
        font-size: 12px;
        selection-background-color: {c.selection};
        selection-color: #ffffff;
    }}
    QMainWindow, QDialog, #mainContent {{
        background-color: {c.window};
    }}
    QToolTip {{
        background-color: {c.raised};
        color: {c.text};
        border: 1px solid {c.border};
        padding: 4px 6px;
        border-radius: 4px;
    }}
    QMenuBar {{
        background-color: {c.window};
        color: {c.text};
    }}
    QMenuBar::item:selected {{ background-color: {c.raised}; }}
    QMenu {{
        background-color: {c.panel};
        color: {c.text};
        border: 1px solid {c.border};
        padding: 4px;
    }}
    QMenu::item {{ padding: 4px 18px; border-radius: 4px; }}
    QMenu::item:selected {{ background-color: {c.accent}; color: #ffffff; }}
    QMenu::separator {{ height: 1px; background: {c.border}; margin: 4px 6px; }}

    /* ---- Regions ------------------------------------------------------- */
    #topBar {{
        background-color: {c.panel};
        border-bottom: 1px solid {c.border_subtle};
    }}
    #layersPanel, #propertiesPanel {{
        background-color: {c.panel};
    }}
    #layersPanel {{ border-right: 1px solid {c.border_subtle}; }}
    #propertiesPanel {{ border-left: 1px solid {c.border_subtle}; }}
    #actionBar {{
        background-color: {c.panel};
        border-top: 1px solid {c.border_subtle};
    }}
    #actionBar QPushButton {{ padding: 3px 9px; }}
    #previewWorkspace, #previewEmptyPage {{ background-color: {c.canvas}; }}
    QStackedWidget, QTabWidget::pane {{ background: transparent; border: none; }}

    QSplitter::handle {{
        background-color: {c.border_subtle};
    }}
    QSplitter::handle:horizontal {{ width: 1px; }}
    QSplitter::handle:vertical {{ height: 1px; }}
    QSplitter::handle:hover {{ background-color: {c.accent}; }}

    /* ---- Cards & text --------------------------------------------------- */
    QFrame[role="card"] {{
        background-color: {c.card};
        border: 1px solid {c.border_subtle};
        border-radius: {RADIUS + 2}px;
    }}
    QFrame[role="banner"] {{
        background-color: {c.accent_soft};
        border: 1px solid {c.accent};
        border-radius: {RADIUS}px;
    }}
    QFrame[role="info"] {{
        background-color: {c.input};
        border: 1px solid {c.border_subtle};
        border-radius: {RADIUS}px;
    }}
    QFrame[role="separator"] {{
        background-color: {c.border_subtle};
        max-height: 1px;
        min-height: 1px;
        border: none;
    }}
    QLabel {{ background: transparent; }}
    QLabel[role="heading"] {{
        font-size: 13px;
        font-weight: 600;
        color: {c.text};
    }}
    QLabel[role="title"] {{
        font-size: 14px;
        font-weight: 700;
        color: {c.text};
    }}
    QLabel[role="caption"] {{
        font-size: 11px;
        color: {c.text_secondary};
    }}
    QLabel[role="muted"] {{
        font-size: 11px;
        color: {c.text_muted};
    }}
    QLabel[role="value"] {{
        font-size: 12px;
        color: {c.text};
        font-weight: 600;
    }}
    QLabel[role="group"] {{
        font-size: 11px;
        font-weight: 600;
        color: {c.text_secondary};
    }}
    QLabel[role="status-ok"] {{ color: {c.success}; }}
    QLabel[role="status-warn"] {{ color: {c.warning}; }}
    QLabel[role="status-error"] {{ color: {c.danger}; }}

    /* ---- Buttons -------------------------------------------------------- */
    QPushButton {{
        background-color: {c.raised};
        color: {c.text};
        border: 1px solid {c.border};
        border-radius: {RADIUS}px;
        padding: 3px 10px;
        min-height: {CONTROL_HEIGHT - 2}px;
    }}
    QPushButton:hover {{ background-color: #3c3c40; border-color: #4a4a4f; }}
    QPushButton:pressed {{ background-color: #2a2a2d; }}
    QPushButton:disabled {{
        background-color: #262628;
        color: {c.text_muted};
        border-color: {c.border_subtle};
    }}
    QPushButton:checked {{
        background-color: {c.accent};
        color: #ffffff;
        border-color: {c.accent};
    }}
    QPushButton[role="accent"] {{
        background-color: {c.accent};
        color: #ffffff;
        border-color: {c.accent};
        font-weight: 600;
    }}
    QPushButton[role="accent"]:hover {{ background-color: {c.accent_hover}; }}
    QPushButton[role="accent"]:pressed {{ background-color: {c.accent_pressed}; }}
    QPushButton[role="accent"]:disabled {{
        background-color: #262628;
        color: {c.text_muted};
        border-color: {c.border_subtle};
    }}
    QPushButton[role="danger"] {{
        background-color: #3a2426;
        color: #ff8a8e;
        border-color: #5a2d31;
    }}
    QPushButton[role="danger"]:hover {{ background-color: #4a2b2e; }}
    QPushButton[role="danger"]:disabled {{
        background-color: #262628;
        color: {c.text_muted};
        border-color: {c.border_subtle};
    }}
    QPushButton[role="quiet"] {{
        background-color: transparent;
        border-color: transparent;
        color: {c.text_secondary};
    }}
    QPushButton[role="quiet"]:hover {{ background-color: {c.raised}; color: {c.text}; }}
    QPushButton[role="nav"] {{
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: {RADIUS}px;
        padding: 4px 10px;
        min-height: 28px;
        color: {c.text_secondary};
    }}
    QPushButton[role="nav"]:hover {{ background-color: {c.raised}; color: {c.text}; }}
    QPushButton[role="nav"]:checked {{
        background-color: {c.accent};
        color: #ffffff;
    }}
    QPushButton[role="nav"]:disabled {{ color: {c.text_muted}; background: transparent; }}
    QPushButton[role="preset"] {{
        padding: 2px 8px;
        min-height: 20px;
        font-size: 11px;
    }}
    QPushButton[role="tool"] {{
        background-color: {c.raised};
        border: 1px solid {c.border};
        border-radius: {RADIUS}px;
        padding: 0px;
        min-width: 26px;
        max-width: 26px;
        min-height: 26px;
        max-height: 26px;
        font-size: 13px;
    }}
    QPushButton[role="tool"]:hover {{ background-color: #3c3c40; }}
    QPushButton[role="tool"]:checked {{ background-color: {c.accent}; color: #ffffff; }}

    /* ---- Tabs ----------------------------------------------------------- */
    QTabWidget::pane {{ border: none; background: transparent; }}
    QTabWidget::tab-bar {{ alignment: left; }}
    QTabBar {{ background: transparent; }}
    QTabBar::tab {{
        background-color: transparent;
        color: {c.text_secondary};
        border: 1px solid transparent;
        border-radius: {RADIUS}px;
        padding: 5px 8px;
        margin: 0px 2px 0px 0px;
        min-height: 18px;
    }}
    QTabBar::tab:hover {{ background-color: {c.raised}; color: {c.text}; }}
    QTabBar::tab:selected {{
        background-color: {c.accent};
        color: #ffffff;
        font-weight: 600;
    }}
    #propertiesTabHost {{
        background-color: {c.card};
        border: 1px solid {c.border_subtle};
        border-radius: {RADIUS + 2}px;
    }}

    /* ---- Inputs --------------------------------------------------------- */
    QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox {{
        background-color: {c.input};
        color: {c.text};
        border: 1px solid {c.border};
        border-radius: {RADIUS - 1}px;
        padding: 1px 6px;
        min-height: {CONTROL_HEIGHT - 4}px;
        selection-background-color: {c.accent};
    }}
    QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus {{
        border-color: {c.accent};
    }}
    QDoubleSpinBox:disabled, QSpinBox:disabled, QComboBox:disabled, QLineEdit:disabled {{
        color: {c.text_muted};
        border-color: {c.border_subtle};
    }}
    QDoubleSpinBox::up-button, QSpinBox::up-button {{
        subcontrol-origin: border;
        subcontrol-position: top right;
        width: 14px;
        border-left: 1px solid {c.border};
        border-top-right-radius: {RADIUS - 1}px;
        background: {c.raised};
    }}
    QDoubleSpinBox::down-button, QSpinBox::down-button {{
        subcontrol-origin: border;
        subcontrol-position: bottom right;
        width: 14px;
        border-left: 1px solid {c.border};
        border-bottom-right-radius: {RADIUS - 1}px;
        background: {c.raised};
    }}
    QDoubleSpinBox::up-button:hover, QSpinBox::up-button:hover,
    QDoubleSpinBox::down-button:hover, QSpinBox::down-button:hover {{
        background: #3c3c40;
    }}
    QDoubleSpinBox::up-arrow, QSpinBox::up-arrow {{
        width: 0px; height: 0px;
        border-left: 3px solid transparent;
        border-right: 3px solid transparent;
        border-bottom: 4px solid {c.text_secondary};
    }}
    QDoubleSpinBox::down-arrow, QSpinBox::down-arrow {{
        width: 0px; height: 0px;
        border-left: 3px solid transparent;
        border-right: 3px solid transparent;
        border-top: 4px solid {c.text_secondary};
    }}
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 18px;
        border-left: 1px solid {c.border};
        border-top-right-radius: {RADIUS - 1}px;
        border-bottom-right-radius: {RADIUS - 1}px;
        background: {c.raised};
    }}
    QComboBox::down-arrow {{
        width: 0px; height: 0px;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid {c.text_secondary};
    }}
    QComboBox QAbstractItemView {{
        background-color: {c.panel};
        color: {c.text};
        border: 1px solid {c.border};
        selection-background-color: {c.accent};
        outline: none;
    }}

    QCheckBox, QRadioButton {{ spacing: 7px; background: transparent; }}
    QCheckBox:disabled, QRadioButton:disabled {{ color: {c.text_muted}; }}
    QCheckBox::indicator, QRadioButton::indicator {{
        width: 14px; height: 14px;
        border: 1px solid #55555b;
        background-color: {c.input};
    }}
    QCheckBox::indicator {{ border-radius: 3px; }}
    QRadioButton::indicator {{ border-radius: 8px; }}
    QCheckBox::indicator:hover, QRadioButton::indicator:hover {{ border-color: {c.accent}; }}
    QCheckBox::indicator:checked {{
        background-color: {c.accent};
        border-color: {c.accent};
        image: url(:/qt-project.org/styles/commonstyle/images/checkbox-checked-16.png);
    }}
    QRadioButton::indicator:checked {{
        background-color: {c.input};
        border: 4px solid {c.accent};
    }}
    QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
        border-color: {c.border_subtle};
        background-color: #202022;
    }}
    QRadioButton::indicator:checked:disabled {{ border: 4px solid #4a5a75; }}

    /* ---- Sliders -------------------------------------------------------- */
    QSlider {{ background: transparent; min-height: 20px; }}
    QSlider::groove:horizontal {{
        height: 4px;
        background: #3b3b40;
        border-radius: 2px;
    }}
    QSlider::sub-page:horizontal {{
        background: {c.accent};
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        width: 14px;
        height: 14px;
        margin: -5px 0px;
        border-radius: 7px;
        background: #e8e8ec;
        border: 1px solid #c8c8cc;
    }}
    QSlider::handle:horizontal:hover {{ background: #ffffff; }}
    QSlider::groove:horizontal:disabled {{ background: #2c2c2f; }}
    QSlider::sub-page:horizontal:disabled {{ background: #3a3f4a; }}
    QSlider::handle:horizontal:disabled {{ background: #55555b; border-color: #4a4a4f; }}

    /* ---- Lists & scrollbars -------------------------------------------- */
    QListWidget, QListView {{
        background-color: transparent;
        border: none;
        outline: none;
    }}
    QListWidget::item {{ border: none; }}
    QScrollArea {{ background: transparent; border: none; }}
    QScrollArea > QWidget > QWidget {{ background: transparent; }}
    QAbstractScrollArea::corner {{ background: transparent; }}
    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 2px 2px 2px 0px;
    }}
    QScrollBar::handle:vertical {{
        background: #4a4a50;
        border-radius: 4px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{ background: #5d5d64; }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 10px;
        margin: 0px 2px 2px 2px;
    }}
    QScrollBar::handle:horizontal {{
        background: #4a4a50;
        border-radius: 4px;
        min-width: 24px;
    }}
    QScrollBar::handle:horizontal:hover {{ background: #5d5d64; }}
    QScrollBar::add-line, QScrollBar::sub-line,
    QScrollBar::add-page, QScrollBar::sub-page {{
        background: none;
        border: none;
        width: 0px;
        height: 0px;
    }}

    /* ---- Progress ------------------------------------------------------- */
    QProgressBar {{
        background-color: {c.input};
        border: 1px solid {c.border_subtle};
        border-radius: 4px;
        text-align: center;
        color: {c.text};
        font-size: 11px;
        min-height: 14px;
        max-height: 16px;
    }}
    QProgressBar::chunk {{
        background-color: {c.accent};
        border-radius: 3px;
    }}
    """


def build_palette(c: ThemeColors = COLORS) -> QPalette:
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: c.window,
        QPalette.ColorRole.WindowText: c.text,
        QPalette.ColorRole.Base: c.input,
        QPalette.ColorRole.AlternateBase: c.panel,
        QPalette.ColorRole.ToolTipBase: c.raised,
        QPalette.ColorRole.ToolTipText: c.text,
        QPalette.ColorRole.Text: c.text,
        QPalette.ColorRole.Button: c.raised,
        QPalette.ColorRole.ButtonText: c.text,
        QPalette.ColorRole.BrightText: "#ffffff",
        QPalette.ColorRole.Highlight: c.accent,
        QPalette.ColorRole.HighlightedText: "#ffffff",
        QPalette.ColorRole.Link: c.accent,
        QPalette.ColorRole.PlaceholderText: c.text_muted,
        QPalette.ColorRole.Mid: c.border,
        QPalette.ColorRole.Dark: c.window,
        QPalette.ColorRole.Light: c.raised,
    }
    for role, value in roles.items():
        palette.setColor(role, QColor(value))
    disabled = QPalette.ColorGroup.Disabled
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(disabled, role, QColor(c.text_muted))
    return palette


def apply_theme(app: QApplication) -> None:
    """Install the Fusion base style, dark palette, and stylesheet on *app*."""
    app.setStyle("Fusion")
    app.setPalette(build_palette())
    app.setStyleSheet(build_stylesheet())


def scaled_font(font: QFont, delta: float, *, minimum: float = 7.0) -> QFont:
    """Return a copy of *font* resized by *delta*, working for point or pixel sizes.

    Stylesheets set ``font-size`` in pixels, in which case ``pointSizeF()`` is -1.
    """
    result = QFont(font)
    if result.pointSizeF() > 0:
        result.setPointSizeF(max(result.pointSizeF() + delta, minimum))
    else:
        pixel = result.pixelSize() if result.pixelSize() > 0 else 12
        result.setPixelSize(max(int(round(pixel + delta)), int(minimum)))
    return result


def set_role(widget, role: str) -> None:
    """Set the ``role`` dynamic property used by the stylesheet and refresh styling."""
    widget.setProperty("role", role)
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)
    widget.update()
