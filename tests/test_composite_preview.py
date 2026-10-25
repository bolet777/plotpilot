"""Checked-layer composite preview. Plot targets stay on the list selection."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from plotpilot.models.svg_document import SvgDocument
from plotpilot.services.layer_geometry import (
    LayerGeometryCache,
    PreviewCompositeCache,
    prepare_composite_geometry,
    prepare_layer_geometry,
)
from plotpilot.services.layer_service import layers_for_document
from plotpilot.services.preview_service import composite_preview_layers, preview_svg_for_layers
from plotpilot.services.svg_loader import load_svg_from_path
from plotpilot.svg.parse import parse_svg_text
from plotpilot.ui.main_window import MainWindow
from qt_helpers import wait_until

FIXTURES = Path(__file__).resolve().parent / "fixtures"

_NESTED = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
     width="100mm" height="100mm" viewBox="0 0 100 100">
  <g inkscape:groupmode="layer" inkscape:label="Parent" id="parent"
     transform="translate(5,6)" stroke="black" fill="none">
    <g inkscape:groupmode="layer" inkscape:label="Child" id="child">
      <rect id="keep-me" x="0" y="0" width="10" height="4"/>
    </g>
    <rect id="sibling" x="40" y="40" width="10" height="4"/>
  </g>
</svg>"""


def _two_layers():
    document = load_svg_from_path(FIXTURES / "preview_two_layers.svg")
    return document, layers_for_document(document)


def _nested_document() -> SvgDocument:
    return SvgDocument(
        path=FIXTURES / "inline.svg",
        name="inline.svg",
        raw_text=_NESTED,
        root=parse_svg_text(_NESTED),
    )


def _check(window: MainWindow, row: int, *, checked: bool = True) -> None:
    item = window._layers_list.item(row)
    assert item is not None
    item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)


def _wait_for_composite(window: MainWindow, layer_ids: tuple[str, ...]) -> None:
    document = window.document
    assert document is not None

    def ready() -> bool:
        geometry = window._composite_cache.lookup(id(document), layer_ids)
        return (
            geometry is not None
            and window._preview.context_polylines == geometry.polylines
            and not window._preview.clip_pending
        )

    wait_until(ready, timeout_ms=5000)


def _wait_for_highlighted(window: MainWindow) -> None:
    document = window.document
    layer = window._current_layer()
    assert document is not None and layer is not None

    def ready() -> bool:
        geometry = window._geometry_cache.lookup(id(document), layer.layer_id)
        return (
            geometry is not None
            and window._preview.context_polylines == geometry.polylines
            and not window._preview.clip_pending
            and window._composite_cache.lookup(id(document), (layer.layer_id,)) is None
        )

    wait_until(ready, timeout_ms=5000)


def test_root_siblings_stay_independent() -> None:
    document, layers = _two_layers()
    assert composite_preview_layers(document, layers) == tuple(layers)
    preview = preview_svg_for_layers(document, layers)
    assert "only-in-layer-a" in preview
    assert "only-in-layer-b" in preview


def test_nested_parent_and_child_are_not_drawn_twice() -> None:
    document = _nested_document()
    layers = layers_for_document(document)
    parent = next(layer for layer in layers if layer.name == "Parent")
    child = next(layer for layer in layers if layer.name == "Child")
    assert composite_preview_layers(document, [parent, child]) == (parent,)

    parent_geometry = prepare_layer_geometry(document, parent)
    child_geometry = prepare_layer_geometry(document, child)
    composite = prepare_composite_geometry(document, [parent, child])
    assert len(parent_geometry.polylines) > len(child_geometry.polylines)
    assert composite.polylines == parent_geometry.polylines
    assert composite.context_svg_text.count("keep-me") == 1
    assert "sibling" in composite.context_svg_text


def test_composite_cache_is_separate_from_highlighted_layer_cache() -> None:
    document, layers = _two_layers()
    highlighted = prepare_layer_geometry(document, layers[0])
    composite = prepare_composite_geometry(document, layers)
    single = LayerGeometryCache()
    checked = PreviewCompositeCache()
    single.store(id(document), layers[0].layer_id, highlighted)
    layer_ids = (layers[0].layer_id, layers[1].layer_id)
    checked.store(id(document), layer_ids, composite)

    assert single.lookup(id(document), layers[0].layer_id) is highlighted
    assert checked.lookup(id(document), layer_ids) is composite
    assert highlighted is not composite
    assert "only-in-layer-b" not in highlighted.context_svg_text
    assert "only-in-layer-a" in composite.context_svg_text
    assert "only-in-layer-b" in composite.context_svg_text
    assert checked.lookup(id(document), (layers[1].layer_id, layers[0].layer_id)) is None


def test_no_checked_layers_preview_the_highlighted_layer(main_window: MainWindow) -> None:
    main_window.set_document(load_svg_from_path(FIXTURES / "preview_two_layers.svg"))
    preview = main_window.current_preview_svg
    assert preview is not None
    assert "only-in-layer-a" in preview
    assert "only-in-layer-b" not in preview

    main_window._layers_list.setCurrentRow(1)
    preview = main_window.current_preview_svg
    assert preview is not None
    assert "only-in-layer-b" in preview
    assert "only-in-layer-a" not in preview
    _wait_for_highlighted(main_window)


