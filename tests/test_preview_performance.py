"""Interactive preview cache, stale results, and plot parity."""

from __future__ import annotations

import threading
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication

from golden_oracle import parse_prepared_polylines
from plotpilot.geometry import plot_viewport
from plotpilot.geometry.plot_viewport import (
    clip_document_polylines,
    flatten_document_geometry,
    prepare_positioned_plot_svg,
)
from plotpilot.models.artwork_transform import ArtworkTransform
from plotpilot.models.plot_settings import PlotSettings
from plotpilot.plotter.fake import FakePlotterBackend
from plotpilot.services.layer_geometry import LayerGeometryCache, PreviewResultGate
from plotpilot.services.layer_service import layers_for_document
from plotpilot.services.positioned_plot_service import prepare_layer_plot_svg
from plotpilot.services.preview_compute_service import PreviewComputeService
from plotpilot.services.preview_work_area import (
    FallbackWorkArea,
    WorkAreaOrientation,
    resolve_plot_viewport,
)
from plotpilot.services.svg_loader import load_svg_from_path
from plotpilot.ui.main_window import MainWindow

FIXTURES = Path(__file__).resolve().parent / "fixtures"
GOLDEN = FIXTURES / "golden"
SQUARE = (FIXTURES / "square_100mm_path.svg").read_text(encoding="utf-8")
ARC = (GOLDEN / "paths" / "b2_near_complete_arc.svg").read_text(encoding="utf-8")
EXIT_REENTER = (GOLDEN / "clipping" / "b1_square_exit_reenter.svg").read_text(encoding="utf-8")
_TOLERANCE_MM = 0.01


def _assert_matches_emitted_svg(
    svg_text: str,
    transform: ArtworkTransform,
    *,
    viewport_width_mm: float,
    viewport_height_mm: float,
) -> None:
    prepared = prepare_positioned_plot_svg(
        svg_text,
        viewport_width_mm=viewport_width_mm,
        viewport_height_mm=viewport_height_mm,
        transform=transform,
    )
    flattened = flatten_document_geometry(svg_text)
    clipped = clip_document_polylines(
        flattened.polylines,
        transform,
        viewport_width_mm=viewport_width_mm,
        viewport_height_mm=viewport_height_mm,
    )
    emitted = parse_prepared_polylines(prepared.svg_text)
    assert len(clipped) == len(emitted)
    for actual, expected in zip(clipped, emitted, strict=True):
        assert len(actual) == len(expected)
        for point, other in zip(actual, expected, strict=True):
            assert point[0] == pytest.approx(other[0], abs=_TOLERANCE_MM)
            assert point[1] == pytest.approx(other[1], abs=_TOLERANCE_MM)


def test_repeated_transforms_prepare_geometry_once() -> None:
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    layer = layers_for_document(document)[0]
    cache = LayerGeometryCache()
    for x_mm in (0.0, 3.0, -2.0):
        cache.clipped_for(
            document,
            layer,
            ArtworkTransform(x_mm=x_mm, y_mm=1.0, scale=1.0),
            viewport_width_mm=210.0,
            viewport_height_mm=297.0,
        )
    assert cache.prepare_count == 1
    assert cache.clip_count == 3


def test_xy_scale_and_orientation_reuse_flattened_geometry() -> None:
    document = load_svg_from_path(FIXTURES / "square_100mm_path.svg")
    layer = layers_for_document(document)[0]
    cache = LayerGeometryCache()
    identity = cache.clipped_for(
        document,
        layer,
        ArtworkTransform.identity(),
        viewport_width_mm=210.0,
        viewport_height_mm=297.0,
    )
    stored = cache.lookup(id(document), layer.layer_id)
    assert stored is not None
    shifted = cache.clipped_for(
        document,
        layer,
        ArtworkTransform(x_mm=4.0, y_mm=0.0, scale=1.0),
        viewport_width_mm=210.0,
        viewport_height_mm=297.0,
    )
    moved_y = cache.clipped_for(
        document,
        layer,
        ArtworkTransform(x_mm=4.0, y_mm=6.0, scale=1.0),
        viewport_width_mm=210.0,
        viewport_height_mm=297.0,
    )
    scaled = cache.clipped_for(
        document,
        layer,
        ArtworkTransform(x_mm=4.0, y_mm=6.0, scale=1.25),
        viewport_width_mm=210.0,
        viewport_height_mm=297.0,
    )
    landscape = cache.clipped_for(
        document,
        layer,
        ArtworkTransform(x_mm=4.0, y_mm=6.0, scale=1.25),
        viewport_width_mm=80.0,
        viewport_height_mm=200.0,
    )
    assert cache.prepare_count == 1
    assert cache.clip_count == 5
    assert cache.lookup(id(document), layer.layer_id) is stored
    assert identity.polylines != shifted.polylines
    assert shifted.polylines != moved_y.polylines
    assert moved_y.polylines != scaled.polylines
    assert scaled.polylines != landscape.polylines


