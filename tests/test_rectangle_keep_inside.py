"""Keep-inside rectangle: overlap with the printable area, then Liang–Barsky."""

from __future__ import annotations

from pathlib import Path

import pytest

from golden_oracle import parse_prepared_polylines
from plotpilot.geometry.plot_viewport import PlotViewportError, prepare_positioned_plot_svg
from plotpilot.models.artwork_transform import ArtworkTransform
from plotpilot.models.clip_shape import ClipRectangle, ClipRectangleError
from plotpilot.models.plot_settings import PlotSettings
from plotpilot.models.print_margins import PrintMargins
from plotpilot.services.layer_geometry import position_and_clip_geometry, prepare_layer_geometry
from plotpilot.services.layer_service import layers_for_document
from plotpilot.services.positioned_plot_service import prepare_layer_plot_svg
from plotpilot.services.preview_compute_service import compute_interactive_preview
from plotpilot.services.preview_prepared_service import build_prepared_layer_preview
from plotpilot.services.preview_work_area import FallbackWorkArea, WorkAreaOrientation
from plotpilot.services.svg_loader import load_svg_from_path

_VIEWPORT = (100.0, 100.0)
_TOL = 0.02
_EMPTY = "No artwork intersects the plot area."

_SQUARE = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<svg xmlns="http://www.w3.org/2000/svg" width="200mm" height="200mm" '
    'viewBox="0 0 200 200">\n'
    '  <path d="M 50 50 L 150 50 L 150 150 L 50 150 Z" fill="none" stroke="black"/>\n'
    "</svg>\n"
)


def _line_svg(x0: float, y0: float, x1: float, y1: float, *, size: float = 100.0) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}mm" height="{size}mm" '
        f'viewBox="0 0 {size} {size}">\n'
        f'  <path d="M {x0} {y0} L {x1} {y1}" fill="none" stroke="black"/>\n'
        "</svg>\n"
    )


def _prepare(
    svg: str,
    *,
    viewport: tuple[float, float] = _VIEWPORT,
    keep_inside: ClipRectangle | None = None,
    clip: tuple[float, float, float, float] | None = None,
    transform: ArtworkTransform | None = None,
) -> list[list[tuple[float, float]]]:
    kwargs: dict[str, float] = {}
    if clip is not None:
        kwargs = {
            "clip_x_min_mm": clip[0],
            "clip_y_min_mm": clip[1],
            "clip_x_max_mm": clip[2],
            "clip_y_max_mm": clip[3],
        }
    prepared = prepare_positioned_plot_svg(
        svg,
        viewport_width_mm=viewport[0],
        viewport_height_mm=viewport[1],
        transform=transform or ArtworkTransform.identity(),
        keep_inside=keep_inside,
        **kwargs,
    )
    return parse_prepared_polylines(prepared.svg_text)


def _assert_polylines(
    actual: list[list[tuple[float, float]]],
    expected: list[list[tuple[float, float]]],
) -> None:
    assert len(actual) == len(expected)
    for got, want in zip(actual, expected, strict=True):
        assert len(got) == len(want)
        for point, expected_point in zip(got, want, strict=True):
            assert point == pytest.approx(expected_point, abs=_TOL)


def _assert_inside(
    polylines: list[list[tuple[float, float]]],
    *,
    x_min: float,
    y_min: float,
    x_max: float,
    y_max: float,
) -> None:
    assert polylines
    for polyline in polylines:
        assert len(polyline) >= 2
        for x, y in polyline:
            assert x_min - _TOL <= x <= x_max + _TOL
            assert y_min - _TOL <= y <= y_max + _TOL


def _segment_matches(
    a0: tuple[float, float],
    a1: tuple[float, float],
    b0: tuple[float, float],
    b1: tuple[float, float],
) -> bool:
    def near(a: tuple[float, float], b: tuple[float, float]) -> bool:
        return abs(a[0] - b[0]) <= _TOL and abs(a[1] - b[1]) <= _TOL

    return (near(a0, b0) and near(a1, b1)) or (near(a0, b1) and near(a1, b0))


# ----------------------------------------------------------------- model


