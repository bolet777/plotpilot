"""Primary application window."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QIcon, QKeySequence, QPainter, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from plotpilot.models.artwork_transform import (
    DEFAULT_SCALE_MAX,
    DEFAULT_SCALE_MIN,
    ArtworkTransform,
    scale_percent,
    transform_from_scale_percent,
)
from plotpilot.models.multi_layer_job import MultiLayerJobState, MultiLayerPlotJob
from plotpilot.models.plot_bounds import BoundsStatus, PlotBoundsCheck
from plotpilot.models.plot_job import PlotPhase, PlotState
from plotpilot.models.plot_progress import PlotProgress
from plotpilot.models.plotter_status import PlotterConnectionState, PlotterStatus
from plotpilot.models.svg_document import SvgDocument
from plotpilot.models.svg_layer import SvgLayer
from plotpilot.plotter.axidraw import AxiDrawCliBackend
from plotpilot.plotter.base import PlotterBackend
from plotpilot.services.bounds_service import check_plot_bounds
from plotpilot.services.layer_service import layers_for_document
from plotpilot.services.multi_layer_plot_service import MultiLayerPlotService
from plotpilot.services.plotter_service import PlotterService
from plotpilot.services.preview_service import preview_svg_for_layer
from plotpilot.services.preview_work_area import (
    FallbackWorkArea,
    preview_work_area_is_ambiguous,
    resolve_preview_work_area,
)
from plotpilot.services.settings_service import SettingsService
from plotpilot.services.svg_loader import SvgLoadError, load_svg_from_path
from plotpilot.svg.plot_dimensions import PlotDimensionError, parse_physical_size
from plotpilot.ui.plot_progress_labels import (
    progress_fraction_label,
    progress_headline,
    progress_next_layer_line,
    progress_timing_line,
)
from plotpilot.ui.plot_settings_widget import PlotSettingsWidget
from plotpilot.ui.preview_widget import LayerPreviewWidget


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


class MainWindow(QMainWindow):
    """PlotPilot main window."""

    def __init__(
        self,
        *,
        plotter_backend: PlotterBackend | None = None,
        settings_service: SettingsService | None = None,
        svg_file_chooser: Callable[[], str | None] | None = None,
        auto_detect_interval_ms: int | None = None,
        auto_detect_resume_delay_ms: int | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("PlotPilot")
        self.resize(900, 560)

        self._document: SvgDocument | None = None
        self._layers: list[SvgLayer] = []
        self._updating_layers = False
        self._bounds_check: PlotBoundsCheck | None = None

        backend = plotter_backend if plotter_backend is not None else AxiDrawCliBackend()
        self._settings_service = (
            settings_service if settings_service is not None else SettingsService(parent=self)
        )
        self._svg_file_chooser = svg_file_chooser
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
        self._multi_layer_service = MultiLayerPlotService(self._plotter_service, parent=self)
        self._multi_layer_service.job_changed.connect(self._apply_multi_layer_job)
        self._multi_layer_service.pen_change_required.connect(self._on_pen_change_required)

        central = QWidget(self)
        root_layout = QVBoxLayout(central)

        content_row = QHBoxLayout()
        left_column = QVBoxLayout()
        layers_heading = QLabel("Layers", central)
        layers_heading.setStyleSheet("font-weight: bold;")
        left_column.addWidget(layers_heading)

        self._layers_list = QListWidget(central)
        self._layers_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._layers_list.setMinimumWidth(220)
        self._layers_list.currentRowChanged.connect(self._on_layer_row_changed)
        self._layers_list.itemChanged.connect(self._on_layer_item_changed)
        left_column.addWidget(self._layers_list, stretch=1)

        content_row.addLayout(left_column, stretch=0)

        preview_column = QVBoxLayout()
        preview_column.setSpacing(6)

        self._open_svg_persistent_button = QPushButton("Open SVG…", central)
        self._open_svg_persistent_button.setVisible(False)
        preview_column.addWidget(
            self._open_svg_persistent_button,
            alignment=Qt.AlignmentFlag.AlignLeft,
        )

        self._fallback_work_area_row = QWidget(central)
        fallback_row = QHBoxLayout(self._fallback_work_area_row)
        fallback_row.setContentsMargins(0, 0, 0, 0)
        fallback_row.addWidget(QLabel("Work area:", self._fallback_work_area_row))
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
        fallback_row.addWidget(self._fallback_work_area_combo)
        fallback_row.addStretch(1)
        preview_column.addWidget(self._fallback_work_area_row)

        self._position_row = QWidget(central)
        position_layout = QHBoxLayout(self._position_row)
        position_layout.setContentsMargins(0, 0, 0, 0)
        position_layout.addWidget(QLabel("Position", self._position_row))
        position_layout.addWidget(QLabel("X:", self._position_row))
        self._artwork_x_spin = QDoubleSpinBox(self._position_row)
        self._artwork_x_spin.setRange(-2000.0, 2000.0)
        self._artwork_x_spin.setSuffix(" mm")
        self._artwork_x_spin.setDecimals(1)
        self._artwork_x_spin.valueChanged.connect(self._on_artwork_position_spin_changed)
        position_layout.addWidget(self._artwork_x_spin)
        position_layout.addWidget(QLabel("Y:", self._position_row))
        self._artwork_y_spin = QDoubleSpinBox(self._position_row)
        self._artwork_y_spin.setRange(-2000.0, 2000.0)
        self._artwork_y_spin.setSuffix(" mm")
        self._artwork_y_spin.setDecimals(1)
        self._artwork_y_spin.valueChanged.connect(self._on_artwork_position_spin_changed)
        position_layout.addWidget(self._artwork_y_spin)
        position_layout.addSpacing(8)
        position_layout.addWidget(QLabel("Scale:", self._position_row))
        self._artwork_scale_spin = QDoubleSpinBox(self._position_row)
        self._artwork_scale_spin.setRange(DEFAULT_SCALE_MIN * 100.0, DEFAULT_SCALE_MAX * 100.0)
        self._artwork_scale_spin.setSuffix(" %")
        self._artwork_scale_spin.setDecimals(0)
        self._artwork_scale_spin.valueChanged.connect(self._on_artwork_scale_spin_changed)
        position_layout.addWidget(self._artwork_scale_spin)
        self._artwork_reset_button = QPushButton("Reset", self._position_row)
        self._artwork_reset_button.clicked.connect(self._on_artwork_reset)
        position_layout.addWidget(self._artwork_reset_button)
        position_layout.addStretch(1)
        preview_column.addWidget(self._position_row)

        self._artwork_status_label = QLabel("", central)
        self._artwork_status_label.setWordWrap(True)
        preview_column.addWidget(self._artwork_status_label)

        self._preview_stack = QStackedWidget(central)
        self._preview_empty_page = QWidget(central)
        empty_layout = QVBoxLayout(self._preview_empty_page)
        empty_layout.addStretch(1)
        empty_heading = QLabel("No SVG loaded", self._preview_empty_page)
        empty_heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_heading.setStyleSheet("font-size: 14px; color: #444444;")
        empty_layout.addWidget(empty_heading)
        empty_layout.addSpacing(12)
        self._open_svg_empty_button = QPushButton("Open SVG…", self._preview_empty_page)
        empty_layout.addWidget(
            self._open_svg_empty_button,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        open_shortcut = QKeySequence(QKeySequence.StandardKey.Open).toString(
            QKeySequence.SequenceFormat.NativeText,
        )
        empty_shortcut_hint = QLabel(
            f"or press {open_shortcut}",
            self._preview_empty_page,
        )
        empty_shortcut_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_shortcut_hint.setStyleSheet("color: #666666;")
        empty_layout.addWidget(empty_shortcut_hint)
        empty_layout.addStretch(1)

        self._preview = LayerPreviewWidget(central)
        self._preview.artwork_transform_changed.connect(self._on_preview_artwork_dragged)
        self._preview_stack.addWidget(self._preview_empty_page)
        self._preview_stack.addWidget(self._preview)
        self._sync_artwork_controls_from_preview()
        preview_column.addWidget(self._preview_stack, stretch=1)

        preview_column_host = QWidget(central)
        preview_column_host.setLayout(preview_column)
        content_row.addWidget(preview_column_host, stretch=1)

        root_layout.addLayout(content_row, stretch=1)

        plotter_heading = QLabel("Plotter", central)
        plotter_heading.setStyleSheet("font-weight: bold;")
        root_layout.addWidget(plotter_heading)

        plotter_row = QHBoxLayout()
        self._plotter_name_label = QLabel("AxiDraw", central)
        plotter_row.addWidget(self._plotter_name_label)

        self._plotter_status_label = QLabel("○ Not connected", central)
        self._plotter_status_label.setWordWrap(True)
        plotter_row.addWidget(self._plotter_status_label, stretch=1)
        root_layout.addLayout(plotter_row)

        plotter_buttons = QHBoxLayout()
        self._pen_up_button = QPushButton("Pen ↑", central)
        self._pen_up_button.clicked.connect(self._plotter_service.pen_up)
        plotter_buttons.addWidget(self._pen_up_button)

        self._pen_down_button = QPushButton("Pen ↓", central)
        self._pen_down_button.clicked.connect(self._plotter_service.pen_down)
        plotter_buttons.addWidget(self._pen_down_button)

        self._plotter_refresh_button = QPushButton("Refresh", central)
        self._plotter_refresh_button.clicked.connect(self._plotter_service.refresh)
        plotter_buttons.addWidget(self._plotter_refresh_button)

        self._plot_layer_button = QPushButton("Plot Selected Layer", central)
        self._plot_layer_button.clicked.connect(self._on_plot_selected_layer)
        plotter_buttons.addWidget(self._plot_layer_button)

        self._plot_checked_button = QPushButton("Plot Checked Layers", central)
        self._plot_checked_button.clicked.connect(self._on_plot_checked_layers)
        plotter_buttons.addWidget(self._plot_checked_button)

        self._plot_stop_button = QPushButton("Stop", central)
        self._plot_stop_button.clicked.connect(self._on_stop_plot)
        self._plot_stop_button.setEnabled(False)
        plotter_buttons.addWidget(self._plot_stop_button)

        self._multi_continue_button = QPushButton("Continue", central)
        self._multi_continue_button.clicked.connect(self._on_multi_continue)
        self._multi_continue_button.setVisible(False)
        plotter_buttons.addWidget(self._multi_continue_button)

        plotter_buttons.addStretch(1)
        root_layout.addLayout(plotter_buttons)

        self._plot_settings = PlotSettingsWidget(self._settings_service, parent=central)
        self._plot_settings.user_changed.connect(self._on_plot_settings_changed)
        root_layout.addWidget(self._plot_settings)

        self._bounds_status_label = QLabel("", central)
        self._bounds_status_label.setWordWrap(True)
        root_layout.addWidget(self._bounds_status_label)

        self._plot_progress_headline = QLabel("", central)
        self._plot_progress_headline.setWordWrap(True)
        self._plot_progress_headline.setVisible(False)
        root_layout.addWidget(self._plot_progress_headline)

        self._plot_progress_bar = QProgressBar(central)
        self._plot_progress_bar.setVisible(False)
        self._plot_progress_bar.setTextVisible(True)
        self._plot_progress_bar.setRange(0, 100)
        root_layout.addWidget(self._plot_progress_bar)

        self._plot_progress_timing = QLabel("", central)
        self._plot_progress_timing.setVisible(False)
        root_layout.addWidget(self._plot_progress_timing)

        self._plot_progress_next = QLabel("", central)
        self._plot_progress_next.setVisible(False)
        root_layout.addWidget(self._plot_progress_next)

        self._plot_activity_label = QLabel("", central)
        self._plot_activity_label.setWordWrap(True)
        root_layout.addWidget(self._plot_activity_label)

        self._pen_change_label = QLabel("", central)
        self._pen_change_label.setWordWrap(True)
        self._pen_change_label.setVisible(False)
        root_layout.addWidget(self._pen_change_label)

        self._plotter_message_label = QLabel("", central)
        self._plotter_message_label.setWordWrap(True)
        root_layout.addWidget(self._plotter_message_label)

        self._status_label = QLabel("", central)
        self._status_label.setWordWrap(True)
        root_layout.addWidget(self._status_label)

        self.setCentralWidget(central)
        self._build_menu()
        self._open_svg_empty_button.clicked.connect(self._open_svg_action.trigger)
        self._open_svg_persistent_button.clicked.connect(self._open_svg_action.trigger)
        self._open_svg_action.enabledChanged.connect(self._open_svg_empty_button.setEnabled)
        self._open_svg_action.enabledChanged.connect(self._open_svg_persistent_button.setEnabled)
        self._sync_preview_empty_state()
        self._apply_plotter_status(self._plotter_service.status)
        self._apply_plot_state(self._plotter_service.plot_state)
        self._apply_plot_progress(self._plotter_service.plot_progress)
        self._apply_multi_layer_job(self._multi_layer_service.job)
        self._refresh_bounds_status()
        self._sync_fallback_work_area_visibility()
        self._refresh_preview_work_area()
        self._update_plot_controls()
        self._plotter_service.start_automatic_monitoring()

    def closeEvent(self, event) -> None:  # noqa: N802 — Qt API
        self._plotter_service.shutdown()
        super().closeEvent(event)

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")

        self._open_svg_action = QAction("Open SVG…", self)
        self._open_svg_action.setShortcut(QKeySequence.StandardKey.Open)
        self._open_svg_action.triggered.connect(self._open_svg)
        file_menu.addAction(self._open_svg_action)

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

    def _apply_plotter_status(self, status: PlotterStatus) -> None:
        if status.state is PlotterConnectionState.CONNECTED:
            indicator = "● Connected"
        elif status.state is PlotterConnectionState.ERROR:
            indicator = "● Error"
        else:
            indicator = "○ Not connected"
        self._plotter_status_label.setText(indicator)
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
        self._plot_progress_headline.setVisible(visible)
        self._plot_progress_bar.setVisible(visible)
        self._plot_progress_timing.setVisible(visible)
        if not visible:
            self._plot_progress_next.setVisible(False)
            self._plot_progress_bar.setRange(0, 100)
            self._plot_progress_bar.setValue(0)

    def _apply_multi_layer_job(self, job: MultiLayerPlotJob) -> None:
        if job.state is MultiLayerJobState.IDLE:
            self._pen_change_label.setVisible(False)
            self._multi_continue_button.setVisible(False)
            return

        if job.state is MultiLayerJobState.WAITING_FOR_PEN_CHANGE:
            self._plot_activity_label.setText(job.progress_label)
            self._update_pen_change_panel(job)
            self._pen_change_label.setVisible(True)
            self._multi_continue_button.setVisible(True)
        elif job.state is MultiLayerJobState.PLOTTING:
            self._pen_change_label.setVisible(False)
            self._multi_continue_button.setVisible(False)
            self._plot_activity_label.setText(job.progress_label)
        else:
            self._pen_change_label.setVisible(False)
            self._multi_continue_button.setVisible(False)
            self._plot_activity_label.setText(job.message)
        self._update_plot_controls()

    def _update_pen_change_panel(self, job: MultiLayerPlotJob) -> None:
        nxt = job.current_layer
        if nxt is None:
            self._pen_change_label.setText("")
            return
        swatch = _color_swatch_text(nxt.representative_color)
        if nxt.representative_color:
            body = (
                f"Layer {job.completed_count} complete\n\n"
                f"Next layer:\n{swatch} {nxt.name}\n\n"
                f"Change the pen to {nxt.name}."
            )
        else:
            human = job.current_index + 1
            body = (
                f"Layer {job.completed_count} complete\n\n"
                f"Next layer:\nLayer {human}\n\n"
                f"Change the pen for the next layer."
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
        self._plotter_refresh_button.setEnabled(not plot_active and not job_active)
        pen_ok = (
            self._plotter_service.status.pen_commands_enabled
            and not plot_active
            and not job_active
            and not stopping
        )
        self._pen_up_button.setEnabled(pen_ok)
        self._pen_down_button.setEnabled(pen_ok)
        settings_locked = plot_active or job_active
        self._plot_settings.set_plotting_active(settings_locked)
        transform_locked = plot_active or job_active
        self._preview.set_transform_controls_enabled(not transform_locked)
        self._position_row.setEnabled(not transform_locked)
        self._open_svg_action.setEnabled(not job_active)
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

    def _open_svg(self) -> None:
        if self._multi_layer_service.job.is_active:
            return
        if self._svg_file_chooser is not None:
            chosen = self._svg_file_chooser()
        else:
            chosen = choose_svg_file(self)
        if not chosen:
            return

        try:
            document = load_svg_from_path(Path(chosen))
        except SvgLoadError as exc:
            QMessageBox.warning(
                self,
                "Could not open SVG",
                exc.user_message,
            )
            return

        self.set_document(document)

    def _sync_preview_empty_state(self) -> None:
        has_document = self._document is not None
        self._preview_stack.setCurrentIndex(1 if has_document else 0)
        self._open_svg_persistent_button.setVisible(has_document)

    def _apply_document(self, document: SvgDocument) -> None:
        self._set_artwork_transform(ArtworkTransform.identity())
        self._document = document
        self._layers = layers_for_document(document)
        self._status_label.setText(document.name)
        self._sync_preview_empty_state()
        self._refresh_layers_list()

    def _refresh_layers_list(self) -> None:
        self._updating_layers = True
        self._layers_list.blockSignals(True)
        self._layers_list.clear()
        for index, layer in enumerate(self._layers, start=1):
            item = QListWidgetItem(f"{index}  {layer.name}")
            item.setIcon(_layer_swatch_icon(layer.representative_color))
            item.setData(Qt.ItemDataRole.UserRole, layer.layer_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._layers_list.addItem(item)
        if self._layers_list.count() > 0:
            self._layers_list.setCurrentRow(0)
        self._layers_list.blockSignals(False)
        self._updating_layers = False
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
        self._update_plot_controls()

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
        self._refresh_preview_work_area()

    def set_document(self, document: SvgDocument) -> None:
        """Replace the active document and layer list (used after successful load)."""
        self._apply_document(document)
        self._refresh_bounds_status()
        self._update_plot_controls()

    def _on_plot_settings_changed(self) -> None:
        self._sync_fallback_work_area_visibility()
        self._refresh_bounds_status()
        self._refresh_preview_work_area()

    def _on_fallback_work_area_changed(self, _index: int) -> None:
        area = self._fallback_work_area_combo.currentData()
        if not isinstance(area, FallbackWorkArea):
            return
        self._settings_service.set_preview_fallback_work_area(area)
        self._refresh_preview_work_area()

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

        work_area = resolve_preview_work_area(
            self._settings_service.plot_settings,
            fallback=self._settings_service.preview_fallback_work_area,
        )
        try:
            physical = parse_physical_size(self._preview.last_svg)
        except PlotDimensionError:
            self._preview.set_work_area_overlay(
                svg_width_mm=0.0,
                svg_height_mm=0.0,
                work_area=None,
            )
            return

        self._preview.set_work_area_overlay(
            svg_width_mm=physical.width_mm,
            svg_height_mm=physical.height_mm,
            work_area=work_area,
        )
        self._refresh_artwork_status()

    def _refresh_artwork_status(self) -> None:
        transform = self._preview.artwork_transform
        work_area = resolve_preview_work_area(
            self._settings_service.plot_settings,
            fallback=self._settings_service.preview_fallback_work_area,
        )
        if work_area is None:
            self._artwork_status_label.setText("")
            return
        lines = [
            f"Artwork — X: {transform.x_mm:.1f} mm, Y: {transform.y_mm:.1f} mm, "
            f"Scale: {scale_percent(transform):.0f}%",
            f"Plot area: {work_area.label}",
        ]
        if work_area.from_fallback:
            lines.append("User-defined work area (not verified hardware).")
        self._artwork_status_label.setText("\n".join(lines))

    def _sync_artwork_controls_from_preview(self) -> None:
        transform = self._preview.artwork_transform
        for spin, value in (
            (self._artwork_x_spin, transform.x_mm),
            (self._artwork_y_spin, transform.y_mm),
            (self._artwork_scale_spin, scale_percent(transform)),
        ):
            spin.blockSignals(True)
            spin.setValue(value)
            spin.blockSignals(False)

    def _set_artwork_transform(self, transform: ArtworkTransform) -> None:
        transform.validate()
        self._preview.set_artwork_transform(transform)
        self._sync_artwork_controls_from_preview()
        self._refresh_artwork_status()

    def _on_preview_artwork_dragged(self, transform: object) -> None:
        if isinstance(transform, ArtworkTransform):
            self._sync_artwork_controls_from_preview()
            self._refresh_artwork_status()

    def _on_artwork_position_spin_changed(self, _value: float) -> None:
        moved = ArtworkTransform(
            x_mm=self._artwork_x_spin.value(),
            y_mm=self._artwork_y_spin.value(),
            scale=self._preview.artwork_transform.scale,
        )
        self._set_artwork_transform(moved)

    def _on_artwork_scale_spin_changed(self, value: float) -> None:
        current = self._preview.artwork_transform
        try:
            scaled = transform_from_scale_percent(current, value)
        except ValueError:
            return
        self._set_artwork_transform(
            ArtworkTransform(x_mm=current.x_mm, y_mm=current.y_mm, scale=scaled.scale),
        )

    def _on_artwork_reset(self) -> None:
        self._set_artwork_transform(ArtworkTransform.identity())

    def _refresh_bounds_status(self) -> None:
        document = self._document
        if document is None:
            self._bounds_check = None
            self._bounds_status_label.setText("")
            self._bounds_status_label.setStyleSheet("")
            self._refresh_preview_work_area()
            return

        self._bounds_check = check_plot_bounds(
            document.raw_text,
            self._settings_service.plot_settings,
        )
        prefix, color = _bounds_status_style(self._bounds_check.status)
        self._bounds_status_label.setText(f"{prefix}{self._bounds_check.message}")
        self._bounds_status_label.setStyleSheet(f"color: {color};")
        self._update_plot_controls()


def _bounds_status_style(status: BoundsStatus) -> tuple[str, str]:
    if status is BoundsStatus.OK:
        return "✓ ", "#1a7f37"
    if status is BoundsStatus.UNKNOWN_MODEL:
        return "⚠ ", "#9a6700"
    if status is BoundsStatus.OUT_OF_BOUNDS:
        return "✕ ", "#cf222e"
    return "✕ ", "#cf222e"


def _color_swatch_text(color: str | None) -> str:
    if color:
        qcolor = QColor(color)
        if qcolor.isValid():
            return "●"
    return "●"


def _layer_swatch_icon(color: str | None) -> QIcon:
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    if color:
        qcolor = QColor(color)
        brush_color = qcolor if qcolor.isValid() else QColor("#808080")
    else:
        brush_color = QColor("#c0c0c0")
    painter.setBrush(brush_color)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(2, 2, 12, 12)
    painter.end()
    return QIcon(pixmap)