def test_layer_change_invalidates_cached_geometry() -> None:
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    layers = layers_for_document(document)
    cache = LayerGeometryCache()
    cache.clipped_for(
        document,
        layers[0],
        ArtworkTransform.identity(),
        viewport_width_mm=300.0,
        viewport_height_mm=300.0,
    )
    cache.invalidate()
    assert cache.lookup(id(document), layers[0].layer_id) is None
    cache.clipped_for(
        document,
        layers[1],
        ArtworkTransform.identity(),
        viewport_width_mm=300.0,
        viewport_height_mm=300.0,
    )
    assert cache.prepare_count == 2
    assert cache.lookup(id(document), layers[0].layer_id) is None
    assert cache.lookup(id(document), layers[1].layer_id) is not None


def test_document_change_invalidates_cached_geometry() -> None:
    first = load_svg_from_path(FIXTURES / "square_100mm_path.svg")
    second = load_svg_from_path(FIXTURES / "simple.svg")
    cache = LayerGeometryCache()
    cache.clipped_for(
        first,
        layers_for_document(first)[0],
        ArtworkTransform.identity(),
        viewport_width_mm=300.0,
        viewport_height_mm=300.0,
    )
    cache.clipped_for(
        second,
        layers_for_document(second)[0],
        ArtworkTransform.identity(),
        viewport_width_mm=300.0,
        viewport_height_mm=300.0,
    )
    assert cache.prepare_count == 2
    assert cache.lookup(id(first), layers_for_document(first)[0].layer_id) is None


def test_prepare_leaves_source_document_unchanged() -> None:
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    raw_text = document.raw_text
    root_xml = ET.tostring(document.root)
    layer = layers_for_document(document)[0]
    cache = LayerGeometryCache()
    cache.clipped_for(
        document,
        layer,
        ArtworkTransform(x_mm=2.0, y_mm=-1.0, scale=0.5),
        viewport_width_mm=210.0,
        viewport_height_mm=297.0,
    )
    assert document.raw_text == raw_text
    assert ET.tostring(document.root) == root_xml


def test_stale_generation_is_discarded_and_latest_wins() -> None:
    gate = PreviewResultGate()
    first = gate.issue()
    second = gate.issue()
    applied: list[str] = []
    for generation, payload in ((first, "old"), (second, "new")):
        if gate.accept(generation):
            applied.append(payload)
    assert applied == ["new"]
    gate.shutdown()
    assert gate.accept(second) is False


def test_shutdown_discards_worker_already_in_flight(qapp: QApplication) -> None:
    started = threading.Event()
    release = threading.Event()
    applied: list[object] = []
    service = PreviewComputeService()

    def operation() -> str:
        started.set()
        assert release.wait(timeout=5)
        return "stale"

    def on_finished(generation: int, result: object) -> None:
        if service.gate.accept(generation):
            applied.append(result)

    service.finished.connect(on_finished)
    service.submit(operation)
    assert started.wait(timeout=5)
    service.shutdown()
    release.set()
    assert QThreadPool.globalInstance().waitForDone(5000)
    qapp.processEvents()
    assert applied == []


def test_later_preview_job_wins_when_an_older_job_finishes_last(qapp: QApplication) -> None:
    from PySide6.QtCore import QEventLoop, QTimer

    started = [threading.Event(), threading.Event()]
    release = [threading.Event(), threading.Event()]
    applied: list[object] = []
    service = PreviewComputeService()
    loop = QEventLoop()

    def operation(index: int) -> str:
        started[index].set()
        assert release[index].wait(timeout=5)
        return f"job-{index}"

    def on_finished(generation: int, result: object) -> None:
        if service.gate.accept(generation):
            applied.append(result)
            loop.quit()

    service.finished.connect(on_finished)
    service.submit(lambda: operation(0))
    service.submit(lambda: operation(1))
    assert started[0].wait(timeout=5)
    assert started[1].wait(timeout=5)
    release[1].set()
    QTimer.singleShot(5000, loop.quit)
    loop.exec()
    assert applied == ["job-1"]
    release[0].set()
    assert QThreadPool.globalInstance().waitForDone(5000)
    qapp.processEvents()
    assert applied == ["job-1"]
    service.shutdown()