def test_rectangle_rejects_non_positive_size() -> None:
    with pytest.raises(ClipRectangleError, match="positive width and height"):
        ClipRectangle(0.0, 0.0, 0.0, 10.0).validate()
    with pytest.raises(ClipRectangleError, match="positive width and height"):
        ClipRectangle(0.0, 0.0, 10.0, -1.0).validate()


def test_rectangle_rejects_non_finite_coordinates() -> None:
    with pytest.raises(ClipRectangleError, match="finite"):
        ClipRectangle(float("nan"), 0.0, 10.0, 10.0).validate()
    with pytest.raises(ClipRectangleError, match="finite"):
        ClipRectangle(0.0, float("inf"), 10.0, 10.0).validate()


def test_prepare_rejects_invalid_rectangle_before_clipping() -> None:
    svg = _line_svg(0, 50, 100, 50)
    with pytest.raises(ClipRectangleError):
        prepare_positioned_plot_svg(
            svg,
            viewport_width_mm=100.0,
            viewport_height_mm=100.0,
            transform=ArtworkTransform.identity(),
            keep_inside=ClipRectangle(0.0, 0.0, 0.0, 10.0),
        )
    assert "M 0 50" in svg


# --------------------------------------------------------------- keep inside


def test_crossing_line_is_trimmed_to_rectangle_edges() -> None:
    polylines = _prepare(
        _line_svg(0, 50, 100, 50),
        keep_inside=ClipRectangle(20.0, 10.0, 40.0, 80.0),
    )
    _assert_polylines(polylines, [[(20.0, 50.0), (60.0, 50.0)]])
    _assert_inside(polylines, x_min=20.0, y_min=10.0, x_max=60.0, y_max=90.0)


def test_diagonal_is_trimmed_to_rectangle() -> None:
    polylines = _prepare(
        _line_svg(0, 0, 100, 100),
        keep_inside=ClipRectangle(25.0, 25.0, 50.0, 50.0),
    )
    _assert_polylines(polylines, [[(25.0, 25.0), (75.0, 75.0)]])


def test_stroke_fully_inside_rectangle_is_kept() -> None:
    polylines = _prepare(
        _line_svg(30, 40, 60, 40),
        keep_inside=ClipRectangle(20.0, 20.0, 50.0, 50.0),
    )
    _assert_polylines(polylines, [[(30.0, 40.0), (60.0, 40.0)]])


def test_stroke_that_misses_rectangle_is_omitted() -> None:
    with pytest.raises(PlotViewportError, match=_EMPTY):
        _prepare(
            _line_svg(0, 10, 10, 10),
            keep_inside=ClipRectangle(50.0, 50.0, 20.0, 20.0),
        )


def test_exit_and_reenter_splits_without_a_bridge() -> None:
    polylines = _prepare(
        _SQUARE,
        viewport=(200.0, 200.0),
        keep_inside=ClipRectangle(0.0, 0.0, 100.0, 100.0),
    )
    assert len(polylines) == 2
    assert polylines[0] == pytest.approx([(50.0, 50.0), (100.0, 50.0)], abs=_TOL)
    assert polylines[1] == pytest.approx([(50.0, 100.0), (50.0, 50.0)], abs=_TOL)
    forbidden = ((100.0, 50.0), (50.0, 100.0))
    for polyline in polylines:
        for start, end in zip(polyline, polyline[1:], strict=False):
            assert not _segment_matches(start, end, forbidden[0], forbidden[1])


def test_touching_only_an_endpoint_drops_the_run() -> None:
    with pytest.raises(PlotViewportError, match=_EMPTY):
        _prepare(
            _line_svg(0, 50, 40, 50),
            keep_inside=ClipRectangle(40.0, 0.0, 20.0, 100.0),
        )


def test_rectangle_overlapping_margin_keeps_only_the_overlap() -> None:
    # Printable window is 10..90. Rectangle is x 0..60, y 40..60. Overlap is x 10..60.
    polylines = _prepare(
        _line_svg(0, 50, 100, 50),
        keep_inside=ClipRectangle(0.0, 40.0, 60.0, 20.0),
        clip=(10.0, 10.0, 90.0, 90.0),
    )
    _assert_polylines(polylines, [[(10.0, 50.0), (60.0, 50.0)]])
    _assert_inside(polylines, x_min=10.0, y_min=40.0, x_max=60.0, y_max=60.0)


