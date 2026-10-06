"""Primary application window (V2 layout).

Composition::

    TopBar
    QSplitter: LayersPanel | PreviewWorkspace | PropertiesPanel(Transform, Plot Settings, Device)
    ActionBar

The window keeps every service, slot, and attribute name from V1 so that the
plotting/estimation/project logic and the existing tests are untouched; only
the arrangement of widgets changed.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QColor, QGuiApplication, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from plotpilot.models.artwork_transform import ArtworkTransform, resolve_rotation_degrees
from plotpilot.models.multi_layer_job import MultiLayerJobState, MultiLayerPlotJob
from plotpilot.models.plot_bounds import BoundsStatus, PlotBoundsCheck
from plotpilot.models.plot_job import PlotPhase, PlotState
from plotpilot.models.plot_progress import PlotProgress
from plotpilot.models.plotter_status import PlotterStatus
from plotpilot.models.print_margins import (
    PrintMargins,
    PrintMarginsError,
    max_symmetric_margin_mm,
    printable_area_for,
)
from plotpilot.models.project_session import ProjectSession
from plotpilot.models.svg_document import SvgDocument
from plotpilot.models.svg_layer import SvgLayer
from plotpilot.plotter.axidraw import AxiDrawCliBackend
from plotpilot.plotter.base import PlotterBackend
from plotpilot.services.bounds_service import check_plot_bounds
from plotpilot.services.layer_geometry import LayerGeometryCache
from plotpilot.services.layer_service import layers_for_document
from plotpilot.services.multi_layer_plot_service import MultiLayerPlotService
from plotpilot.services.plotter_service import PlotterService
from plotpilot.services.preview_compute_service import (
    InteractivePreview,
    PreviewComputeService,
    compute_interactive_preview,
)
from plotpilot.services.preview_service import preview_svg_for_layer
from plotpilot.services.preview_work_area import (
    FallbackWorkArea,
    WorkAreaOrientation,
    preview_work_area_is_ambiguous,
    resolve_preview_work_area,
)
from plotpilot.services.project_file_service import (
    ProjectFileError,
    ProjectUnsupportedVersionError,
    read_project_file,
    unmatched_layer_ids,
    write_project_file,
)
from plotpilot.services.settings_service import SettingsService
from plotpilot.services.svg_loader import SvgLoadError, load_svg_from_path
from plotpilot.svg.plot_dimensions import PlotDimensionError, parse_physical_size
from plotpilot.ui.action_bar import ActionBar
from plotpilot.ui.artwork_transform_controls import ArtworkTransformControls
from plotpilot.ui.device_panel import DevicePanel
from plotpilot.ui.layers_panel import LayersPanel, populate_layer_item
from plotpilot.ui.plot_progress_labels import (
    progress_fraction_label,
    progress_headline,
    progress_next_layer_line,
    progress_timing_line,
)
from plotpilot.ui.plot_settings_widget import PlotSettingsWidget
from plotpilot.ui.preview_workspace import PreviewWorkspace
from plotpilot.ui.properties_panel import (
    TAB_DEVICE,
    TAB_PLOT_SETTINGS,
    TAB_TRANSFORM,
    PropertiesPanel,
)
from plotpilot.ui.theme import set_role
from plotpilot.ui.top_bar import TopBar
from plotpilot.ui.transform_slider_mapping import ArtworkBoundsMm, artwork_bounds_from_polylines
from plotpilot.ui.widgets import make_wrapping_label

_PREFERRED_WINDOW_WIDTH = 1240
_PREFERRED_WINDOW_HEIGHT = 800
_MINIMUM_WINDOW_WIDTH = 760
_MINIMUM_WINDOW_HEIGHT = 520

_LAYERS_PANEL_DEFAULT_WIDTH = 220
_PROPERTIES_PANEL_DEFAULT_WIDTH = 356


def window_size_bounds(
    available_width: int | None,
    available_height: int | None,
) -> tuple[tuple[int, int], tuple[int, int]]:
    """Return ``(minimum, initial)`` sizes clamped to the usable screen.

    ``available_*`` should already exclude the menu bar and Dock. The initial
    size stays at the preferred size when that fits, and never exceeds the
    usable screen. The minimum also shrinks on tiny displays so the window is
    always fully visible.
    """
    min_w = _MINIMUM_WINDOW_WIDTH
    min_h = _MINIMUM_WINDOW_HEIGHT
    width = _PREFERRED_WINDOW_WIDTH
    height = _PREFERRED_WINDOW_HEIGHT
    if available_width is not None and available_width > 0:
        min_w = min(min_w, available_width)
        width = min(width, available_width)
    if available_height is not None and available_height > 0:
        min_h = min(min_h, available_height)
        height = min(height, available_height)
    return (min_w, min_h), (max(width, min_w), max(height, min_h))


def splitter_sizes_for_width(
    total_width: int,
    *,
    layers_visible: bool = True,
    layers_width: int = _LAYERS_PANEL_DEFAULT_WIDTH,
    properties_width: int = _PROPERTIES_PANEL_DEFAULT_WIDTH,
) -> list[int]:
    """Initial ``[layers, preview, properties]`` widths; the preview takes the remainder.

    On narrow windows the side panels shrink proportionally so the preview keeps
    at least a third of the width.
    """
    total = max(total_width, 0)
    layers = layers_width if layers_visible else 0
    properties = properties_width
    preview_floor = int(total * 0.38)
    overflow = layers + properties + preview_floor - total
    if overflow > 0:
        side = layers + properties
        if side > 0:
            layers = max(0, layers - overflow * layers // side)
            properties = max(0, properties - (overflow - (layers_width - layers)))
    preview = max(0, total - layers - properties)
    return [layers, preview, properties]


def choose_svg_file(parent: QWidget) -> str | None:
    """Show the production SVG file picker. Returns an absolute path or None if cancelled."""
    file_path, _selected_filter = QFileDialog.getOpenFileName(
        parent,
        "Open SVG…",
        "",
        "SVG files (*.svg)",
    )
    if not file_path:
        return None
    return file_path


def choose_project_file(parent: QWidget) -> str | None:
    file_path, _selected_filter = QFileDialog.getOpenFileName(
        parent,
        "Open Project…",
        "",
        "PlotPilot projects (*.plotpilot)",
    )
    if not file_path:
        return None
    return file_path


def choose_save_project_file(parent: QWidget, *, suggested_name: str = "") -> str | None:
    file_path, _selected_filter = QFileDialog.getSaveFileName(
        parent,
        "Save Project As…",
        suggested_name,
        "PlotPilot projects (*.plotpilot)",
    )
    if not file_path:
        return None
    if not file_path.endswith(".plotpilot"):
        file_path = f"{file_path}.plotpilot"
    return file_path


class MainWindow(QMainWindow):
    """PlotPilot main window."""

    def __init__(
        self,
        *,
        plotter_backend: PlotterBackend | None = None,
        settings_service: SettingsService | None = None,
        svg_file_chooser: Callable[[], str | None] | None = None,
        project_file_chooser: Callable[[], str | None] | None = None,
        save_project_file_chooser: Callable[[], str | None] | None = None,
        auto_detect_interval_ms: int | None = None,
        auto_detect_resume_delay_ms: int | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("PlotPilot")

        self._document: SvgDocument | None = None
        self._layers: list[SvgLayer] = []
        self._updating_layers = False
        self._bounds_check: PlotBoundsCheck | None = None
        self._bounds_rotation_degrees = 0
        self._project_file_path: Path | None = None
        self._project_dirty = False

        backend = plotter_backend if plotter_backend is not None else AxiDrawCliBackend()
        self._settings_service = (
            settings_service if settings_service is not None else SettingsService(parent=self)
        )
        self._svg_file_chooser = svg_file_chooser
        self._project_file_chooser = project_file_chooser
        self._save_project_file_chooser = save_project_file_chooser
        self._plotter_service = PlotterService(
            backend,
            settings_service=self._settings_service,
            auto_detect_interval_ms=auto_detect_interval_ms,
            auto_detect_resume_delay_ms=auto_detect_resume_delay_ms,
            parent=self,
        )
        self._plotter_service.status_changed.connect(self._apply_plotter_status)
        self._plotter_service.plot_state_changed.connect(self._apply_plot_state)
        self._plotter_service.plot_progress_changed.connect(self._apply_plot_progress)
        self._plotter_service.pre_plot_estimate_changed.connect(self._apply_pre_plot_estimate)
        self._plotter_service.manual_command_finished.connect(self._on_manual_command_finished)
        self._multi_layer_service = MultiLayerPlotService(self._plotter_service, parent=self)
        self._multi_layer_service.job_changed.connect(self._apply_multi_layer_job)
        self._multi_layer_service.pen_change_required.connect(self._on_pen_change_required)
        self._geometry_cache = LayerGeometryCache()
        self._preview_compute = PreviewComputeService(parent=self)
        self._preview_compute.finished.connect(self._on_preview_compute_finished)

        self._build_ui()
        self._build_menu()
        self._wire_ui()

        self._sync_preview_empty_state()
        self._apply_plotter_status(self._plotter_service.status)
        self._apply_plot_state(self._plotter_service.plot_state)
        self._apply_plot_progress(self._plotter_service.plot_progress)
        self._apply_multi_layer_job(self._multi_layer_service.job)
        self._refresh_bounds_status()
        self._sync_fallback_work_area_visibility()
        self._sync_print_margin_controls()
        self._refresh_preview_work_area()
        self._update_plot_controls()
        self._plotter_service.start_automatic_monitoring()
        self._update_window_title()
        self._apply_launch_geometry()

    # ------------------------------------------------------------------ build
    def _build_ui(self) -> None:
        content = QWidget(self)
        content.setObjectName("mainContent")
        root_layout = QVBoxLayout(content)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._top_bar = TopBar(content)
        root_layout.addWidget(self._top_bar)

        # ---- Left: layers ------------------------------------------------------
        self._layers_panel = LayersPanel(content)
        self._layers_list = self._layers_panel.list_widget
        self._layers_list.currentRowChanged.connect(self._on_layer_row_changed)
        self._layers_list.itemChanged.connect(self._on_layer_item_changed)
        self._open_svg_persistent_button = self._layers_panel.open_button
        self._open_svg_persistent_button.setVisible(False)

        # ---- Center: workspace -------------------------------------------------
        self._workspace = PreviewWorkspace(content)
        self._preview_stack = self._workspace.stack
        self._preview_empty_page = self._workspace.empty_page
        self._open_svg_empty_button = self._workspace.open_button
        self._preview = self._workspace.preview
        self._preview.artwork_transform_changed.connect(self._on_preview_artwork_dragged)
        self._preview_prep_timer = QTimer(self)
        self._preview_prep_timer.setSingleShot(True)
        self._preview_prep_timer.setInterval(50)
        self._preview_prep_timer.timeout.connect(self._refresh_prepared_preview)

        # ---- Right: properties -------------------------------------------------
        self._artwork_controls = ArtworkTransformControls(content)
        self._artwork_controls.transform_changed.connect(self._on_artwork_controls_changed)
        self._artwork_controls.margins_changed.connect(self._on_print_margins_changed)

        self._fallback_work_area_row = QWidget(content)
        fallback_row = QHBoxLayout(self._fallback_work_area_row)
        fallback_row.setContentsMargins(0, 0, 0, 0)
        fallback_row.setSpacing(6)
        fallback_caption = QLabel("Work area", self._fallback_work_area_row)
        fallback_caption.setProperty("role", "caption")
        fallback_caption.setToolTip(
            "Default (CLI) model has no known travel limits. Pick the page size and "
            "orientation used for the preview and clipping.",
        )
        fallback_row.addWidget(fallback_caption)
        self._fallback_work_area_combo = QComboBox(self._fallback_work_area_row)
        for area in (FallbackWorkArea.A4, FallbackWorkArea.A3):
            self._fallback_work_area_combo.addItem(area.value, area)
        stored_fallback = self._settings_service.preview_fallback_work_area
        fallback_index = self._fallback_work_area_combo.findData(stored_fallback)
        if fallback_index >= 0:
            self._fallback_work_area_combo.setCurrentIndex(fallback_index)
        self._fallback_work_area_combo.currentIndexChanged.connect(
            self._on_fallback_work_area_changed,
        )
        fallback_row.addWidget(self._fallback_work_area_combo, stretch=1)
        self._fallback_work_area_orientation_combo = QComboBox(self._fallback_work_area_row)
        for orientation in (WorkAreaOrientation.PORTRAIT, WorkAreaOrientation.LANDSCAPE):
            self._fallback_work_area_orientation_combo.addItem(orientation.value, orientation)
        stored_orientation = self._settings_service.preview_fallback_work_area_orientation
        orientation_index = self._fallback_work_area_orientation_combo.findData(stored_orientation)
        if orientation_index >= 0:
            self._fallback_work_area_orientation_combo.setCurrentIndex(orientation_index)
        self._fallback_work_area_orientation_combo.currentIndexChanged.connect(
            self._on_fallback_work_area_orientation_changed,
        )
        fallback_row.addWidget(self._fallback_work_area_orientation_combo, stretch=1)
        self._artwork_controls.work_area_slot.addWidget(self._fallback_work_area_row)

        self._bounds_status_label = make_wrapping_label("", content, role="caption")
        self._bounds_status_label.setVisible(False)
        self._artwork_controls.work_area_slot.addWidget(self._bounds_status_label)

        self._plot_settings = PlotSettingsWidget(self._settings_service, parent=content)
        self._plot_settings.user_changed.connect(self._on_plot_settings_changed)

        self._device_panel = DevicePanel(content)

        self._properties_panel = PropertiesPanel(
            transform=self._artwork_controls,
            plot_settings=self._plot_settings,
            device=self._device_panel,
            parent=content,
        )
        self._properties_tabs = self._properties_panel.tabs

        # ---- Splitter ------------------------------------------------------------
        self._splitter = QSplitter(Qt.Orientation.Horizontal, content)
        self._splitter.setObjectName("mainSplitter")
        self._splitter.setChildrenCollapsible(False)
        self._splitter.setHandleWidth(1)
        self._splitter.addWidget(self._layers_panel)
        self._splitter.addWidget(self._workspace)
        self._splitter.addWidget(self._properties_panel)
        # Proportional stretch so shrinking the window never starves the preview.
        self._splitter.setStretchFactor(0, 2)
        self._splitter.setStretchFactor(1, 6)
        self._splitter.setStretchFactor(2, 3)
        self._splitter.setCollapsible(0, True)
        root_layout.addWidget(self._splitter, stretch=1)

        # ---- Bottom: actions -------------------------------------------------------
        self._action_bar = ActionBar(content)
        root_layout.addWidget(self._action_bar)
        bar = self._action_bar
        self._plotter_status_label = bar.plotter_status_label
        self._connect_button = bar.connect_button
        self._pen_up_button = bar.pen_up_button
        self._pen_down_button = bar.pen_down_button
        self._home_button = bar.home_button
        self._motors_off_button = bar.motors_off_button
        self._plotter_refresh_button = bar.refresh_button
        self._plot_layer_button = bar.plot_layer_button
        self._plot_checked_button = bar.plot_checked_button
        self._plot_stop_button = bar.stop_button
        self._plot_stop_button.setEnabled(False)
        self._multi_continue_button = bar.continue_button
        self._estimate_button = bar.estimate_button
        self._estimate_label = bar.estimate_label
        self._status_label = bar.status_label
        self._plot_activity_label = bar.activity_label
        self._plotter_message_label = bar.plotter_message_label
        self._pen_change_label = bar.pen_change_label
        self._plot_progress_headline = bar.progress_headline
        self._plot_progress_bar = bar.progress_bar
        self._plot_progress_timing = bar.progress_timing
        self._plot_progress_next = bar.progress_next

        self.setCentralWidget(content)

    def _wire_ui(self) -> None:
        bar = self._action_bar
        self._pen_up_button.clicked.connect(self._plotter_service.pen_up)
        self._pen_down_button.clicked.connect(self._plotter_service.pen_down)
        self._home_button.clicked.connect(self._on_home)
        self._motors_off_button.clicked.connect(self._on_motors_off)
        self._plotter_refresh_button.clicked.connect(self._plotter_service.refresh)
        bar.connect_button.clicked.connect(self._plotter_service.refresh)
        self._plot_layer_button.clicked.connect(self._on_plot_selected_layer)
        self._plot_checked_button.clicked.connect(self._on_plot_checked_layers)
        self._plot_stop_button.clicked.connect(self._on_stop_plot)
        self._multi_continue_button.clicked.connect(self._on_multi_continue)
        self._estimate_button.clicked.connect(self._on_estimate_plot)

        device = self._device_panel
        device.refresh_requested.connect(self._plotter_service.refresh)
        device.pen_up_requested.connect(self._plotter_service.pen_up)
        device.pen_down_requested.connect(self._plotter_service.pen_down)
        device.home_requested.connect(self._on_home)
        device.motors_off_requested.connect(self._on_motors_off)

        self._open_svg_empty_button.clicked.connect(self._open_svg_action.trigger)
        self._open_svg_persistent_button.clicked.connect(self._open_svg_action.trigger)
        self._open_svg_action.enabledChanged.connect(self._open_svg_empty_button.setEnabled)
        self._open_svg_action.enabledChanged.connect(self._open_svg_persistent_button.setEnabled)
        self._open_svg_action.enabledChanged.connect(self._top_bar.open_button.setEnabled)

        top = self._top_bar
        top.open_requested.connect(self._open_svg_action.trigger)
        top.layers_toggled.connect(self._on_layers_sidebar_toggled)
        top.device_requested.connect(lambda: self._properties_panel.set_current_tab(TAB_DEVICE))

    def _apply_launch_geometry(self) -> None:
        screen = QGuiApplication.primaryScreen()
        available = None if screen is None else screen.availableGeometry().size()
        minimum, initial = window_size_bounds(
            None if available is None else available.width(),
            None if available is None else available.height(),
        )
        self.setMinimumSize(minimum[0], minimum[1])
        self.resize(initial[0], initial[1])
        self._splitter.setSizes(splitter_sizes_for_width(initial[0]))

    @property
    def project_file_path(self) -> Path | None:
        return self._project_file_path

    @property
    def project_dirty(self) -> bool:
        return self._project_dirty

    def closeEvent(self, event) -> None:  # noqa: N802 — Qt API
        self._preview_prep_timer.stop()
        self._preview_compute.shutdown()
        self._plotter_service.shutdown()
        super().closeEvent(event)

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")

        self._open_svg_action = QAction("Open SVG…", self)
        self._open_svg_action.setShortcut(QKeySequence.StandardKey.Open)
        self._open_svg_action.triggered.connect(self._open_svg)
        file_menu.addAction(self._open_svg_action)

        self._open_project_action = QAction("Open Project…", self)
        self._open_project_action.setShortcut(QKeySequence("Ctrl+Shift+O"))
        self._open_project_action.triggered.connect(self._open_project)
        file_menu.addAction(self._open_project_action)

        file_menu.addSeparator()

        self._save_project_action = QAction("Save Project", self)
        self._save_project_action.setShortcut(QKeySequence.StandardKey.Save)
        self._save_project_action.triggered.connect(self._save_project)
        file_menu.addAction(self._save_project_action)

        self._save_project_as_action = QAction("Save Project As…", self)
        self._save_project_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self._save_project_as_action.triggered.connect(self._save_project_as)
        file_menu.addAction(self._save_project_as_action)

        view_menu = self.menuBar().addMenu("&View")
        self._toggle_layers_action = QAction("Layers Sidebar", self)
        self._toggle_layers_action.setCheckable(True)
        self._toggle_layers_action.setChecked(True)
        self._toggle_layers_action.setShortcut(QKeySequence("Ctrl+Shift+L"))
        self._toggle_layers_action.toggled.connect(self._top_bar.layers_button.setChecked)
        view_menu.addAction(self._toggle_layers_action)
        view_menu.addSeparator()
        fit_action = QAction("Fit Preview", self)
        fit_action.setShortcut(QKeySequence("Ctrl+0"))
        fit_action.triggered.connect(self._preview.fit_view)
        view_menu.addAction(fit_action)
        zoom_in_action = QAction("Zoom In", self)
        zoom_in_action.setShortcut(QKeySequence.StandardKey.ZoomIn)
        zoom_in_action.triggered.connect(self._preview.zoom_in)
        view_menu.addAction(zoom_in_action)
        zoom_out_action = QAction("Zoom Out", self)
        zoom_out_action.setShortcut(QKeySequence.StandardKey.ZoomOut)
        zoom_out_action.triggered.connect(self._preview.zoom_out)
        view_menu.addAction(zoom_out_action)
        view_menu.addSeparator()
        for label, index in (
            ("Transform", TAB_TRANSFORM),
            ("Plot Settings", TAB_PLOT_SETTINGS),
            ("Device", TAB_DEVICE),
        ):
            action = QAction(label, self)
            action.setShortcut(QKeySequence(f"Ctrl+{index + 1}"))
            action.triggered.connect(
                lambda _checked=False, i=index: self._properties_panel.set_current_tab(i),
            )
            view_menu.addAction(action)

    # ------------------------------------------------------------- navigation
    def _on_layers_sidebar_toggled(self, visible: bool) -> None:
        self._layers_panel.setVisible(visible)
        if self._toggle_layers_action.isChecked() != visible:
            self._toggle_layers_action.setChecked(visible)

    # ------------------------------------------------------------- properties
    @property
    def document(self) -> SvgDocument | None:
        return self._document

    @property
    def layers(self) -> list[SvgLayer]:
        return list(self._layers)

    @property
    def current_preview_svg(self) -> str | None:
        return self._preview.last_svg

    @property
    def plotter_service(self) -> PlotterService:
        return self._plotter_service

    @property
    def multi_layer_service(self) -> MultiLayerPlotService:
        return self._multi_layer_service

    # ------------------------------------------------------------ plotter UI
    def _apply_plotter_status(self, status: PlotterStatus) -> None:
        self._action_bar.set_connection_state(status.state)
        model_name = self._plot_settings.current_model_name()
        self._top_bar.set_device(model_name, status.state)
        self._device_panel.apply_status(status, model_name=model_name)
        plotter_idle = not self._plotter_service.plot_state.is_active
        job_idle = not self._multi_layer_service.job.is_active
        if plotter_idle and job_idle:
            self._plotter_message_label.setText(status.message)
        self._update_plot_controls()

    def _apply_plot_state(self, state: PlotState) -> None:
        job = self._multi_layer_service.job
        if job.is_active and state.phase is not PlotPhase.STOPPING:
            self._plot_activity_label.setText("")
            self._update_plot_controls()
            return
        if state.phase is PlotPhase.STOPPING:
            self._plot_activity_label.setText(state.message)
        elif state.phase in (PlotPhase.SUCCEEDED, PlotPhase.FAILED, PlotPhase.CANCELLED):
            self._plot_activity_label.setText(state.message)
        elif state.phase is PlotPhase.IDLE:
            self._plot_activity_label.setText(state.message)
        else:
            self._plot_activity_label.setText("")
        self._update_plot_controls()

    def _apply_plot_progress(self, progress: PlotProgress) -> None:
        job = self._multi_layer_service.job
        if job.state is MultiLayerJobState.WAITING_FOR_PEN_CHANGE:
            self._set_plot_progress_visible(False)
            return
        if not progress.is_visible:
            self._set_plot_progress_visible(False)
            return
        self._set_plot_progress_visible(True)
        headline = progress_headline(progress)
        self._plot_progress_headline.setText(headline)
        fraction_label = progress_fraction_label(progress)
        if progress.estimated_fraction is not None:
            value = int(round(progress.estimated_fraction * 100))
            self._plot_progress_bar.setRange(0, 100)
            self._plot_progress_bar.setValue(min(100, max(0, value)))
            self._plot_progress_bar.setFormat(fraction_label)
        else:
            self._plot_progress_bar.setRange(0, 0)
            self._plot_progress_bar.setFormat(fraction_label or "")
        self._plot_progress_timing.setText(progress_timing_line(progress))
        next_line = progress_next_layer_line(progress)
        self._plot_progress_next.setText(next_line)
        self._plot_progress_next.setVisible(bool(next_line))

    def _set_plot_progress_visible(self, visible: bool) -> None:
        self._action_bar.progress_row.setVisible(visible)
        self._plot_progress_headline.setVisible(visible)
        self._plot_progress_bar.setVisible(visible)
        self._plot_progress_timing.setVisible(visible)
        if not visible:
            self._plot_progress_next.setVisible(False)
            self._plot_progress_bar.setRange(0, 100)
            self._plot_progress_bar.setValue(0)

    def _apply_multi_layer_job(self, job: MultiLayerPlotJob) -> None:
        if job.state is MultiLayerJobState.IDLE:
            self._set_pen_change_visible(False)
            return

        if job.state is MultiLayerJobState.WAITING_FOR_PEN_CHANGE:
            self._plot_activity_label.setText(job.progress_label)
            self._update_pen_change_panel(job)
            self._set_pen_change_visible(True)
        elif job.state is MultiLayerJobState.PLOTTING:
            self._set_pen_change_visible(False)
            self._plot_activity_label.setText(job.progress_label)
        else:
            self._set_pen_change_visible(False)
            self._plot_activity_label.setText(job.message)
        self._update_plot_controls()

    def _set_pen_change_visible(self, visible: bool) -> None:
        self._action_bar.pen_change_banner.setVisible(visible)
        self._pen_change_label.setVisible(visible)
        self._multi_continue_button.setVisible(visible)

    def _update_pen_change_panel(self, job: MultiLayerPlotJob) -> None:
        nxt = job.current_layer
        if nxt is None:
            self._pen_change_label.setText("")
            return
        swatch = _color_swatch_text(nxt.representative_color)
        if nxt.representative_color:
            body = (
                f"Layer {job.completed_count} complete — next layer: {swatch} {nxt.name}. "
                f"Change the pen to {nxt.name}, then press Continue."
            )
        else:
            human = job.current_index + 1
            body = (
                f"Layer {job.completed_count} complete — next layer: Layer {human}. "
                "Change the pen for the next layer, then press Continue."
            )
        self._pen_change_label.setText(body)

    def _on_pen_change_required(self, _next_layer: object) -> None:
        self._apply_multi_layer_job(self._multi_layer_service.job)

    def _update_plot_controls(self) -> None:
        plot_state = self._plotter_service.plot_state
        plot_active = plot_state.is_active
        stopping = plot_state.phase is PlotPhase.STOPPING
        job = self._multi_layer_service.job
        job_active = job.is_active
        job_blocks_ui = job_active or job.state in (
            MultiLayerJobState.COMPLETED,
            MultiLayerJobState.CANCELLED,
            MultiLayerJobState.ERROR,
        )
        layer = self._current_layer()
        checked = self._checked_layers()
        can_start = (
            self._document is not None
            and self._plotter_service.status.is_connected
            and not plot_active
            and not job_active
        )
        bounds_block = self._bounds_check is not None and self._bounds_check.blocks_plotting
        can_plot_single = can_start and layer is not None and not bounds_block
        can_plot_multi = can_start and len(checked) >= 1 and not bounds_block
        self._plot_layer_button.setEnabled(can_plot_single)
        self._plot_checked_button.setEnabled(can_plot_multi)
        stop_enabled = (plot_active or job_active) and not stopping
        self._plot_stop_button.setEnabled(stop_enabled)
        if job_active and job.state is MultiLayerJobState.WAITING_FOR_PEN_CHANGE:
            self._plot_stop_button.setText("Stop Job")
        else:
            self._plot_stop_button.setText("Stop")
        self._multi_continue_button.setEnabled(
            job.state is MultiLayerJobState.WAITING_FOR_PEN_CHANGE
            and not plot_active
            and not stopping
        )
        refresh_ok = not plot_active and not job_active
        self._plotter_refresh_button.setEnabled(refresh_ok)
        self._connect_button.setEnabled(refresh_ok)
        self._device_panel.set_refresh_enabled(refresh_ok)
        pen_ok = (
            self._plotter_service.status.pen_commands_enabled
            and not plot_active
            and not job_active
            and not stopping
        )
        manual_busy = self._plotter_service.manual_command_active
        pen_ok = pen_ok and not manual_busy
        self._pen_up_button.setEnabled(pen_ok)
        self._pen_down_button.setEnabled(pen_ok)
        self._home_button.setEnabled(pen_ok)
        self._motors_off_button.setEnabled(pen_ok)
        self._device_panel.set_manual_controls_enabled(pen_ok)
        self._estimate_button.setEnabled(
            self._document is not None
            and (layer is not None or len(checked) >= 1)
            and not plot_active
            and not job_active
            and not stopping
            and not manual_busy
        )
        settings_locked = plot_active or job_active
        self._plot_settings.set_plotting_active(settings_locked)
        transform_locked = plot_active or job_active
        self._preview.set_transform_controls_enabled(not transform_locked)
        self._artwork_controls.setEnabled(not transform_locked)
        self._open_svg_action.setEnabled(not job_active)
        has_document = self._document is not None
        self._save_project_action.setEnabled(has_document and not job_active)
        self._save_project_as_action.setEnabled(has_document and not job_active)
        self._open_project_action.setEnabled(not job_active)
        allow_preview = job.state is MultiLayerJobState.WAITING_FOR_PEN_CHANGE
        self._layers_list.setEnabled(not job_active or allow_preview)
        self._updating_layers = True
        for row in range(self._layers_list.count()):
            item = self._layers_list.item(row)
            if item is None:
                continue
            flags = item.flags()
            if job_active:
                item.setFlags(flags & ~Qt.ItemFlag.ItemIsUserCheckable)
            else:
                item.setFlags(flags | Qt.ItemFlag.ItemIsUserCheckable)
        self._updating_layers = False
        if job_blocks_ui and job.state in (
            MultiLayerJobState.COMPLETED,
            MultiLayerJobState.CANCELLED,
            MultiLayerJobState.ERROR,
        ):
            self._open_svg_action.setEnabled(True)
            self._layers_list.setEnabled(True)

    def _current_layer(self) -> SvgLayer | None:
        if self._document is None or not self._layers:
            return None
        row = self._layers_list.currentRow()
        if row < 0 or row >= len(self._layers):
            return None
        return self._layers[row]

    def _checked_layers(self) -> list[SvgLayer]:
        if not self._layers:
            return []
        selected: list[SvgLayer] = []
        for row in range(self._layers_list.count()):
            item = self._layers_list.item(row)
            if item is None:
                continue
            if item.checkState() is not Qt.CheckState.Checked:
                continue
            if 0 <= row < len(self._layers):
                selected.append(self._layers[row])
        return selected

    def _on_home(self) -> None:
        error = self._plotter_service.home()
        if error:
            self._plotter_message_label.setText(error)
        self._update_plot_controls()

    def _on_motors_off(self) -> None:
        error = self._plotter_service.motors_off()
        if error:
            self._plotter_message_label.setText(error)
        self._update_plot_controls()

    def _on_manual_command_finished(self, _name: str, _result: object) -> None:
        self._update_plot_controls()

    def _on_estimate_plot(self) -> None:
        document = self._document
        if document is None:
            return
        checked = self._checked_layers()
        if checked:
            layers = checked
        else:
            selected = self._current_layer()
            layers = [selected] if selected is not None else []
        error = self._plotter_service.request_pre_plot_estimate(
            document,
            layers,
            plot_settings=self._settings_service.plot_settings,
            artwork_transform=self._preview.artwork_transform,
            fallback_work_area=self._settings_service.preview_fallback_work_area,
            fallback_work_area_orientation=(
                self._settings_service.preview_fallback_work_area_orientation
            ),
            print_margins=self._settings_service.print_margins,
        )
        if error:
            self._estimate_label.setText(error)
        self._update_plot_controls()

    def _apply_pre_plot_estimate(self, report: object) -> None:
        summary = getattr(report, "summary", "")
        self._estimate_label.setText(str(summary))
        self._update_plot_controls()

    def _on_plot_selected_layer(self) -> None:
        if self._plotter_service.plot_state.is_active or self._multi_layer_service.job.is_active:
            return
        layer = self._current_layer()
        document = self._document
        if document is None or layer is None:
            return

        confirm = QMessageBox.question(
            self,
            "Plot layer",
            f'Plot layer "{layer.name}"?\n\nThis will move the AxiDraw physically.',
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Ok,
            QMessageBox.StandardButton.Cancel,
        )
        if confirm != QMessageBox.StandardButton.Ok:
            return

        error = self._plotter_service.start_plot_layer(
            document,
            layer,
            plot_settings=self._settings_service.plot_settings,
            artwork_transform=self._preview.artwork_transform,
            fallback_work_area=self._settings_service.preview_fallback_work_area,
            fallback_work_area_orientation=(
                self._settings_service.preview_fallback_work_area_orientation
            ),
            print_margins=self._settings_service.print_margins,
        )
        if error is not None:
            QMessageBox.warning(self, "Cannot plot", error)
            self._update_plot_controls()

    def _on_plot_checked_layers(self) -> None:
        if self._plotter_service.plot_state.is_active or self._multi_layer_service.job.is_active:
            return
        document = self._document
        layers = self._checked_layers()
        if document is None or not layers:
            return

        order_lines = "\n".join(
            f"{index}. {layer.name}" for index, layer in enumerate(layers, start=1)
        )
        confirm = QMessageBox.question(
            self,
            "Plot checked layers",
            (
                f"Plot {len(layers)} layers?\n\n"
                "The AxiDraw will move physically.\n"
                "PlotPilot will pause between each layer so you can change pens.\n\n"
                f"Order:\n{order_lines}"
            ),
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Ok,
            QMessageBox.StandardButton.Cancel,
        )
        if confirm != QMessageBox.StandardButton.Ok:
            return

        settings = self._settings_service.plot_settings
        error = self._multi_layer_service.start_job(
            document,
            layers,
            settings=settings,
            artwork_transform=self._preview.artwork_transform,
            fallback_work_area=self._settings_service.preview_fallback_work_area,
            fallback_work_area_orientation=(
                self._settings_service.preview_fallback_work_area_orientation
            ),
            print_margins=self._settings_service.print_margins,
        )
        if error is not None:
            QMessageBox.warning(self, "Cannot plot", error)
        self._update_plot_controls()

    def _on_multi_continue(self) -> None:
        error = self._multi_layer_service.continue_after_pen_change()
        if error is not None:
            QMessageBox.warning(self, "Cannot continue", error)
        self._update_plot_controls()

    def _on_stop_plot(self) -> None:
        if self._multi_layer_service.job.is_active:
            self._multi_layer_service.stop_job()
            return
        self._plotter_service.request_safe_stop()

    # ------------------------------------------------------------ documents
    def _open_svg(self) -> None:
        if self._multi_layer_service.job.is_active:
            return
        if self._svg_file_chooser is not None:
            chosen = self._svg_file_chooser()
        else:
            chosen = choose_svg_file(self)
        if not chosen:
            return
        self._load_svg_document(Path(chosen), reset_transform=True, clear_project=True)

    def _open_project(self) -> None:
        if self._multi_layer_service.job.is_active:
            return
        if self._project_file_chooser is not None:
            chosen = self._project_file_chooser()
        else:
            chosen = choose_project_file(self)
        if not chosen:
            return
        project_path = Path(chosen)
        try:
            session = read_project_file(project_path)
        except ProjectUnsupportedVersionError as exc:
            QMessageBox.warning(self, "Cannot open project", exc.user_message)
            return
        except ProjectFileError as exc:
            QMessageBox.warning(self, "Cannot open project", exc.user_message)
            return

        if not session.svg_path.is_file():
            QMessageBox.warning(
                self,
                "Cannot open project",
                (
                    "The source SVG for this project could not be found:\n\n"
                    f"{session.svg_path}\n\n"
                    "The current document was not changed."
                ),
            )
            return

        try:
            document = load_svg_from_path(session.svg_path)
        except SvgLoadError as exc:
            QMessageBox.warning(self, "Could not open SVG", exc.user_message)
            return

        self._settings_service.begin_project_session(
            session.plot_settings,
            session.fallback_work_area,
            session.fallback_work_area_orientation,
            print_margins=session.print_margins,
        )
        self._sync_fallback_combo_from_service()
        self._sync_print_margin_controls()
        self._apply_document(document, reset_transform=False)
        self._set_artwork_transform(session.artwork_transform, mark_dirty=False)
        self._restore_checked_layer_ids(session.checked_layer_ids)
        self._project_file_path = project_path.resolve()
        self._project_dirty = False
        self._update_window_title()

        missing = unmatched_layer_ids(session, {layer.layer_id for layer in self._layers})
        if missing:
            self._status_label.setText(
                f"{document.name}\nSome saved layers were not found in the SVG and were skipped.",
            )
        else:
            self._status_label.setText(document.name)
        self._refresh_bounds_status()
        self._update_plot_controls()

    def _load_svg_document(
        self,
        path: Path,
        *,
        reset_transform: bool,
        clear_project: bool,
    ) -> None:
        try:
            document = load_svg_from_path(path)
        except SvgLoadError as exc:
            QMessageBox.warning(
                self,
                "Could not open SVG",
                exc.user_message,
            )
            return

        if clear_project:
            self._clear_project_association()
        self._apply_document(document, reset_transform=reset_transform)
        self._refresh_bounds_status()
        self._update_plot_controls()

    def _clear_project_association(self) -> None:
        if self._settings_service.project_session_active:
            self._settings_service.end_project_session()
            self._sync_fallback_combo_from_service()
            self._sync_print_margin_controls()
        self._project_file_path = None
        self._project_dirty = False
        self._update_window_title()

    def _build_project_session(self) -> ProjectSession | None:
        document = self._document
        if document is None:
            return None
        checked_ids = tuple(layer.layer_id for layer in self._checked_layers())
        return ProjectSession(
            svg_path=document.path,
            checked_layer_ids=checked_ids,
            artwork_transform=self._preview.artwork_transform,
            plot_settings=self._settings_service.plot_settings,
            fallback_work_area=self._settings_service.preview_fallback_work_area,
            fallback_work_area_orientation=(
                self._settings_service.preview_fallback_work_area_orientation
            ),
            print_margins=self._settings_service.print_margins,
        )

    def _save_project(self) -> None:
        if self._document is None:
            return
        if self._project_file_path is None:
            self._save_project_as()
            return
        self._save_project_at_path(self._project_file_path)

    def _save_project_as(self) -> None:
        if self._document is None:
            return
        suggested = ""
        if self._project_file_path is not None:
            suggested = str(self._project_file_path)
        elif self._document is not None:
            suggested = str(self._document.path.with_suffix(".plotpilot"))
        if self._save_project_file_chooser is not None:
            chosen = self._save_project_file_chooser()
        else:
            chosen = choose_save_project_file(self, suggested_name=suggested)
        if not chosen:
            return
        path = Path(chosen)
        if not self._settings_service.project_session_active:
            self._settings_service.begin_project_session(
                self._settings_service.plot_settings,
                self._settings_service.preview_fallback_work_area,
                self._settings_service.preview_fallback_work_area_orientation,
                print_margins=self._settings_service.print_margins,
            )
        self._save_project_at_path(path)

    def _save_project_at_path(self, path: Path) -> None:
        session = self._build_project_session()
        if session is None:
            return
        try:
            write_project_file(path, session)
        except OSError as exc:
            QMessageBox.warning(
                self,
                "Could not save project",
                f"Could not write the project file:\n\n{exc}",
            )
            return
        self._project_file_path = path.resolve()
        self._project_dirty = False
        self._update_window_title()
        self._status_label.setText(self._document.name if self._document else "")

    def _restore_checked_layer_ids(self, checked_ids: tuple[str, ...]) -> None:
        wanted = set(checked_ids)
        self._updating_layers = True
        for row in range(self._layers_list.count()):
            item = self._layers_list.item(row)
            if item is None:
                continue
            layer_id = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(layer_id, str) and layer_id in wanted:
                item.setCheckState(Qt.CheckState.Checked)
            else:
                item.setCheckState(Qt.CheckState.Unchecked)
        self._updating_layers = False
        self._update_plot_controls()

    def _sync_fallback_combo_from_service(self) -> None:
        stored_fallback = self._settings_service.preview_fallback_work_area
        fallback_index = self._fallback_work_area_combo.findData(stored_fallback)
        if fallback_index >= 0:
            self._fallback_work_area_combo.blockSignals(True)
            self._fallback_work_area_combo.setCurrentIndex(fallback_index)
            self._fallback_work_area_combo.blockSignals(False)
        stored_orientation = self._settings_service.preview_fallback_work_area_orientation
        orientation_index = self._fallback_work_area_orientation_combo.findData(stored_orientation)
        if orientation_index >= 0:
            self._fallback_work_area_orientation_combo.blockSignals(True)
            self._fallback_work_area_orientation_combo.setCurrentIndex(orientation_index)
            self._fallback_work_area_orientation_combo.blockSignals(False)

    def _mark_project_dirty(self) -> None:
        if self._document is None:
            return
        if not self._project_dirty:
            self._project_dirty = True
            self._update_window_title()

    def _update_window_title(self) -> None:
        dirty_suffix = " *" if self._project_dirty else ""
        if self._project_file_path is not None:
            self.setWindowTitle(f"PlotPilot — {self._project_file_path.name}{dirty_suffix}")
            return
        if self._document is not None:
            self.setWindowTitle(f"PlotPilot — {self._document.name}{dirty_suffix}")
            return
        self.setWindowTitle("PlotPilot")

    def _sync_preview_empty_state(self) -> None:
        has_document = self._document is not None
        self._workspace.show_document(has_document)
        self._open_svg_persistent_button.setVisible(has_document)

    def _apply_document(self, document: SvgDocument, *, reset_transform: bool = True) -> None:
        if reset_transform:
            transform = ArtworkTransform.identity()
            transform.validate()
            self._preview.set_artwork_transform(transform)
            self._sync_artwork_controls_from_preview()
        self._preview.fit_view()
        self._document = document
        self._layers = layers_for_document(document)
        self._status_label.setText(document.name)
        self._sync_preview_empty_state()
        self._refresh_layers_list()
        self._update_window_title()

    def set_document(self, document: SvgDocument) -> None:
        """Replace the active document and layer list (used after successful load)."""
        self._apply_document(document, reset_transform=True)
        self._refresh_bounds_status()
        self._update_plot_controls()

    def _refresh_layers_list(self) -> None:
        self._updating_layers = True
        self._layers_list.blockSignals(True)
        self._layers_list.clear()
        for index, layer in enumerate(self._layers, start=1):
            item = QListWidgetItem()
            populate_layer_item(item, layer, index)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._layers_list.addItem(item)
        if self._layers_list.count() > 0:
            self._layers_list.setCurrentRow(0)
        self._layers_list.blockSignals(False)
        self._updating_layers = False
        self._layers_panel.set_layer_count(len(self._layers))
        self._update_preview_for_current_layer()
        self._update_plot_controls()

    def _on_layer_row_changed(self, _row: int) -> None:
        if self._updating_layers:
            return
        self._update_preview_for_current_layer()
        self._update_plot_controls()

    def _on_layer_item_changed(self, item: QListWidgetItem) -> None:
        if self._updating_layers:
            return
        if self._multi_layer_service.job.is_active:
            return
        _ = item
        self._mark_project_dirty()
        self._update_plot_controls()

    # --------------------------------------------------------------- preview
    def _update_preview_for_current_layer(self) -> None:
        if self._document is None or not self._layers:
            self._preview.clear_preview()
            return

        row = self._layers_list.currentRow()
        if row < 0 or row >= len(self._layers):
            self._preview.clear_preview("Select a layer to preview.")
            return

        layer = self._layers[row]
        svg_text = preview_svg_for_layer(self._document, layer)
        self._preview.set_preview_svg(svg_text)
        self._geometry_cache.invalidate()
        self._preview.clear_clipped_plot()
        self._schedule_prepared_preview_refresh()

    def _schedule_prepared_preview_refresh(self) -> None:
        if self._document is None or not self._layers:
            return
        if self._preview.last_svg is None:
            return
        # The ghost already follows the live transform; hide the stale clipped ink
        # until the asynchronous clip catches up so two copies are never shown.
        self._preview.set_clip_pending()
        self._preview_prep_timer.start()

    def _refresh_prepared_preview(self) -> None:
        if self._preview.message is not None and self._preview.last_svg is None:
            self._preview.set_work_area_overlay(
                svg_width_mm=0.0,
                svg_height_mm=0.0,
                work_area=None,
            )
            return

        if self._document is None or not self._layers:
            return

        row = self._layers_list.currentRow()
        if row < 0 or row >= len(self._layers):
            return

        document = self._document
        layer = self._layers[row]
        transform = self._preview.artwork_transform
        plot_settings = self._settings_service.plot_settings
        fallback = self._settings_service.preview_fallback_work_area
        fallback_orientation = self._settings_service.preview_fallback_work_area_orientation
        print_margins = self._settings_service.print_margins
        cached = self._geometry_cache.lookup(id(document), layer.layer_id)

        def operation() -> InteractivePreview:
            return compute_interactive_preview(
                document,
                layer,
                cached_geometry=cached,
                transform=transform,
                plot_settings=plot_settings,
                fallback=fallback,
                fallback_orientation=fallback_orientation,
                print_margins=print_margins,
            )

        self._preview_compute.submit(operation)

    def _on_preview_compute_finished(self, generation: int, result: object) -> None:
        if not self._preview_compute.gate.accept(generation):
            return
        if isinstance(result, Exception):
            message = str(result) or "Preview preparation failed."
            self._preview.set_clipped_plot(
                polylines=(),
                error_message=message,
                status_lines=(message,),
            )
            return
        if not isinstance(result, InteractivePreview):
            return
        if self._document is None or id(self._document) != result.document_id:
            return
        if result.fresh_geometry is not None:
            self._geometry_cache.prepare_count += 1
            self._geometry_cache.store(
                result.document_id,
                result.layer_id,
                result.fresh_geometry,
            )
        self._geometry_cache.clip_count += 1
        geometry = result.fresh_geometry or self._geometry_cache.lookup(
            result.document_id, result.layer_id
        )
        self._preview.set_context_polylines(geometry.polylines if geometry is not None else None)
        if result.page_width_mm > 0 and result.page_height_mm > 0 and result.work_area is not None:
            self._preview.set_work_area_overlay(
                svg_width_mm=result.page_width_mm,
                svg_height_mm=result.page_height_mm,
                work_area=result.work_area,
                printable_area=result.printable_area,
            )
        else:
            self._preview.set_work_area_overlay(
                svg_width_mm=0.0,
                svg_height_mm=0.0,
                work_area=None,
            )
        self._preview.set_clipped_plot(
            polylines=result.clipped.polylines,
            error_message=result.clipped.error_message,
            status_lines=result.status_lines,
        )
        self._refresh_artwork_transform_panel()

    def _on_plot_settings_changed(self) -> None:
        self._mark_project_dirty()
        self._sync_fallback_work_area_visibility()
        self._refresh_bounds_status()
        self._apply_margin_limits()
        self._refresh_artwork_transform_panel()
        self._schedule_prepared_preview_refresh()
        self._apply_plotter_status(self._plotter_service.status)

    def _on_fallback_work_area_changed(self, _index: int) -> None:
        area = _coerce_fallback_work_area(self._fallback_work_area_combo.currentData())
        if area is None:
            return
        self._settings_service.set_preview_fallback_work_area(area)
        self._mark_project_dirty()
        self._apply_margin_limits()
        self._refresh_artwork_transform_panel()
        self._schedule_prepared_preview_refresh()

    def _on_fallback_work_area_orientation_changed(self, _index: int) -> None:
        orientation = _coerce_work_area_orientation(
            self._fallback_work_area_orientation_combo.currentData(),
        )
        if orientation is None:
            return
        self._settings_service.set_preview_fallback_work_area_orientation(orientation)
        self._mark_project_dirty()
        self._apply_margin_limits()
        self._refresh_artwork_transform_panel()
        self._schedule_prepared_preview_refresh()

    def _sync_fallback_work_area_visibility(self) -> None:
        show = preview_work_area_is_ambiguous(self._settings_service.plot_settings)
        self._fallback_work_area_row.setVisible(show)

    def _refresh_preview_work_area(self) -> None:
        if self._preview.message is not None or self._preview.last_svg is None:
            self._preview.set_work_area_overlay(
                svg_width_mm=0.0,
                svg_height_mm=0.0,
                work_area=None,
            )
            return
        self._refresh_prepared_preview()

    def _refresh_artwork_transform_panel(self) -> None:
        work_area = resolve_preview_work_area(
            self._settings_service.plot_settings,
            fallback=self._settings_service.preview_fallback_work_area,
            fallback_orientation=self._settings_service.preview_fallback_work_area_orientation,
        )
        if work_area is None:
            self._artwork_controls.set_plot_area_text("")
            self._artwork_controls.set_printable_text("Printable: —")
            self._artwork_controls.set_status_lines([])
            return
        self._artwork_controls.set_work_area_dimensions(
            work_area.width_mm,
            work_area.height_mm,
        )
        self._artwork_controls.set_page_dimensions(*self._document_page_mm())
        self._artwork_controls.set_artwork_bounds(self._current_artwork_bounds())
        if work_area.from_fallback:
            orientation = self._settings_service.preview_fallback_work_area_orientation
            plot_line = (
                f"Plot area: {self._settings_service.preview_fallback_work_area.value} "
                f"{orientation.value} — {work_area.label.split(' — ', 1)[-1]}"
            )
        else:
            plot_line = f"Plot area: {work_area.label}"
        status_lines: list[str] = []
        if work_area.from_fallback:
            status_lines.append("User-defined work area (not verified hardware).")
        for line in self._preview.status_lines:
            if line not in status_lines and line != plot_line:
                status_lines.append(line)
        self._artwork_controls.set_plot_area_text(plot_line)
        self._artwork_controls.set_printable_text(self._printable_size_text(work_area))
        self._artwork_controls.set_status_lines(status_lines)
        if self._document is not None and (
            self._effective_rotation_degrees() != self._bounds_rotation_degrees
        ):
            # Auto-rotate can flip when the page, work area, or margins change.
            self._refresh_bounds_status()

    def _document_page_mm(self) -> tuple[float, float]:
        """Unrotated page size of the current document; (0, 0) when unknown."""
        document = self._document
        if document is None:
            return 0.0, 0.0
        layer = self._current_layer()
        if layer is not None:
            geometry = self._geometry_cache.lookup(id(document), layer.layer_id)
            if geometry is not None and geometry.page_width_mm > 0 and geometry.page_height_mm > 0:
                return geometry.page_width_mm, geometry.page_height_mm
        try:
            physical = parse_physical_size(document.raw_text)
        except PlotDimensionError:
            return 0.0, 0.0
        return physical.width_mm, physical.height_mm

    def _effective_rotation_degrees(self) -> int:
        """Rotation the pipeline applies for the current orientation, page, and margins.

        Computed from the same inputs as the preview/plot pipeline so it does not
        depend on the refresh order of the Transform tab widgets.
        """
        orientation = self._preview.artwork_transform.orientation
        page_w, page_h = self._document_page_mm()
        if page_w <= 0 or page_h <= 0:
            return 0
        work_area = resolve_preview_work_area(
            self._settings_service.plot_settings,
            fallback=self._settings_service.preview_fallback_work_area,
            fallback_orientation=self._settings_service.preview_fallback_work_area_orientation,
        )
        if work_area is None:
            return 0
        try:
            area = printable_area_for(
                work_area.width_mm,
                work_area.height_mm,
                self._settings_service.print_margins,
            )
        except PrintMarginsError:
            return 0
        return resolve_rotation_degrees(
            orientation,
            page_width_mm=page_w,
            page_height_mm=page_h,
            printable_width_mm=area.width_mm,
            printable_height_mm=area.height_mm,
        )

    def _current_artwork_bounds(self) -> ArtworkBoundsMm:
        """Unscaled document-mm extent of the selected layer, before placement."""
        document = self._document
        layer = self._current_layer()
        if document is None or layer is None:
            return ArtworkBoundsMm.origin_point()
        geometry = self._geometry_cache.lookup(id(document), layer.layer_id)
        if geometry is None:
            return ArtworkBoundsMm.origin_point()
        bounds = artwork_bounds_from_polylines(geometry.polylines)
        if bounds is None:
            return ArtworkBoundsMm.origin_point()
        return bounds

    def _printable_size_text(self, work_area: object) -> str:
        width = getattr(work_area, "width_mm", None)
        height = getattr(work_area, "height_mm", None)
        if not isinstance(width, float) or not isinstance(height, float):
            return "Printable: —"
        try:
            area = printable_area_for(width, height, self._settings_service.print_margins)
        except PrintMarginsError:
            return "Printable: —"
        return f"Printable: {area.size_label()}"

    def _sync_print_margin_controls(self) -> None:
        self._artwork_controls.set_print_margins(self._settings_service.print_margins)
        self._apply_margin_limits()
        self._refresh_artwork_transform_panel()

    def _apply_margin_limits(self) -> None:
        work_area = resolve_preview_work_area(
            self._settings_service.plot_settings,
            fallback=self._settings_service.preview_fallback_work_area,
            fallback_orientation=self._settings_service.preview_fallback_work_area_orientation,
        )
        if work_area is None:
            return
        clamped = self._artwork_controls.set_margin_ranges(
            max_symmetric_margin_mm(work_area.width_mm),
            max_symmetric_margin_mm(work_area.height_mm),
        )
        if clamped is None:
            return
        self._settings_service.set_print_margins(clamped)
        self._mark_project_dirty()
        self._schedule_prepared_preview_refresh()

    def _on_print_margins_changed(self, margins: object) -> None:
        if not isinstance(margins, PrintMargins):
            return
        try:
            margins.validate()
        except PrintMarginsError:
            return
        if margins == self._settings_service.print_margins:
            self._refresh_artwork_transform_panel()
            return
        self._settings_service.set_print_margins(margins)
        self._estimate_label.setText("")
        self._refresh_artwork_transform_panel()
        self._schedule_prepared_preview_refresh()
        self._mark_project_dirty()

    def _sync_artwork_controls_from_preview(self) -> None:
        self._artwork_controls.set_transform(self._preview.artwork_transform)

    def _set_artwork_transform(
        self,
        transform: ArtworkTransform,
        *,
        mark_dirty: bool = True,
    ) -> None:
        transform.validate()
        orientation_changed = (
            transform.orientation is not self._preview.artwork_transform.orientation
        )
        self._preview.set_artwork_transform(transform)
        self._sync_artwork_controls_from_preview()
        if orientation_changed:
            # The page-level bounds preflight depends on the effective rotation.
            self._refresh_bounds_status()
        self._schedule_prepared_preview_refresh()
        if mark_dirty:
            self._mark_project_dirty()

    def _on_preview_artwork_dragged(self, transform: object) -> None:
        if isinstance(transform, ArtworkTransform):
            self._sync_artwork_controls_from_preview()
            self._schedule_prepared_preview_refresh()
            self._mark_project_dirty()

    def _on_artwork_controls_changed(self, transform: ArtworkTransform) -> None:
        if transform == self._preview.artwork_transform:
            return
        self._set_artwork_transform(transform)

    def _refresh_bounds_status(self) -> None:
        document = self._document
        if document is None:
            self._bounds_check = None
            self._bounds_status_label.setText("")
            self._bounds_status_label.setVisible(False)
            set_role(self._bounds_status_label, "caption")
            self._refresh_preview_work_area()
            return

        rotation = self._effective_rotation_degrees()
        self._bounds_rotation_degrees = rotation
        self._bounds_check = check_plot_bounds(
            document.raw_text,
            self._settings_service.plot_settings,
            rotation_degrees=rotation,
        )
        prefix, role = _bounds_status_style(self._bounds_check.status)
        self._bounds_status_label.setText(f"{prefix}{self._bounds_check.message}")
        self._bounds_status_label.setVisible(True)
        set_role(self._bounds_status_label, role)
        self._update_plot_controls()


def _coerce_fallback_work_area(value: object) -> FallbackWorkArea | None:
    if isinstance(value, FallbackWorkArea):
        return value
    if value == FallbackWorkArea.A3.value:
        return FallbackWorkArea.A3
    if value == FallbackWorkArea.A4.value:
        return FallbackWorkArea.A4
    return None


def _coerce_work_area_orientation(value: object) -> WorkAreaOrientation | None:
    if isinstance(value, WorkAreaOrientation):
        return value
    if value == WorkAreaOrientation.LANDSCAPE.value:
        return WorkAreaOrientation.LANDSCAPE
    if value == WorkAreaOrientation.PORTRAIT.value:
        return WorkAreaOrientation.PORTRAIT
    return None


def _bounds_status_style(status: BoundsStatus) -> tuple[str, str]:
    """Prefix glyph and stylesheet ``role`` for the bounds preflight label."""
    if status is BoundsStatus.OK:
        return "✓ ", "status-ok"
    if status is BoundsStatus.UNKNOWN_MODEL:
        return "⚠ ", "status-warn"
    if status is BoundsStatus.OUT_OF_BOUNDS:
        return "✕ ", "status-error"
    return "✕ ", "status-error"


def _color_swatch_text(color: str | None) -> str:
    if color:
        qcolor = QColor(color)
        if qcolor.isValid():
            return "●"
    return "●"