def test_preview_polylines_match_emitted_plot_svg() -> None:
    _assert_matches_emitted_svg(
        SQUARE,
        ArtworkTransform.identity(),
        viewport_width_mm=200,
        viewport_height_mm=200,
    )
    _assert_matches_emitted_svg(
        ARC,
        ArtworkTransform.identity(),
        viewport_width_mm=100,
        viewport_height_mm=100,
    )
    _assert_matches_emitted_svg(
        EXIT_REENTER,
        ArtworkTransform.identity(),
        viewport_width_mm=100,
        viewport_height_mm=100,
    )
    _assert_matches_emitted_svg(
        SQUARE,
        ArtworkTransform(x_mm=15.0, y_mm=-8.0, scale=1.0),
        viewport_width_mm=200,
        viewport_height_mm=200,
    )
    _assert_matches_emitted_svg(
        SQUARE,
        ArtworkTransform(x_mm=0.0, y_mm=0.0, scale=1.4),
        viewport_width_mm=200,
        viewport_height_mm=200,
    )


def test_portrait_and_landscape_preview_match_plot_svg() -> None:
    document = load_svg_from_path(FIXTURES / "square_100mm_path.svg")
    settings = PlotSettings(model=None)
    transform = ArtworkTransform(x_mm=5.0, y_mm=5.0, scale=1.1)
    for orientation in (WorkAreaOrientation.PORTRAIT, WorkAreaOrientation.LANDSCAPE):
        viewport = resolve_plot_viewport(
            settings,
            fallback=FallbackWorkArea.A4,
            fallback_orientation=orientation,
        )
        prepared = prepare_layer_plot_svg(
            document.raw_text,
            plot_settings=settings,
            transform=transform,
            fallback=FallbackWorkArea.A4,
            fallback_orientation=orientation,
        )
        flattened = flatten_document_geometry(document.raw_text)
        clipped = clip_document_polylines(
            flattened.polylines,
            transform,
            viewport_width_mm=viewport.width_mm,
            viewport_height_mm=viewport.height_mm,
        )
        emitted = parse_prepared_polylines(prepared.svg_text)
        assert len(clipped) == len(emitted)
        for actual, expected in zip(clipped, emitted, strict=True):
            assert len(actual) == len(expected)
            for point, other in zip(actual, expected, strict=True):
                assert point[0] == pytest.approx(other[0], abs=_TOLERANCE_MM)
                assert point[1] == pytest.approx(other[1], abs=_TOLERANCE_MM)


def test_plot_preparation_still_runs_output_validator(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    original = plot_viewport._validate_output_geometry

    def wrapped(svg_text: str, width_mm: float, height_mm: float) -> None:
        calls.append(svg_text)
        original(svg_text, width_mm, height_mm)

    monkeypatch.setattr(plot_viewport, "_validate_output_geometry", wrapped)
    prepare_positioned_plot_svg(
        SQUARE,
        viewport_width_mm=200.0,
        viewport_height_mm=200.0,
        transform=ArtworkTransform.identity(),
    )
    assert len(calls) == 1


def test_transform_refresh_does_not_flatten_on_the_caller(
    qapp: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from plotpilot.services import layer_geometry

    window = MainWindow(plotter_backend=FakePlotterBackend(), svg_file_chooser=lambda: None)
    flatten_calls: list[str] = []
    original = layer_geometry.flatten_document_geometry

    def wrapped(svg_text: str):
        flatten_calls.append("flatten")
        return original(svg_text)

    monkeypatch.setattr(layer_geometry, "flatten_document_geometry", wrapped)
    queued: list[object] = []
    window._preview_compute.submit = lambda operation: (  # type: ignore[method-assign]
        queued.append(operation) or 0
    )
    window.set_document(load_svg_from_path(FIXTURES / "square_100mm_path.svg"))
    window._preview_prep_timer.stop()
    queued.clear()
    flatten_calls.clear()

    window._set_artwork_transform(ArtworkTransform(x_mm=2.0, y_mm=0.0, scale=1.0))
    window._preview_prep_timer.stop()
    window._refresh_prepared_preview()
    assert flatten_calls == []
    assert queued
    result = queued[0]()  # type: ignore[operator]
    assert flatten_calls == ["flatten"]
    assert result.fresh_geometry is not None
    window._geometry_cache.store(result.document_id, result.layer_id, result.fresh_geometry)

    flatten_calls.clear()
    queued.clear()
    window._set_artwork_transform(ArtworkTransform(x_mm=3.0, y_mm=1.0, scale=1.2))
    window._preview_prep_timer.stop()
    window._refresh_prepared_preview()
    assert flatten_calls == []
    assert queued
    queued[0]()  # type: ignore[operator]
    assert flatten_calls == []
    window.close()