def test_rectangle_larger_than_printable_area_does_not_expand_it() -> None:
    clipped = _prepare(
        _line_svg(0, 50, 100, 50),
        keep_inside=ClipRectangle(-10.0, -10.0, 200.0, 200.0),
        clip=(10.0, 10.0, 90.0, 90.0),
    )
    margins_only = _prepare(
        _line_svg(0, 50, 100, 50),
        clip=(10.0, 10.0, 90.0, 90.0),
    )
    _assert_polylines(clipped, margins_only)
    _assert_polylines(clipped, [[(10.0, 50.0), (90.0, 50.0)]])


def test_rectangle_with_no_printable_overlap_is_empty() -> None:
    with pytest.raises(PlotViewportError, match=_EMPTY):
        _prepare(
            _line_svg(0, 50, 100, 50),
            keep_inside=ClipRectangle(0.0, 0.0, 5.0, 5.0),
            clip=(10.0, 10.0, 90.0, 90.0),
        )


def test_shared_edge_with_no_area_is_empty() -> None:
    with pytest.raises(PlotViewportError, match=_EMPTY):
        _prepare(
            _line_svg(0, 50, 100, 50),
            keep_inside=ClipRectangle(0.0, 0.0, 10.0, 50.0),
            clip=(10.0, 10.0, 90.0, 90.0),
        )


def test_square_window_is_a_rectangle_with_equal_sides() -> None:
    polylines = _prepare(
        _line_svg(0, 40, 100, 40),
        keep_inside=ClipRectangle(30.0, 20.0, 40.0, 40.0),
    )
    _assert_polylines(polylines, [[(30.0, 40.0), (70.0, 40.0)]])


# --------------------------------------------------------------- unchanged


def test_omitted_rectangle_matches_explicit_absence() -> None:
    svg = _line_svg(-10, 50, 110, 50)
    omitted = prepare_positioned_plot_svg(
        svg,
        viewport_width_mm=100.0,
        viewport_height_mm=100.0,
        transform=ArtworkTransform.identity(),
    )
    explicit = prepare_positioned_plot_svg(
        svg,
        viewport_width_mm=100.0,
        viewport_height_mm=100.0,
        transform=ArtworkTransform.identity(),
        keep_inside=None,
    )
    assert omitted.svg_text == explicit.svg_text
    _assert_polylines(
        parse_prepared_polylines(omitted.svg_text),
        [[(0.0, 50.0), (100.0, 50.0)]],
    )


def test_rectangle_on_a_larger_page_matches_a_smaller_viewport() -> None:
    with_rectangle = _prepare(
        _SQUARE,
        viewport=(200.0, 200.0),
        keep_inside=ClipRectangle(0.0, 0.0, 100.0, 100.0),
    )
    viewport_only = _prepare(_SQUARE, viewport=(100.0, 100.0))
    _assert_polylines(with_rectangle, viewport_only)


def test_source_svg_and_flattened_polylines_stay_unchanged(tmp_path: Path) -> None:
    svg = _line_svg(0, 50, 100, 50)
    path = tmp_path / "line.svg"
    path.write_text(svg, encoding="utf-8")
    document = load_svg_from_path(path)
    layer = layers_for_document(document)[0]
    geometry = prepare_layer_geometry(document, layer)
    before = geometry.polylines
    raw_before = document.raw_text

    clipped = position_and_clip_geometry(
        geometry,
        ArtworkTransform.identity(),
        viewport_width_mm=100.0,
        viewport_height_mm=100.0,
        print_margins=PrintMargins(0.0, 0.0),
        keep_inside=ClipRectangle(20.0, 0.0, 30.0, 100.0),
    )

    assert document.raw_text == raw_before
    assert path.read_text(encoding="utf-8") == svg
    assert geometry.polylines is before
    assert clipped.polylines
    assert clipped.polylines != before