def test_one_checked_layer_previews_that_layer_even_if_not_highlighted(
    main_window: MainWindow,
) -> None:
    main_window.set_document(load_svg_from_path(FIXTURES / "preview_two_layers.svg"))
    assert main_window._layers_list.currentRow() == 0
    _check(main_window, 1)
    preview = main_window.current_preview_svg
    assert preview is not None
    assert "only-in-layer-b" in preview
    assert "only-in-layer-a" not in preview

    layer_b = main_window.layers[1]
    _wait_for_composite(main_window, (layer_b.layer_id,))
    highlighted = main_window._geometry_cache.lookup(
        id(main_window.document),
        main_window.layers[0].layer_id,
    )
    composite = main_window._composite_cache.lookup(
        id(main_window.document),
        (layer_b.layer_id,),
    )
    assert highlighted is not None and composite is not None
    assert highlighted is not composite
    assert "only-in-layer-b" not in highlighted.context_svg_text
    assert "only-in-layer-a" not in composite.context_svg_text
    assert main_window._preview.context_polylines == composite.polylines
    assert main_window._preview.context_polylines != highlighted.polylines


def test_several_checked_layers_preview_the_union(main_window: MainWindow) -> None:
    main_window.set_document(load_svg_from_path(FIXTURES / "preview_two_layers.svg"))
    _check(main_window, 0)
    _check(main_window, 1)
    preview = main_window.current_preview_svg
    assert preview is not None
    assert "only-in-layer-a" in preview
    assert "only-in-layer-b" in preview
    layer_ids = tuple(layer.layer_id for layer in main_window.layers)
    _wait_for_composite(main_window, layer_ids)
    composite = main_window._composite_cache.lookup(id(main_window.document), layer_ids)
    highlighted = main_window._geometry_cache.lookup(
        id(main_window.document),
        main_window.layers[0].layer_id,
    )
    assert composite is not None and highlighted is not None
    assert composite is not highlighted
    assert len(composite.polylines) == len(highlighted.polylines) + len(
        prepare_layer_geometry(main_window.document, main_window.layers[1]).polylines
    )
    assert main_window._preview.context_polylines == composite.polylines
    assert "only-in-layer-b" not in highlighted.context_svg_text


def test_highlight_change_does_not_replace_the_composite_preview(
    main_window: MainWindow,
) -> None:
    main_window.set_document(load_svg_from_path(FIXTURES / "preview_two_layers.svg"))
    _check(main_window, 0)
    _check(main_window, 1)
    layer_ids = tuple(layer.layer_id for layer in main_window.layers)
    _wait_for_composite(main_window, layer_ids)
    preview = main_window.current_preview_svg
    ink = main_window._preview.context_polylines

    main_window._layers_list.setCurrentRow(1)
    assert main_window.current_preview_svg == preview
    assert main_window._preview.context_polylines == ink
    assert "only-in-layer-a" in (preview or "")
    assert "only-in-layer-b" in (preview or "")

    layer_b = main_window.layers[1]
    wait_until(
        lambda: (
            main_window._geometry_cache.lookup(id(main_window.document), layer_b.layer_id)
            is not None
        ),
        timeout_ms=5000,
    )
    highlighted = main_window._geometry_cache.lookup(id(main_window.document), layer_b.layer_id)
    assert highlighted is not None
    assert "only-in-layer-a" not in highlighted.context_svg_text
    assert main_window.current_preview_svg == preview
    assert main_window._preview.context_polylines == ink
    stored = main_window._composite_cache.lookup(id(main_window.document), layer_ids)
    assert stored is not highlighted


def test_unchecking_the_last_layer_returns_to_the_highlighted_preview(
    main_window: MainWindow,
) -> None:
    main_window.set_document(load_svg_from_path(FIXTURES / "preview_two_layers.svg"))
    main_window._layers_list.setCurrentRow(1)
    _check(main_window, 0)
    _check(main_window, 0, checked=False)
    preview = main_window.current_preview_svg
    assert preview is not None
    assert "only-in-layer-b" in preview
    assert "only-in-layer-a" not in preview
    _wait_for_highlighted(main_window)


def test_nested_checks_do_not_duplicate_child_geometry(main_window: MainWindow) -> None:
    document = _nested_document()
    parent = next(layer for layer in layers_for_document(document) if layer.name == "Parent")
    parent_geometry = prepare_layer_geometry(document, parent)
    main_window.set_document(document)
    _check(main_window, 0)
    _check(main_window, 1)
    preview = main_window.current_preview_svg
    assert preview is not None
    assert preview.count("keep-me") == 1
    assert "sibling" in preview
    _wait_for_composite(main_window, (parent.layer_id,))
    composite = main_window._composite_cache.lookup(id(main_window.document), (parent.layer_id,))
    assert composite is not None
    assert composite.polylines == parent_geometry.polylines


def test_plot_layer_still_targets_the_highlighted_layer(
    main_window: MainWindow,
    monkeypatch,
) -> None:
    main_window.set_document(load_svg_from_path(FIXTURES / "preview_two_layers.svg"))
    _check(main_window, 1)
    recorded: list[str] = []

    def spy(_document, layer, **_kwargs) -> None:
        recorded.append(layer.layer_id)
        return None

    monkeypatch.setattr(main_window._plotter_service, "start_plot_layer", spy)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )
    main_window._on_plot_selected_layer()
    assert recorded == [main_window.layers[0].layer_id]


def test_plot_checked_layers_still_targets_the_checked_layers(
    main_window: MainWindow,
    monkeypatch,
) -> None:
    main_window.set_document(load_svg_from_path(FIXTURES / "preview_two_layers.svg"))
    _check(main_window, 1)
    recorded: list[tuple[str, ...]] = []

    def spy(_document, layers, **_kwargs) -> None:
        recorded.append(tuple(layer.layer_id for layer in layers))
        return None

    monkeypatch.setattr(main_window._multi_layer_service, "start_job", spy)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )
    main_window._on_plot_checked_layers()
    assert recorded == [(main_window.layers[1].layer_id,)]