def test_margins_still_apply_when_no_rectangle_is_supplied() -> None:
    polylines = _prepare(
        _line_svg(0, 50, 100, 50),
        clip=(10.0, 10.0, 90.0, 90.0),
    )
    _assert_polylines(polylines, [[(10.0, 50.0), (90.0, 50.0)]])


# ------------------------------------------------------------------- parity


def _write_document(tmp_path: Path, svg: str) -> tuple[object, object]:
    path = tmp_path / "artwork.svg"
    path.write_text(svg, encoding="utf-8")
    document = load_svg_from_path(path)
    layer = layers_for_document(document)[0]
    return document, layer


def test_preview_and_plot_polylines_match_with_rectangle(tmp_path: Path) -> None:
    document, layer = _write_document(tmp_path, _line_svg(0, 50, 100, 50, size=210))
    settings = PlotSettings()
    transform = ArtworkTransform.identity()
    margins = PrintMargins(10.0, 10.0)
    keep = ClipRectangle(0.0, 40.0, 80.0, 30.0)
    preview = build_prepared_layer_preview(
        document,
        layer,
        plot_settings=settings,
        transform=transform,
        fallback=FallbackWorkArea.A4,
        fallback_orientation=WorkAreaOrientation.PORTRAIT,
        print_margins=margins,
        keep_inside=keep,
    )
    assert preview.prepared is not None
    plotted = prepare_layer_plot_svg(
        preview.context_svg_text,
        plot_settings=settings,
        transform=transform,
        fallback=FallbackWorkArea.A4,
        fallback_orientation=WorkAreaOrientation.PORTRAIT,
        print_margins=margins,
        keep_inside=keep,
    )
    assert preview.prepared.svg_text == plotted.svg_text
    polylines = parse_prepared_polylines(plotted.svg_text)
    # A4 portrait is 210 × 297. Margins 10. Rectangle x 0..80, y 40..70.
    # Overlap is x 10..80, y 40..70. The line sits at y = 50.
    _assert_polylines(polylines, [[(10.0, 50.0), (80.0, 50.0)]])

    interactive = compute_interactive_preview(
        document,
        layer,
        cached_geometry=None,
        transform=transform,
        plot_settings=settings,
        fallback=FallbackWorkArea.A4,
        fallback_orientation=WorkAreaOrientation.PORTRAIT,
        print_margins=margins,
        keep_inside=keep,
    )
    assert interactive.clipped.error_message is None
    _assert_polylines(list(interactive.clipped.polylines), polylines)


def test_preview_and_plot_match_without_a_rectangle(tmp_path: Path) -> None:
    document, layer = _write_document(tmp_path, _line_svg(0, 50, 100, 50, size=210))
    settings = PlotSettings()
    transform = ArtworkTransform.identity()
    margins = PrintMargins(0.0, 0.0)
    preview = build_prepared_layer_preview(
        document,
        layer,
        plot_settings=settings,
        transform=transform,
        print_margins=margins,
    )
    assert preview.prepared is not None
    plotted = prepare_layer_plot_svg(
        preview.context_svg_text,
        plot_settings=settings,
        transform=transform,
        print_margins=margins,
    )
    assert preview.prepared.svg_text == plotted.svg_text


def test_preview_and_plot_share_the_empty_outcome(tmp_path: Path) -> None:
    document, layer = _write_document(tmp_path, _line_svg(0, 50, 100, 50, size=210))
    settings = PlotSettings()
    transform = ArtworkTransform.identity()
    margins = PrintMargins(10.0, 10.0)
    keep = ClipRectangle(0.0, 0.0, 5.0, 5.0)
    preview = build_prepared_layer_preview(
        document,
        layer,
        plot_settings=settings,
        transform=transform,
        print_margins=margins,
        keep_inside=keep,
    )
    assert preview.prepared is None
    assert preview.preparation_error == _EMPTY
    with pytest.raises(PlotViewportError, match=_EMPTY):
        prepare_layer_plot_svg(
            preview.context_svg_text,
            plot_settings=settings,
            transform=transform,
            print_margins=margins,
            keep_inside=keep,
        )
